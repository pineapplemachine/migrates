"""
This module documents migrates' command-line interface.
"""

general_options = """
    -p, --path <paths...>
        Designate one or more paths to Python package directories to be
        imported. The packages should implement and register migrations
        recognized by migrates, for example using the "@migrates.register"
        class decorator.
    -h, --host <hosts...>
        Designate one or more Elasticsearch hosts. If none are given,
        defaults to "127.0.0.1:9200".
    -d, --dry
        Where changes would normally be made to data in Elasticsearch, a
        description of those changes is given and Elasticsearch data is
        not modified.
    -y, --yes
        Omit confirmation prompts and just go ahead with things.
    -v, --verbose
        Output more information than usual about what migrates is doing.
    -V, --version
        Display migrates version and exit.
    --log
        Path to a file to log output to."""

migration_options = """
    -l, --detail
        Specifies one or more index and template patterns that are of
        particular interest. When migration affects documents in an
        index whose name matches any pattern, or templates whose names
        match any pattern, extra information regarding action that was
        taken is outputted.
    -k, --keep-dummies
        Normally, as a part of index migration, intermediate "dummy"
        indexes are created to store a copy of the original data, and
        they are removed once the process has been completed successfully.
        This option indicates that dummy indexes should not be removed
        even after a successful migration or after recovery from a failed
        migration.
    -r, --restore-path
        Path to write files to that can be used to restore Elasticsearch
        state in case of a migration failure. Defaults to the directory
        that the migrates script is located in."""

general = """
Usage:
    migrates <command> <options...>

Examples:
    migrates run --host 192.0.2.10:9200 --path my/migrations/path
    migrates run my_migration_name --dry --path my/migrations/path
    migrates reindex "source_index=>destination_index"
    migrates history 2000-01-31 2000-02-29
    migrates migrations --path my/migrations/path
    migrates help
    migrates help run

Commands:
    run
        Run pending migrations, or run a specified list of migrations.
    reindex
        Reindex the documents in an index, either back into the same
        index or into a new one.
    history
        Show migration history, describing which migrations have been
        run and at what times.
    migrations
        Show information about registered migrations.
    restore_templates
        Get templates from a json file path then update Elasticsearch
        to contain the templates as described.
    restore_indexes
        Restore original Elasticsearch indexes from dummies created
        during a failed migration process, given information about the
        affected indexes described at a json file path.
    restore_history
        Load migration history from a json file path then write that
        history to Elasticsearch.
    restore_cleanup
        Every time migrates is run, recovery files are created to
        ensure that, if something breaks, data will still be
        recoverable. This command can be used to remove old recovery
        files.
    remove_history
        Remove migrates' migration history data from Elasticsearch.
    remove_dummies
        Intermediate "dummy" indexes are created during the migration
        process and may sometimes end up sticking around. This command
        removes any index in Elasticsearch that looks like one of
        migrates' dummy indexes.
    help
        Show this help text or, when an additional option is given, more
        detailed help for a command. For example, "migrates help run".

General Options: %s
""" % general_options

run = """
Usage:
    migrates run <migrations...> <options...>

Examples:
    migrates run --host 192.0.2.10:9200 --path my/migrations/path
    migrates run my_migration_name --dry --path my/migrations/path

Description:
    When a list of migration names is explicitly given, those migrations
    are run in the order they were provided.
    When no list of names is given, pending migrations are run. (Pending
    migrations include those which have been registered by the user but,
    according to the migration history found in Elasticsearch, have never
    been run.) Pending migrations are run in ascending timestamp order.

Migration Options: %s

General Options: %s
""" % (migration_options, general_options)

reindex = """
Usage:
    migrates reindex <indexes...> <options...>

Examples:
    migrates reindex my_index another_index
    migrates reindex "source_index=>destination_index"
    migrates reindex "index_prefix_*"
    migrates reindex my_index a_index=>b_index --host 192.0.2.10:9200 --dry

Description:
    Reindex the contents of an index or indexes, optionally to a different
    destination index than where the documents were originally located.
    This functionality can be used, for example, to update the settings
    and mappings of an index after changing a template which applies to it.
    When "=>" is present in an index option, it indicates that documents in
    the index on the left side should be reindexed into the index on the
    right side.
    When "=>" is not present, documents are reindexed back into the same
    index that they came from.

Migration Options: %s

General Options: %s
""" % (migration_options, general_options)

history = """
Usage:
    migrates history <begin_time> <end_time> <options...>

Examples:
    migrates history --host 192.0.2.10:9200
    migrates history 2012-01-01
    migrates history 2012-02-28T10:00:00Z 2012-04-01T13:00:00:00Z

Description:
    Describe the migrations that have been applied to Elasticsearch data
    according to the history index that migrates maintains.
    Timestamps are interpreted as UTC. They must be either of the format
    "%%Y-%%m-%%d" or "%%Y-%%m-%%dT%%H:%%M:%%SZ".
    Accepts zero, one, or two timestamp arguments. If there are no such
    arguments, all migration history is shown. If there's one, migration
    history since that time is shown. If there are two, migration history
    starting with the first time and ending with the second time is shown.

General Options: %s
""" % general_options

migrations = """
Usage:
    migrates migrations <options...>

Examples:
    migrates migrations --host 192.0.2.10:9200 --path my/migrations/path
    migrates migrations --pending --path my/migrations/path

Description:
    List and describe the migrations known by migrates.

Migrations Options:
    --pending
        List only those migrations which are currently pending, i.e.
        those that are registed but have yet to be run.

General Options: %s
""" % general_options

restore_templates = """
Usage:
    migrates restore_templates <path> <options...>

Examples:
    migrates restore_templates my/templates.json

Description:
    Load templates from a json file and update the templates currently in
    Elasticsearch to reflect them.
    This may be used to recover Elasticsearch state after a failed
    migration, if normal recovery fails or is prematurely terminated.

General Options: %s
""" % general_options

restore_indexes = """
Usage:
    migrates restore_indexes <path> <options...>

Examples:
    migrates restore_indexes my/indexes.json

Description:
    Given a json file describing indexes that were affected by a recent
    migration attempt, restore documents from dummy indexes back to their
    original locations.
    This may be used to recover Elasticsearch state after a failed
    migration, if normal recovery fails or is prematurely terminated.

General Options: %s
""" % general_options

restore_history = """
Usage:
    migrates restore_history <path> <options...>

Examples:
    migrates restore_history my/history.json

Description:
    Load migration history information from a json file and update
    migrates' history index in Elasticsearch to include that data.
    This may be used to recover Elasticsearch state after a failed
    migration, if normal recovery fails or is prematurely terminated.

General Options: %s
""" % general_options

restore_cleanup = """
Usage:
    migrates restore_cleanup <options...>

Examples:
    migrates restore_cleanup
    migrates restore_cleanup --older-than 2000-01-01

Description:
    Clean up old recovery files that are written at the beginning of
    migration to be used to restore Elasticsearch state in case of a
    migration failure and normal recovery failure.
    
Cleanup Options:
    --older-than
        Only remove files older than a date given in UTC and formatted
        like either "%%Y-%%m-%%d" or "%%Y-%%m-%%dT%%H:%%M:%%SZ". Files
        newer than this will not be removed.
    --keep-files
        Keep at least this many of the most recent recovery files, even
        if they're older than the given date. Defaults to keeping the
        four most recent recovery files of each type.

General Options: %s
""" % general_options

remove_history = """
Usage:
    migrates remove_history <options...>

Examples:
    migrates remove_history --host 192.0.2.10:9200

Description:
    Remove migrates' migration history index from Elasticsearch.
    Migration history is stored in the "migrates_history" index unless
    otherwise specified.

General Options: %s
""" % general_options

remove_dummies = """
Usage:
    migrates remove_dummies <options...>

Examples:
    migrates remove_dummies --host 192.0.2.10:9200

Description:
    Intermediate "dummy" indexes are created during the migration
    process and, unless otherwise specified, removed at the end of the
    process after a successful migration or failure recovery has taken
    place.
    This command indiscriminately removes anything that looks like
    one of migrates' dummy indexes. This means any index matching the
    pattern "migrates_dummy_*", assuming that migrates hasn't been told
    to write and look for its dummies somewhere else. Be careful!

General Options: %s
""" % general_options

help = """
Usage:
    migrates help <command>

Examples:
    migrates help
    migrates help run

Description:
    Show information and usage instructions for a command, or general usage
    when no command is given.
    The recognized commands are "run", "reindex", "history", "migrations",
    "restore_templates", "restore_indexes", "restore_history",
    "restore_cleanup", "remove_history", "remove_dummies", and "help".

General Options: %s
""" % general_options



commands = {
    'run': run,
    'reindex': reindex,
    'history': history,
    'migrations': migrations,
    'restore_templates': restore_templates,
    'restore_indexes': restore_indexes,
    'restore_history': restore_history,
    'restore_cleanup': restore_cleanup,
    'remove_history': remove_history,
    'remove_dummies': remove_dummies,
    'help': help,
}
