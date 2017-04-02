"""
This module is a depenency of migrates used to support showing extra detail for
indexes affected by migration.
"""

import traceback, copy, collections, json

# Use long integers for both Python 2 and 3
try:
    x = long(0)
except NameError:
    long = int

class MigratesIndexDetail(object):
    def __init__(self, detail, logger):
        self.detail = detail
        self.logger = logger
        self.index_touched = collections.defaultdict(long)
        self.index_deleted = collections.defaultdict(long)
        self.migration_touched = collections.defaultdict(long)
        self.migration_deleted = collections.defaultdict(long)
        self.migration_errors = collections.defaultdict(long)
        self.shown_doc_types = collections.defaultdict(set)
        self.document = None
        self.document_index = None
        self.document_type = None
        self.document_detail = False
        self.document_touched_by = set()
        self.document_deleted_by = None
        self.document_errored_by = None
        self.document_exceptions = collections.defaultdict(
            lambda: collections.defaultdict(list)
        )
    
    def pre(self, document):
        """
        To be called before applying migrations to a document.
        """
        self.document_index = document['_index']
        self.document_type = document['_type']
        self.index_touched[self.document_index] += 1
        if self.detail and self.document_type not in self.shown_doc_types[self.document_index]:
            self.document = copy.deepcopy(document)
            self.document_detail = True
    
    def touch(self, migration):
        """
        To be called for each migration touching a document.
        """
        if self.detail:
            self.document_touched_by.add(migration)
        self.migration_touched[migration] += 1
    
    def delete(self, migration):
        """
        To be called when a migration deletes a document.
        """
        self.document_deleted_by = migration
        self.index_deleted[self.document_index] += 1
        self.migration_deleted[migration] += 1
    
    def error(self, migration, exception):
        """
        To be called when a migration encounters an error handling a document.
        """
        self.document_errored_by = migration
        self.migration_errors[migration] += 1
        self.document_exceptions[self.document_index][self.document_type].append(exception)
    
    def post(self, document):
        """
        To be called after migrations have been applied to a document.
        """
        if not self.document_detail:
            return
        document_name = '/'.join((
            self.document['_index'], self.document['_type'], self.document['_id']
        ))
        self.logger.log(
            'Document "%s" was touched by %s migrations: %s.',
            document_name, len(self.document_touched_by),
            ', '.join(str(i) for i in self.document_touched_by)
        )
        if self.document_errored_by:
            self.logger.log(
                'Document produced an error with migration "%s".',
                self.document_deleted_by
            )
        elif self.document_deleted_by:
            self.logger.log(
                'Document was deleted by migration "%s".',
                self.document_deleted_by
            )
        else:
            post_document_name = '/'.join((
                document['_index'], document['_type'], document['_id']
            ))
            self.logger.log(
                'The original document %s:\n%s',
                document_name, json.dumps(self.document, indent=2)
            )
            self.logger.log(
                'The migrated document %s:\n%s',
                post_document_name, json.dumps(document, indent=2)
            )
        self.shown_doc_types[self.document_index].add(self.document_type)
        self.document = None
        self.document_index = None
        self.document_detail = False
        self.document_touched_by = set()
        self.document_deleted_by = None
        self.document_errored_by = None
    
    def report(self):
        # Sort by number of touched documents
        index_info = sorted(self.index_touched.items(), key=lambda i: -i[1])
        # Sort by migration date
        migration_info = sorted(self.migration_touched.items(), key=lambda i: i[0].date)
        # Sort by number of errors
        error_info = sorted(self.migration_errors.items(), key=lambda i: -i[1])
        # Now actually report all that info!
        for index, touched in index_info:
            self.logger.log('In index "%s": %s documents touched, %s documents deleted.',
                index, touched, self.index_deleted[index]
            )
        for migration, touched in migration_info:
            self.logger.log('Migration "%s": %s documents touched, %s documents deleted.',
                migration, touched, self.migration_deleted[migration]
            )
        for migration, errors in error_info:
            self.logger.error('Migration "%s" produced %s errors out of %s touched documents!',
                migration, errors, self.migration_touched[migration]
            )
        # Also report exceptions that were encountered.
        for index in self.document_exceptions:
            for doc_type in self.document_exceptions[index]:
                exceptions = self.document_exceptions[index][doc_type]
                self.logger.error(
                    'Encountered %s exceptions for documents in "%s/%s", including:',
                    len(exceptions), index, doc_type
                )
                self.logger.log(
                    '\n'.join(traceback.format_exc(e) for e in exceptions[:3])
                )
