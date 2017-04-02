"""
This module implements a command-line interface for migrates.
"""

import os, sys, imp, datetime, argparse, re, json, logging
import elasticsearch

import usage
import migrates
from logger import Logger



def truncate(text, length):
    """Helper function for truncating a string."""
    if text and len(text) > length:
        return text[:length - 3] + '...'
    else:
        return text

def truncate_description(text, length):
    return truncate(text if text else '(No description.)', length)



class Arguments(object):
    # Format for logged dates.
    date_format = '%Y-%m-%dT%H:%M:%SZ'

    def __init__(self, path, command, args, options):
        # Path to the script
        self.path = path
        # The command to run, e.g. "migrates [run]"
        self.command = command
        # Command-specific arguments, e.g. "migrates run [my migrations]"
        self.args = args
        # Trailing options and flags, e.g. "migrates run [--dry]"
        self.options = options
        # Persistent Elasticsearch instance.
        self.connection = None
        # Persistent Logger instance.
        self.logger = None
        # Make Elasticsearch logger quieter
        logging.getLogger('elasticsearch').setLevel(logging.CRITICAL)
    
    def get_connection(self):
        if self.connection is None:
            logger = self.get_logger()
            if not self.options.host:
                self.connection = elasticsearch.Elasticsearch()
                logger.log('Acquired connection to local Elasticsearch host.')
            else:
                self.connection = elasticsearch.Elasticsearch(self.options.host)
                logger.log('Acquired connection to Elasticsearch host%s %s.',
                    '' if len(self.options.host) == 1 else 's',
                    ', '.join(self.options.host)
                )
        return self.connection
    
    def get_logger(self):
        if self.logger is None:
            self.logger = Logger(
                path=self.options.log,
                verbose=self.options.verbose,
                yes=self.options.yes or self.options.dry
            )
        return self.logger
    
    def get_migrates(self):
        """Get a Migrates instance given the options described by this object."""
        return migrates.Migrates(
            connection=self.get_connection(),
            logger=self.get_logger(),
            dry=self.options.dry,
            detail=self.options.detail,
            keep_dummies=self.options.keep_dummies,
            restore_path=self.options.restore_path,
            history_template=self.options.history_template,
            history_index=self.options.history_index,
            history_doc_type=self.options.history_doc_type,
            dummy_index_prefix=self.options.dummy_index_prefix,
        )
    
    def import_paths(self):
        """
        Import Python packages presumably including migrations from the paths
        specified. Returns True if all imports were successful and False if
        any of them failed. (The function bails after the first failure.)
        """
        logger = self.get_logger()
        if self.options.path:
            logger.debug('Importing %s paths.', len(self.options.path))
        else:
            logger.debug('No migration package paths specified.')
            return True
        for i, path in enumerate(self.options.path):
            logger.debug('Importing path "%s".', path)
            if not os.path.exists(path):
                logger.log('Nonexistent migration package path "%s".', path)
                return False
            if path.endswith('.py'):
                module_path = path
            else:
                module_path = os.path.join(path, '__init__.py')
                if not os.path.exists(module_path):
                    logger.log('Migration directory "%s" is not a Python module or package.', path)
                    logger.log('Paths must refer to Python files or directories containing an "__init__.py".')
                    return False
            with open(module_path, 'U') as module_file:
                imp.load_module(
                    'migrates.imported_package%s' % i,
                    module_file, module_path, ('.py', 'U', imp.PY_SOURCE)
                )
        return True
    
    @classmethod
    def parse(cls, args=None, path=None):
        args = sys.argv[1:] if args is None else args
        path = sys.argv[0] if path is None else path
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                break
            else:
                i += 1
        command_args = args[:i]
        command = command_args[0] if command_args else None
        options_args = args[i:]
        options = cls.options_parser(command).parse_args(options_args)
        if not options.restore_path:
            options.restore_path = os.path.join(os.path.dirname(path), 'restore')
            if not os.path.exists(options.restore_path):
                os.mkdir(options.restore_path)
        return cls(path, command, command_args[1:i], options)
    
    @staticmethod
    def options_parser(command=None):
        parser = argparse.ArgumentParser(usage=usage.general, add_help=False)
        # General options
        parser.add_argument('-p', '--path', type=str, nargs='+')
        parser.add_argument('-h', '--host', type=str, nargs='+')
        parser.add_argument('-l', '--detail', type=str, nargs='+')
        parser.add_argument('-d', '--dry', action='store_true')
        parser.add_argument('-k', '--keep-dummies', action='store_true')
        parser.add_argument('-r', '--restore-path', type=str, default='')
        parser.add_argument('-y', '--yes', action='store_true')
        parser.add_argument('-v', '--verbose', action='store_true')
        parser.add_argument('-V', '--version', action='store_true')
        parser.add_argument('--log', type=str, default='')
        # Advanced options
        parser.add_argument('--history-template', type=str,
            default=migrates.Migrates.default_history_template
        )
        parser.add_argument('--history-index', type=str,
            default=migrates.Migrates.default_history_index
        )
        parser.add_argument('--history-doc-type', type=str,
            default=migrates.Migrates.default_history_doc_type
        )
        parser.add_argument('--dummy-index-prefix', type=str,
            default=migrates.Migrates.default_dummy_index_prefix
        )
        # Command-specific options
        if command == 'migrations':
            parser.add_argument('--pending', action='store_true')
        elif command == 'restore_cleanup':
            parser.add_argument('--older-than', type=str, default='')
            parser.add_argument('--keep-files', type=int, default=4)
        return parser
    
    @staticmethod
    def parse_timestamp(timestamp):
        return datetime.datetime.strptime(timestamp,
            '%Y-%m-%dT%H:%M:%SZ' if timestamp.endswith('Z') else '%Y-%m-%d'
        )
    
    def enforce_command_args(self, min_args, max_args=None):
        if (
            (max_args is None and len(self.args) != min_args) or
            max_args is not None and (
                len(self.args) < min_args or len(self.args) > max_args
            )
        ):
            self.get_logger().log('Invalid number of command arguments.')
            print(usage.commands[self.command])
            return False
        else:
            return True



def __main__(args=None):
    if args is None:
        args = Arguments.parse()
    if args.options.version:
        version(args)
    elif args.command is None or args.command not in commands:
        print(usage.general)
    else:
        commands[args.command](args)



def show_help(args):
    if len(args.args) == 0:
        print(usage.general)
    elif len(args.args) >= 1:
        if args.args[0] in usage.commands:
            print(usage.commands[args.args[0]])
        else:
            print('Unknown command "%s".' % args.args[0])
            print(usage.help)



def version(args):
    logger = args.get_logger()
    logger.log(
        'Running migrates version %s from path "%s".',
        '.'.join(str(v) for v in migrates.__version__),
        os.path.abspath(args.path)
    )



def run(args):
    logger = args.get_logger()
    if not args.import_paths():
        return
    mig = args.get_migrates()
    if args.args:
        migrations = [migrates.Migrates.get(name) for name in args.args]
        kind = 'specified'
    else:
        migrations = mig.get_pending_migrations()
        kind = 'pending'
    if migrations and not logger.confirm('Run %s %s migrations?', len(migrations), kind):
        logger.log('Exiting without running migrations.')
        return
    mig.migrate(migrations)



def reindex(args):
    logger = args.get_logger()
    if not args.args:
        logger.log('Nothing to reindex.')
        return
    mig = args.get_migrates()
    migrations = []
    for index in args.args:
        target = None
        if '=>' in index:
            index, target = index.split('=>')
            index.strip()
            target.strip()
            logger.log('Reindexing documents from "%s" to "%s".', index, target)
        else:
            logger.log('Reindexing documents in index "%s".', index)
        migration = migrates.Migration.reindex(index, target)
        migrations.append(migration)
        mig.add(migration)
    if not logger.confirm('Proceed with %s reindex actions?', len(migrations)):
        logger.log('Exiting without reindexing.')
        return
    mig.migrate(migrations)
    logger.log('Finished reindexing.')



def show_history(args):
    if not args.enforce_command_args(0, 2):
        return
    logger = args.get_logger()
    es_filter = None
    if not args.args:
        es_filter = {'match_all': {}}
        logger.log('Showing migration history from the dawn of time.')
    else:
        begin = args.parse_timestamp(args.args[0])
        range_filter = {'gte': begin}
        if len(args.args) > 1:
            end = args.parse_timestamp(args.args[1])
            range_filter['lte'] = end
            logger.log('Showing migration history from %s to %s UTC.',
                begin.strftime(args.date_format), end.strftime(args.date_format)
            )
        else:
            logger.log('Showing migration history from %s UTC and onward.',
                begin.strftime(args.date_format)
            )
        es_filter = {'range': {'timestamp': range_filter}}
    try:
        any_history = False
        for document in elasticsearch.helpers.scan(
            client=args.get_connection(),
            index=args.options.history_index,
            doc_type=args.options.history_doc_type,
            preserve_order=True,
            query={
                'filter': es_filter,
                'sort': [
                    {'timestamp': {'order': 'asc'}},
                    {'migration_date': {'order': 'asc'}}
                ]
            }
        ):
            any_history = True
            timestamp = datetime.datetime.strptime(  # e.g. "2017-04-01T13:18:59.850701"
                document['_source']['timestamp'][:19], '%Y-%m-%dT%H:%M:%S'
            )
            logger.log('%s: "%s", %s',
                timestamp.strftime(args.date_format), document['_source']['name'],
                truncate_description(document['_source']['description'], 60)
            )
        if not any_history:
            logger.log('No migration history for this time period.')
    except elasticsearch.exceptions.NotFoundError:
        logger.log('No migration history index is present in Elasticsearch.')



def show_migrations(args):
    if (not args.enforce_command_args(0)) or (not args.import_paths()):
        return
    logger = args.get_logger()
    if args.options.pending:
        logger.log('Showing pending registered migrations.')
        migrations = args.get_migrates().get_pending_migrations()
    else:
        logger.log('Showing all registered migrations.')
        migrations = [migration for migration in migrates.Migrates.registry.values()]
        migrations.sort(key=lambda migration: migration.date)
    if migrations:
        for migration in migrations:
            logger.log('%s: "%s", %s',
                migration.date.strftime(args.date_format), migration.name,
                truncate_description(migration.description, 60)
            )
    else:
        logger.log('No registered migrations to show.')



def restore_templates(args):
    if not args.enforce_command_args(1):
        return
    logger = args.get_logger()
    path = args.args[0]
    with open(path, 'rb') as restore_file:
        templates = json.load(restore_file)
    if not logger.confirm('Set templates to those loaded from "%s"?', path):
        logger.log('Exiting without modifying data.')
        return
    migration = migrates.Migration.set_templates(templates)
    mig = args.get_migrates()
    mig.migrate([migration])
    logger.log('Finished restoring templates.')



def restore_indexes(args):
    if not args.enforce_command_args(1):
        return
    logger = args.get_logger()
    path = args.args[0]
    with open(path, 'rb') as restore_file:
        affected = list(json.load(restore_file))
    logger.log(
        'Found %s affected indexes: %s', len(affected),
        ', '.join('"%s"' % index for index in affected)
    )
    if not logger.confirm(
        'Restore %s affected indexes loaded from "%s"?', len(affected), path
    ):
        logger.log('Exiting without modifying data.')
        return
    mig = args.get_migrates()
    mig.affected = affected
    mig.settings = mig.get_index_settings(affected, dummies=True)
    mig.revert_indexes_migration()
    logger.log('Finished restoring indexes.')



def restore_history(args):
    if not args.enforce_command_args(1):
        return
    logger = args.get_logger()
    path = args.args[0]
    with open(path, 'rb') as restore_file:
        history = list(json.load(restore_file))
    if not logger.confirm('Write %s migration history entries from "%s"?',
        len(history), path
    ):
        logger.log('Exiting without modifying data.')
        return
    mig = args.get_migrates()
    mig.write_migration_history(migration_actions=history)
    logger.log('Finished restoring migration history.')



def restore_cleanup(args):
    logger = args.get_logger()
    older_than = None
    yes = False
    def cleanup_file(path):
        if args.options.dry:
            logger.log('File "%s" would be removed.', path)
        else:
            logger.debug('Removing file "%s".', path)
            os.remove(path)
    if args.options.older_than:
        older_than = args.parse_timestamp(args.options.older_than)
        yes = logger.confirm('Remove recovery files older than %s?',
            older_than.strftime(args.date_format)
        )
    else:
        yes = logger.confirm('Remove recovery files made since the beginning of time?')
    if not yes:
        logger.log('Exiting without removing recovery files.')
        return
    old_files = {
        'indexes': [],
        'templates': [],
        'migrations': [],
    }
    not_old = {
        'indexes': 0,
        'templates': 0,
        'migrations': 0,
    }
    pattern = r'migrates\.(indexes|templates|migrations)\.(\d{14})\.json'
    for name in os.listdir(args.options.restore_path):
        path = os.path.join(args.options.restore_path, name)
        if os.path.isfile(path):
            match = re.match(pattern, name)
            if match:
                timestamp = datetime.datetime.strptime(match.group(2), '%Y%m%d%H%M%S')
                if not older_than or timestamp < older_than:
                    old_files[match.group(1)].append(path)
                else:
                    not_old[match.group(1)] += 1
    for key in old_files:
        if not_old[key] < args.options.keep_files:
            old_files[key].sort(reverse=True)
            old_files[key] = old_files[key][(args.options.keep_files - not_old[key]):]
        logger.log('Removing %s "%s" recovery files.', len(old_files[key]), key)
        for path in old_files[key]:
            cleanup_file(path)
    logger.log('Finished cleaning up recovery files.')



def remove_history(args):
    if not args.enforce_command_args(0):
        return
    logger = args.get_logger()
    connection = args.get_connection()
    history = args.options.history_index
    if args.options.dry:
        logger.log('Previewing migration history removal.')
    if not logger.confirm('Remove migration history index "%s"?', history):
        logger.log('Exiting without removing migration history.')
        return
    if connection.indices.exists(history):
        logger.log('Removing migration history index "%s".', history)
        if not args.options.dry:
            connection.indices.delete(history)
    else:
        logger.log('Migration history "%s" does not exist.', history)
    logger.log('Finished removing migration history.')
    


def remove_dummies(args):
    if not args.enforce_command_args(0):
        return
    logger = args.get_logger()
    if args.options.dry:
        logger.log('Previewing dummy index removal.')
    connection = args.get_connection()
    dummy_pattern = args.options.dummy_index_prefix + '*'
    dummies = connection.indices.get(index=dummy_pattern)
    if not dummies:
        logger.log('No dummy indexes to remove.')
        return
    if not logger.confirm('Remove all %s indexes prefixed with "%s"?',
        len(dummies), args.options.dummy_index_prefix
    ):
        logger.log('Exiting without removing dummy indexes.')
        return
    if args.options.dry:
        for dummy in dummies:
            logger.log('Would remove index "%s".', dummy)
        logger.log('Finished previewing dummy index removal.')
    else:
        connection.indices.delete(index=dummy_pattern)
        logger.log('Finished removing %s dummy indexes.', len(dummies))



commands = {
    'run': run,
    'reindex': reindex,
    'history': show_history,
    'migrations': show_migrations,
    'restore_templates': restore_templates,
    'restore_indexes': restore_indexes,
    'restore_history': restore_history,
    'restore_cleanup': restore_cleanup,
    'remove_history': remove_history,
    'remove_dummies': remove_dummies,
    'help': show_help,
}



if __name__ == '__main__':
    __main__()
