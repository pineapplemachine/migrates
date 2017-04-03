"""
This module implements migrates' actual migration process.
"""

from __future__ import division

import sys, os, re, copy, datetime, collections, json
import elasticsearch
from elasticsearch import helpers as eshelpers

from .batch import Batch
from .logger import Logger
from .detail import MigratesIndexDetail



__version__ = (0, 1, 0)
__versionstr__ = '.'.join(str(i) for i in __version__)



class MigratesFailState(object):
    """Enumerates constants recognized by the `handle_migration_failure` method."""
    
    # Counter for assigning unique IDs to failure states.
    id_counter = 0
    
    def __init__(self, message):
        self.message = message
        self.id = MigratesFailState.id_counter
        MigratesFailState.id_counter += 1
    def __eq__(self, other):
        return self.id == other.id
    def __hash__(self):
        return hash(self.id)
    
# All the recognized failure states.
MigratesFailState.GetMigrations = MigratesFailState(
    'Encountered unhandled error while getting pending migrations.'
)
MigratesFailState.GetTemplates = MigratesFailState(
    'Encountered unhandled error while retrieving templates'
)
MigratesFailState.BackupTemplates = MigratesFailState(
    'Encountered unhandled error while backing up template data.'
)
MigratesFailState.PendingMigrations = MigratesFailState(
    'Encountered unhandled error while recording pending migrations.'
)
MigratesFailState.GetAffected = MigratesFailState(
    'Encountered unhandled error while getting affected indexes.'
)
MigratesFailState.TransformTemplates = MigratesFailState(
    'Encountered unhandled error while transforming templates.'
)
MigratesFailState.CreateDummies = MigratesFailState(
    'Encountered unhandled error while creating dummy indexes.'
)
MigratesFailState.PersistTemplates = MigratesFailState(
    'Encountered unhandled error while persisting templates.'
)
MigratesFailState.MigrateDocuments = MigratesFailState(
    'Encountered unhandled error while migrating documents.'
)
MigratesFailState.WriteHistory = MigratesFailState(
    'Encountered unhandled error while recording migration history.'
)

# Failure states which occurred before any Elasticsearch data was
# actually modified; no recovery action is necessary.
MigratesFailState.NoRecoveryNeeded = (
    MigratesFailState.GetMigrations,
    MigratesFailState.GetTemplates,
    MigratesFailState.BackupTemplates,
    MigratesFailState.PendingMigrations,
    MigratesFailState.GetAffected,
    MigratesFailState.TransformTemplates,
)



class Migrates(object):
    """
    Contains a registry of known migrations and implements the migration process.
    """
    
    FailState = MigratesFailState
    IndexDetail = MigratesIndexDetail
    
    registry = {}  # Will contain Migration objects
    
    default_history_template = 'migrates_history_template'
    default_history_index = 'migrates_history'
    default_history_doc_type = 'migration'
    default_dummy_index_prefix = 'migrates_dummy_'
    
    # Commonly-used query for scanning the complete contents of an index
    scan_query = {"query": {"match_all": {}}, "sort": ["_doc"]}
    
    @classmethod
    def add(cls, migration):
        """Add a Migration object to the registry."""
        if migration.name in cls.registry:
            raise KeyError(
                'Migration names must be unique. (Encountered duplicate '
                'name "%s").' % migration.name
            )
        elif '/' in migration.name and not migration.internal:
            raise KeyError(
                'Migration names must not contain forward slashes (\'/\').'
            )
        cls.registry[migration.name] = migration
    
    @classmethod
    def get(cls, name):
        """Get a Migration object from the registry by its name."""
        try:
            return cls.registry[name]
        except KeyError:
            raise ValueError('Found no migration with name "%s".' % name)
    
    @classmethod
    def register(cls, *args, **kwargs):
        """
        To be used as a decorator for registering some class as a migration.
        Passes through arguments to the Migration constructor.
        """
        def decorator(target):
            cls.add(Migration(target, *args, **kwargs))
            return target
        return decorator
    
    def __init__(
        self, connection=None, logger=None, dry=False, no_history=False,
        detail=None, keep_dummies=False, restore_path=None,
        history_template=default_history_template,
        history_index=default_history_index,
        history_doc_type=default_history_doc_type,
        dummy_index_prefix=default_dummy_index_prefix,
    ):
        # The Elasticsearch connection object used to interact with the API.
        self.connection = elasticsearch.Elasticsearch() if connection is None else connection
        # A Logger object used for outputting information about the migration process.
        self.logger = Logger() if logger is None else logger
        # Name of template to use for the migrates history index.
        self.history_template = history_template
        # Name of index in which to store migrates history.
        self.history_index = history_index
        # Document type for storing migrates history.
        self.history_doc_type = history_doc_type
        # A string to prefix intermediate "dummy" indexes with.
        self.dummy_index_prefix = dummy_index_prefix
        # Whether this is a dry run.
        self.dry = dry
        # When True, don't write migration history.
        self.no_history = no_history
        # Indexes to show an increased amount of detail when migrating.
        self.detail = detail
        # Whether to keep dummy indexes rather than cleaning them up afterwards.
        self.keep_dummies = keep_dummies
        # Path to write restore files to. (Files written to help recover from a failed migration.)
        self.restore_path = restore_path
        # Will be a set of index names affected by the migrations being evaluated.
        self.affected = None
        # Will represent settings and mappings for affected Elasticsearch indexes.
        self.settings = None
        # Will represent Elasticsearch templates prior to migration.
        self.original_templates = None
        # Will represent Elasticsearch templates after migration.
        self.updated_templates = None
        # Will represent the time at which migration was initiated.
        self.timestamp = datetime.datetime.utcnow()
        # Will represent a set of migration names which are to be processed.
        self.migrations = None
        # Paths to files recorded in case the information is needed for recovery.
        if restore_path is None:
            self.restore_templates_path = None
            self.restore_indexes_path = None
            self.restore_migrations_path = None
        else:
            path_date = self.timestamp.strftime('%Y%m%d%H%M%S')
            self.restore_templates_path = os.path.join(
                restore_path, 'migrates.templates.' + path_date + '.json'
            )
            self.restore_indexes_path = os.path.join(
                restore_path, 'migrates.indexes.' + path_date + '.json'
            )
            self.restore_migrations_path = os.path.join(
                restore_path, 'migrates.migrations.' + path_date + '.json'
            )
        # Will store Elasticsearch version information
        self.es_version = self.get_es_version()
        self.verbose('Found Elasticsearch version %s.', self.es_version)
    
    def get_es_version(self):
        response = self.connection.transport.perform_request(
            'GET', '/', params=None
        )
        try:
            return response[1]['version']['number']
        except KeyError:
            return response['version']['number']
    
    def batch(self, *args, **kwargs):
        """Get a batch object for handling bulk actions."""
        return Batch(self.connection, self.logger, *args, **kwargs)
    
    def log(self, text, *args):
        """Log a message."""
        self.logger.log(text, *args)
    
    def verbose(self, text, *args):
        """Log a message. (But only if the verbose flag was set.)"""
        self.logger.debug(text, *args)
    
    def log_exception(self, text, *args, **kwargs):
        """Log an exception."""
        self.logger.exception(text, *args, **kwargs)
    
    def error(self, text, *args):
        """Log an error message."""
        self.logger.error(text, *args)
    
    def important(self, text, *args):
        """Log an important message."""
        self.logger.important(text, *args)
        
    def wait(self, seconds=None):
        """
        Helper function to wait for some amount of time and report to stdout.
        When a number of seconds isn't explicitly provided, the function will
        wait an amount of time proportional to the number of indexes that are
        affected by the pending migrations.
        """
        if self.dry:
            return  # Don't wait during dry runs, that would be silly.
        if seconds is None:
            seconds = max(5, min(20, len(self.affected)))
        self.logger.wait(seconds)
    
    def get_dummy_index(self, index):
        """Given an index name, get the name of an intermediate "dummy" index."""
        return self.dummy_index_prefix + index
    
    def get_original_index(self, dummy):
        """Returns the input of `get_dummy_index` given its output."""
        if not dummy.startswith(self.dummy_index_prefix):
            raise ValueError('Index name "%s" does not belong to a dummy index.', dummy)
        return dummy[len(self.dummy_index_prefix):]
    
    @classmethod
    def match_pattern(cls, pattern, target):
        """
        Helper function used to match a string against an Elasticsearch-style
        pattern.
        """
        return re.match(cls.get_pattern_regex(pattern), target)
    
    @staticmethod
    def get_pattern_regex(pattern):
        """
        Helper function used to construct a regular expression from an
        Elasticsearch-style pattern.
        """
        return re.escape(pattern).replace('\\*', '.*') + '$'
    
    def get_performed_migrations(self):
        """Get a set of names of migrations that have already been performed."""
        try:
            migration_history = set(
                document['_source']['name']
                for document in eshelpers.scan(
                    client=self.connection,
                    preserve_order=True,
                    index=self.history_index,
                    doc_type=self.history_doc_type,
                    query=self.scan_query
                )
            )
            return migration_history
        except elasticsearch.exceptions.NotFoundError:
            # If the index doesn't exist, no migrations have been performed.
            return set()
    
    def get_pending_migrations(self):
        """
        Get all migrations awaiting execution from least to most recent, as
        determined by the migration history stored in Elasticsearch.
        """
        self.verbose('Getting pending migrations.')
        performed = self.get_performed_migrations()
        pending = [
            migration for migration in self.registry.values() if (
                migration.repeat or migration.name not in performed
            )
        ]
        pending.sort(key=lambda migration: migration.date)
        if not pending:
            self.log('Found no pending migrations.')
        else:
            self.log(
                'Found %s pending migrations: %s', len(pending),
                ', '.join(str(migration) for migration in pending)
            )
        return pending
    
    def get_keyword_field(self):
        """
        For Elasticsearch 5.x and later, return a "keyword" field mapping.
        For prior versions, return a "not_analyzed" "string" field mapping.
        """
        if self.es_version and int(self.es_version[0]) >= 5:
            return {"type": "keyword", "index": True}
        else:
            return {"type": "string", "index": "not_analyzed"}

    def enforce_history_template(self):
        """Make sure that the template used by migrates is present in ES."""
        if self.no_history:
            return
        self.verbose('Verifying that history template is present in Elasticsearch.')
        self.connection.indices.put_template(
            create=False,
            name=self.history_template,
            body={
                "template": self.history_index,
                "mappings": {
                    self.history_doc_type: {
                        "dynamic": False,
                        "properties": {
                            "timestamp": {"type": "date"},
                            "migration_date": {"type": "date"},
                            "name": self.get_keyword_field(),
                            "description": self.get_keyword_field(),
                            "internal": {"type": "boolean"}
                        }
                    }
                }
            }
        )

    def write_migration_history(self, migration_actions=None):
        """Write migration history information to Elasticsearch."""
        if self.no_history:
            return
        if migration_actions is None:
            migration_actions = [
                self.migration_action(migration) for migration in self.migrations
            ]
        try:
            self.log('Writing %s migration history entries.', len(migration_actions))
            self.enforce_history_template()
        except Exception:  # Not a fatal error
            self.log_exception('Failed to enforce existence of migrates history template.')
        if self.dry:
            return
        with self.batch() as batch:
            batch.update(migration_actions)
            
    def migration_action(self, migration):
        return {
            '_op_type': 'index',
            '_index': self.history_index,
            '_type': self.history_doc_type,
            '_id': migration.name + '/' + self.timestamp.strftime('%Y%m%d%H%M%S'),
            '_source': {
                'timestamp': self.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'migration_date': migration.date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'name': migration.name,
                'description': migration.description,
                'internal': migration.internal
            }
        }
    
    def write_original_templates(self):
        if self.restore_templates_path is None:
            self.verbose('Skipping writing original template data.')
            return
        self.log('Writing original template data to path "%s".', self.restore_templates_path)
        with open(self.restore_templates_path, 'w') as output_file:
            json.dump(self.original_templates, output_file)
    
    def write_affected_indexes(self):
        if self.restore_indexes_path is None:
            self.verbose('Skipping writing affected index information.')
            return
        self.log('Writing affected index information to path "%s".', self.restore_indexes_path)
        with open(self.restore_indexes_path, 'w') as output_file:
            json.dump(list(self.affected), output_file)
    
    def write_pending_migrations(self):
        if self.restore_migrations_path is None:
            self.verbose('Skipping writing migration information.')
            return
        self.log('Writing migration information to path "%s".', self.restore_migrations_path)
        migrations = [
            self.migration_action(migration) for migration in self.migrations
        ]
        with open(self.restore_migrations_path, 'w') as output_file:
            json.dump(migrations, output_file)
    
    def get_templates(self):
        """Get a dictionary of templates currently present in Elasticsearch."""
        self.verbose('Retrieving templates from Elasticsearch.')
        # The Python API doesn't seem to provide a nice wrapper for this
        # Also, depending on API version, this could be a dict or a tuple.
        result = self.connection.transport.perform_request(
            'GET', '/_template/', params=None
        )
        try:
            return result[1]
        except KeyError:
            return result
        
    def migrate(self, migrations=None):
        """
        This is were the action happens!
        Optionally accepts an iterable of migrations to be processed, otherwise
        registered migrations which are currently pending will be processed.
        """
        
        # Get migrations that should be applied.
        try:
            if migrations is None:
                self.migrations = self.get_pending_migrations()
            else:
                self.migrations = list(migrations)
        except BaseException as e:
            return self.handle_migration_failure(self.FailState.GetMigrations, e)
        
        # If there are no migrations to be applied, just bail now.
        if not migrations:
            return
        
        # Retrieve current Elasticsearch templates.
        try:
            self.original_templates = self.get_templates()
        except BaseException as e:
            return self.handle_migration_failure(self.FailState.GetTemplates, e)
        
        # Record original template information. Can be used to recover
        # Elasticsearch state if normal recovery fails.
        # If migration fails here: No recovery action is required.
        try:
            if not self.dry:
                self.write_original_templates()
        except BaseException as e:
            return self.handle_migration_failure(self.FailState.BackupTemplates, e)
        
        # Record information about the templates that are about to be performed.
        # Can be used to update migration history to correctly reflect current
        # state if normal history recording fails.
        # If migration fails here: No recovery action is required.
        try:
            if not self.dry:
                self.write_pending_migrations()
        except BaseException as e:
            return self.handle_migration_failure(self.FailState.PendingMigrations, e)
        
        # Get affected indexes and the settings and mappings of those indexes.
        # If migration fails here: No recovery action is required.
        try:
            self.affected = self.get_affected_indexes()
            if not self.dry:
                self.write_affected_indexes()
            if self.affected:
                self.log(
                    'Found %s affected indexes: %s', len(self.affected),
                    ', '.join('"%s"' % index for index in self.affected)
                )
            else:
                self.log('Found no affected indexes.')
            if not self.dry:
                self.settings = self.get_index_settings(self.affected)
        except BaseException as e:
            return self.handle_migration_failure(self.FailState.GetAffected, e)
        
        # Apply template transformations to the templates found in Elasticsearch.
        # If migration fails here: No recovery action is required.
        try:
            self.updated_templates = self.get_updated_templates()
        except BaseException as e:
            return self.handle_migration_failure(self.FailState.TransformTemplates, e)
        
        # Create and populate dummy indexes.
        # If migration fails here: Dummy indexes should be removed.
        try:
            if self.affected and not self.dry:
                self.create_dummy_indexes()
                self.wait()
                self.populate_dummy_indexes()
        except BaseException as e:
            return self.handle_migration_failure(self.FailState.CreateDummies, e)
            
        # Persist the transformed templates to Elasticsearch.
        # If migration fails here: Dummies should be removed and templates reverted.
        try:
            self.migrate_templates(self.original_templates, self.updated_templates)
        except BaseException as e:
            return self.handle_migration_failure(self.FailState.PersistTemplates, e)
        
        # Persist the transformed templates to Elasticsearch.
        # If migration fails here: Templates and indexes should be reverted,
        # dummies removed.
        try:
            if self.affected:
                if not self.dry:
                    self.remove_indexes(self.affected)
                self.wait()
                self.migrate_indexes()
        except BaseException as e:
            return self.handle_migration_failure(self.FailState.MigrateDocuments, e)
            
        # Remove dummy indexes since they are no longer needed.
        # If migration fails here: Report the error but continue on. Failure
        # to remove dummies warrants no recovery action.
        try:
            if not self.dry:
                self.remove_indexes([
                    self.get_dummy_index(index) for index in self.affected
                ])
        except BaseException:
            # Not a fatal error
            # TODO: Tell the user how to clean the dummies up
            self.log_exception('Failed to remove dummy indexes.')
        
        # Write migrates history information to Elasticsearch.
        # If migration fails here: No recovery action should be taken, but the
        # user should be notified about how to attempt to update migration
        # history information.
        try:
            if not self.dry:
                self.write_migration_history()
        except BaseException as e:
            return self.handle_migration_failure(self.FailState.WriteHistory, e)
        
        # All done! Report success status.
        if self.dry:
            self.log('Finished migration dry run.')
        else:
            self.log('Migration completed successfully!')

    def get_affected_indexes(self):
        """
        Get a set of index names that would be affected by running the given
        migrations. Whether an index will be affected is determined by whether
        any index transformation pattern represented in a dictionary returned
        by a migration's `transform_documents` method matches the index name.
        """
        self.verbose('Determining affected indexes.')
        transformations = Migration.merge_document_transformations(self.migrations)
        affected = set()  # Names of indexes affected by any transformation
        for pattern in transformations.keys():
            try:
                affected.update(self.connection.indices.get_settings(
                    index=pattern, params={'expand_wildcards': 'open,closed'}
                ))
            except elasticsearch.exceptions.NotFoundError:
                pass  # Index doesn't exist, and that's ok.
        if not self.affected:
            self.verbose('Found no affected indexes.')
        else:
            self.verbose(
                'Found %s affected indexes: %s',
                len(self.affected), ', '.join(self.affected)
            )
        return affected
    
    def get_index_settings(self, indexes, dummies=False):
        class Result(object):
            def __init__(self):
                self.mappings = {}
                self.settings = {}
            def __getitem__(self, index):
                return {
                    'mappings': self.mappings[index],
                    'settings': self.settings[index]
                }
        self.verbose('Retrieving index mappings and settings.')
        result = Result()
        for index in indexes:
            self.verbose('Retrieving settings for index "%s".', index)
            try:
                target = self.get_dummy_index(index) if dummies else index
                result.mappings[index] = self.connection.indices.get_mapping(
                    index=target
                )[target]['mappings']
                settings = self.connection.indices.get_settings(
                    index=target
                )[target]['settings']
                # Elasticsearch 5.x includes an "index.creation_date" field in
                # responses but does not accept the field for index creation.
                # Since that's what this data will be used for later, remove
                # the field now.
                if 'index' in settings and 'creation_date' in settings['index']:
                    del settings['index']
                result.settings[index] = settings
                    
            except elasticsearch.exceptions.NotFoundError:
                self.verbose('Could not get settings for nonexistent index "%s".', index)
        return result
    
    def create_dummy_indexes(self):
        """
        Create intermediate "dummy" indexes used during the migration process.
        The created indexes will have the same mappings and setttings as the
        indexes that their contents are to be copied from.
        """
        self.log('Creating dummy indexes.')
        for index in self.affected:
            dummy = self.get_dummy_index(index)
            if not self.connection.indices.exists(dummy):
                self.log('Creating dummy index "%s".', dummy)
            else:
                self.log('Deleting then recreating dummy index "%s".', dummy)
                if not self.dry:
                    self.connection.indices.delete(dummy)
            if not self.dry:
                self.connection.indices.create(
                    index=dummy, body=self.settings[index]
                )
        
    def populate_dummy_indexes(self):
        """
        Copy documents from their original affected indexes into their
        corresponding dummy indexes.
        """
        self.log('Populating dummy indexes.')
        with self.batch() as batch:
            for index in self.affected:
                dummy = self.get_dummy_index(index)
                self.log(
                    'Populating dummy index "%s" with documents from "%s".',
                    index, dummy
                )
                if self.dry:
                    continue
                batch.update(
                    {
                        '_op_type': 'index',
                        '_index': dummy,
                        '_type': document['_type'],
                        '_id': document['_id'],
                        '_source': document['_source']
                    }
                    for document in eshelpers.scan(
                        client=self.connection,
                        preserve_order=True,
                        index=index, doc_type="*",
                        query=self.scan_query
                    )
                )
                
    def remove_dummy_indexes(self):
        if self.keep_dummies:
            self.verbose('Keeping dummy indexes.')
        else:
            self.log('Removing %s dummy indexes.', len(self.affected))
            try:
                self.remove_indexes([
                    self.get_dummy_index(index) for index in self.affected
                ])
            except Exception:
                self.log_exception('Failed to remove dummy indexes.')

    def remove_indexes(self, indexes):
        """Remove all index names given in an iterable."""
        self.verbose('Removing %s indexes.', len(indexes))
        for index in indexes:
            self.log('Removing index "%s".', index)
            try:
                if not self.dry:
                    self.connection.indices.delete(index=index)
            except elasticsearch.exceptions.NotFoundError:
                self.verbose('Failed to remove nonexistent index "%s".', index)

    def get_updated_templates(self):
        """
        Applies the pending migrations' template transformations to the original
        templates present in Elasticsearch prior to migration and returns the
        resulting dictionary.
        """
        self.verbose('Transforming templates with %s migrations.', len(self.migrations))
        updated = copy.deepcopy(self.original_templates)
        for migration in self.migrations:
            self.verbose('Transforming template with migration "%s".', migration)
            updated = migration.transform_templates(updated)
            if updated is None:
                raise ValueError('Template transformations must return a dictionary.')
        return updated
    
    def migrate_templates(self, original, updated):
        """
        Given a description of the templates present in Elasticsearch before
        migration, update templates to reflect those given by the `updated`
        dictionary.
        """
        def template_detail(name):
            return self.detail and any(
                self.match_pattern(pattern, name) for pattern in self.detail
            )
        self.log('Writing migrated templates.')
        unchanged = set()
        any_changes = False
        for name, body in original.items():
            if not(name in updated and body == updated[name]):
                any_changes = True
                if name not in updated:
                    self.log('Removing deleted template "%s".', name)
                else:
                    self.log('Removing changed template "%s".', name)
                    if template_detail(name):
                        self.log('Original template "%s":\n%s', name, body)
                        self.log('Updated template "%s":\n%s', name, updated[name])
                if not self.dry:
                    self.connection.indices.delete_template(name=name)
            else:
                self.verbose('Found unchanged template "%s".', name)
                unchanged.add(name)
        for name, body in updated.items():
            if name not in unchanged:
                any_changes = True
                if name in original:
                    self.log('Adding changed template "%s".', name)
                else:
                    self.log('Adding new template "%s".', name)
                if not self.dry:
                    self.connection.indices.put_template(
                        name=name, body=body, create=True
                    )
        if not any_changes:
            self.log('No templates were affected.')

    @staticmethod
    def validate_transformed_document(document, add_op_type):
        """Helper function used when migrating Elasticsearch documents."""
        if '_index' not in document:
            raise ValueError('Document must have an "_index" attribute.')
        elif '_type' not in document:
            raise ValueError('Document must have a "_type" attribute.')
        elif '_source' not in document:
            raise ValueError('Document must have a "_source" attribute.')
        if add_op_type and '_op_type' not in document:
            document['_op_type'] = 'index'
        return document
    
    def migrate_indexes(self):
        # TODO: Handle transformations returning more than one document
        detail = self.IndexDetail(detail=self.detail, logger=self.logger)
        with self.batch() as batch:
            for index in self.affected:
                self.log('Transforming documents in index "%s".', index)
                for document in eshelpers.scan(
                    client=self.connection,
                    preserve_order=True,
                    index=index if self.dry else self.get_dummy_index(index),
                    doc_type="*",
                    query=self.scan_query
                ):
                    if not self.dry:
                        document['_index'] = self.get_original_index(document['_index'])
                    detail.pre(document)
                    for migration in self.migrations:
                        detail.touch(migration)
                        try:
                            document = migration.transform_document(document)
                        except Exception as e:
                            detail.error(migration, e)
                            if self.dry:
                                break
                            else:
                                raise e
                        if document is None:  # Returning None removes the document
                            detail.delete(migration)
                            break
                    detail.post(document)
                    if document is not None and not self.dry:
                        batch.add(self.validate_transformed_document(
                            document, add_op_type=True
                        ))
        detail.report()
    
    def handle_migration_failure(self, state, exception):
        self.log_exception(state.message, exception=exception)
        if self.dry:
            self.log(
                'Migration dry run failed; '
                'Elasticsearch data was not modified.'
            )
        elif state in self.FailState.NoRecoveryNeeded:
            self.log(
                'Elasticsearch data was not modified, '
                'and no recovery action is necessary.'
            )
        elif state is self.FailState.CreateDummies:
            self.log(
                'Existing Elasticsearch data was not modified, though dummy '
                'indexes may have been created.'
            )
            if not self.keep_dummies:
                self.log(
                    'Please do not terminate the process before recovery is complete.'
                )
            self.remove_dummy_indexes()
            self.log('Recovery complete.')
        elif state is self.FailState.PersistTemplates:
            self.log(
                'Elasticsearch templates may have been modified and '
                'dummy indexes may have been created.'
            )
            self.log(
                'Please do not terminate the process before recovery is complete.'
            )
            self.remove_dummy_indexes()
            self.revert_template_migration()
            self.log('Recovery complete.')
        elif state is self.FailState.MigrateDocuments:
            self.log(
                'Elasticsearch templates and indexes may have been modified '
                'and dummy indexes may have been created.'
            )
            self.log(
                'Please do not terminate the process before recovery is complete.'
            )
            self.revert_template_migration()
            self.revert_indexes_migration()
            self.log('Recovery complete.')
        elif state is self.FailState.WriteHistory:
            self.log('No recovery action will be taken.')
            self.important(
                'Run `migrates restore_history "%s"` to attempt recording '
                'migration history again.',
                os.path.abspath(self.restore_migrations_path)
            )
        else:
            self.log('No recovery action will be taken.')
    
    def revert_indexes_migration(self):
        try:
            self.log('Reverting changes made to Elasticsearch indexes and documents.')
            for index in self.affected:
                if self.connection.indices.exists(index=self.get_dummy_index(index)):
                    self.log('Recreating affected index "%s".', index)
                    if not self.dry:
                        if self.connection.indices.exists(index=index):
                            self.connection.indices.delete(index=index)
                        self.connection.indices.create(
                            index=index, body=self.settings[index]
                        )
                else:
                    self.error('No dummy exists for affected index "%s".', index)
                    self.error('Documents cannot be recovered if the dummy does not exist!')
            self.wait()
            with self.batch() as batch:
                for index in self.affected:
                    dummy = self.get_dummy_index(index)
                    if not self.connection.indices.exists(index=dummy):
                        continue
                    self.log(
                        'Copying documents from dummy index "%s" to original '
                        'index "%s".', dummy, index
                    )
                    if self.dry:
                        continue
                    batch.update(
                        {
                            '_op_type': 'index',
                            '_index': index,
                            '_type': document['_type'],
                            '_id': document['_id'],
                            '_source': document['_source']
                        }
                        for document in eshelpers.scan(
                            client=self.connection,
                            preserve_order=True,
                            index=dummy, doc_type="*",
                            query=self.scan_query
                        )
                    )
        except BaseException:
            self.log_exception(
                'Failed to recover data. The original documents should still '
                'exist, though located in indexes prefixed with "%s".',
                self.dummy_index_prefix
            )
            self.important(
                'Run `migrates restore_indexes "%s"` to attempt index recovery '
                'again.', os.path.abspath(self.restore_indexes_path)
            )
        else:
            self.remove_dummy_indexes()
    
    def revert_template_migration(self):
        """
        Revert changes made to templates in Elasticsearch during migration.
        If that fails, dump the original template data to a json file.
        If that fails, dump the template data to stdout.
        If even that fails, the user is sadly shit out of luck.
        """
        if self.updated_templates == self.original_templates:
            self.log('Migration made no changes to templates; nothing to revert.')
            return
        self.log('Reverting changes to Elasticsearch templates.')
        try:
            self.migrate_templates(
                original=self.updated_templates, updated=self.original_templates
            )
        except BaseException:
            self.log_exception('Failed to revert templates.')
            self.important(
                'Run `migrates restore_templates "%s"` to attempt template '
                'recovery again.', os.path.abspath(self.restore_templates_path)
            )



class Migration(object):
    """
    Represents a migration which may be evaluated as part of the migration
    process implemented by a Migrates object.
    """
    
    # Minimum representable datetime.
    # Year is 1900 for compatibility with strftime.
    min_date = datetime.datetime(year=1900, month=1, day=1)
    
    def __init__(self, target, name, date, description=None, repeat=False, internal=False):
        """
        Create a Migration object. This constructor is used when registering
        migrations with, for example, the `@Migrates.register` class decorator.
        `target` refers to a class representing a migration. Typically, this
        class should have a `transform_documents` function, a `transform_templates`
        function, or both.
        `name` must be a unique identifying string for the migration. An error
        will be produced when attempting to register migrations with overlapping
        names.
        `date` should either be a datetime.datetime object or a date string of the
        format %Y-%m-%d. Migration scripts with less recent dates are run before
        scripts with more recent dates.
        `description` is an optional string describing the purpose of the
        migration.
        `repeat` is an optional boolean specifying whether the migration should
        be considered pending regardless of whether migrates history shows that
        a migration with that name has been executed before.
        `internal` indicates that the target object was generated by migrates
        rather than loaded from user code. Migrations marked as internal may be
        subject to different requirements from user migrations.
        """
        self.target = target
        self.repeat = repeat
        self.internal = internal
        if name is None:
            self.name = target.__class__.__name__
        else:
            self.name = name
        if date is None and hasattr(target, 'date'):
            date = target.date
        if isinstance(date, datetime.datetime):
            self.date = date
        else:
            self.date = datetime.datetime.strptime(date, '%Y-%m-%d')
        if self.date < self.min_date:
            raise ValueError('Migration date must be at least 1900-01-01.')
        if description is None and hasattr(target, 'description'):
            self.description = target.description
        else:
            self.description = description
    
    @classmethod
    def reindex(cls, index, target=None):
        """
        Get a Migration object for reindexing the data in some index without
        modifying it.
        """
        if target is None:
            return cls(
                name='migrates/reindex/%s' % index,
                description='Reindex "%s".' % index,
                date=cls.min_date, repeat=True, internal=True,
                target=type('migration', (object,), {
                    'transform_documents': staticmethod(
                        lambda: {index: {'*': lambda doc: doc}}
                    )
                }),
            )
        else:
            def transform(document):
                document['_index'] = target
                return document
            return cls(
                name='migrates/reindex/%s/%s' % (index, target),
                description='Reindex "%s" to "%s".' % (index, target),
                date=cls.min_date, repeat=True, internal=True,
                target=type('migration', (object,), {
                    'transform_documents': staticmethod(
                        lambda: {index: {'*': transform}}
                    )
                }),
            )
    
    @classmethod
    def set_templates(cls, templates):
        """Get a Migration object for setting templates to a given state."""
        return cls(
            name='migrates/set_templates',
            description='Set template data.',
            date=cls.min_date, repeat=True, internal=True,
            target=type('migration', (object,), {
                'transform_templates': staticmethod(
                    lambda _: templates
                )
            }),
        )

    def __eq__(self, other):
        return self.name == other.name
    def __hash__(self):
        return hash(self.name)
    def __str__(self):
        return self.name

    def transform_document(self, document):
        """
        If this migration has any transformation functions applying to the given
        document's index and doc type, apply the transformation and return the
        result. Otherwise, just return back the original document.
        """
        transform = self.get_document_transform(document)
        return transform(document)
    
    def get_document_transform(self, document):
        """
        Get the migration's transformation function applying to a given document,
        judging by its index and document type.
        If the Migration object does not explicitly define any applicable
        transformation function, a function which simply returns its argument
        is returned.
        If the object defines more than one applicable transformation function,
        then an error is produced because this is considered an ambiguity.
        """
        transform_map = self.transform_documents()
        index_keys = [
            index for index in transform_map
            if Migrates.match_pattern(index, document['_index'])
        ]
        if len(index_keys) > 1:
            raise ValueError(
                'Migration "{0}" attempted to apply multiple transformations to a '
                'single index, but because the order of these transformations cannot '
                'be guaranteed this operation is not allowed. The matching index '
                'keys were {2}.'.format(self.name, index_keys)
            )
        elif index_keys:
            index_key = index_keys[0]
            doc_type = document['_type']
            doc_type_keys = [
                doc_type for doc_type in transform_map[index_key]
                if Migrates.match_pattern(doc_type, document['_type'])
            ]
            if len(doc_type_keys) > 1:
                raise ValueError(
                    'Migration "{0}" attempted to apply multiple transformations to a '
                    'single document type, but because the order of these transformations cannot '
                    'be guaranteed this operation is not allowed. The matching document type '
                    'keys were {2}.'.format(self.name, doc_type_keys)
                )
            elif doc_type_keys:
                doc_type_key = doc_type_keys[0]
                return transform_map[index_key][doc_type_key]
        return lambda doc: doc
    
    @staticmethod
    def merge_document_transformations(migrations):
        """
        Get one big dictionary indicating all the indexes and document types
        that are affected by the document transformations defined by some
        iterable of Migration objects.
        """
        transformations = collections.defaultdict(lambda: collections.defaultdict(list))
        for migration in migrations:
            transform = migration.transform_documents()
            for index in transform:
                for doc_type in transform[index]:
                    transformations[index][doc_type].append(transform[index][doc_type])
        return transformations

    def transform_documents(self):
        """
        Get a dictionary indicating transformations which should be applied to
        Elasticsearch documents, as defined by the value of a registered
        migration's `transform_documents` dictionary member.
        The transformation functions are allowed to modify the dictionary
        passed to them, but they must still return the modified dictionary.
        When a transformation function returns None, it indicates that the
        received document should be removed from Elasticsearch.
        """
        if hasattr(self.target, 'transform_documents'):
            return self.target.transform_documents()
        else:
            return {}

    def transform_templates(self, templates):
        """
        Get the result of transforming Elasticsearch template data according
        to the `transform_templates` method defined by a registered migration,
        if any.
        The transformation functions are allowed to modify the dictionary
        passed to them, but they must still return the modified dictionary.
        If the function returns None, an error will be produced.
        """
        if hasattr(self.target, 'transform_templates'):
            return self.target.transform_templates(templates)
        else:
            return templates



# Also put the registration decorator in the global mainspace, for convenience
# in writing and registering user migrations.
register = Migrates.register
