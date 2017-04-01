# migrates

Migrates offers a solution for migrating data stored in Elasticsearch.
It is written and maintained by Sophie Kirschner (sophiek@pineapplemachine.com)
and is distributed under the
[GNU GPL v3.0](https://github.com/pineapplemachine/migrates/blob/master/LICENSE)
license.

## Setup

To install migrates as a dependency so that it can be imported in migration
scripts, run `pip install migrates` (SOON!) or, alternatively, download this
repository and run `pip install .` in its root directory.

To make migrates usable as a command line tool on Unix platforms, you can add
this line to your bash profile:

``` text
alias migrates="python -m migrates.__main__"
```

On Windows, you can put `migrates.bat`, located in this repository's root
directory, someplace that's referred to in your PATH environment variable.

If migrates has been set up correctly, entering this in your command line
should show migrates' general usage instructions:

``` text
migrates help
```

## Introduction

Migrates makes it possible to write Elasticsearch migrations as simple Python
scripts. Elasticsearch data is read once and written once during the migration
process; migrations are structured in such a way that their modifications to
Elasticsearch templates and documents are applied sequentially to templates,
and to each document as it is read.

Here's an example of a simple migration:

``` python
import migrates

# Register a migration with migrates
@migrates.register(
    # A unique identifier for the migration
    name='my_first_migration',
    # The date you made the migration - migrations are run in chronological order
    date='2000-01-01',
    # A very helpful description of what the migration does
    description='This is an example migration to square `x` and put it in `y`.'
)
class my_first_migration(object):
    @staticmethod
    def transform_templates(templates):
        # The transform_templates method can be used to add, modify, or remove
        # index templates.
        templates['my_template'] = {
            'My template data...'
        }
        return templates
    @staticmethod
    def transform_documents():
        # The transform_documents method can be used to make modifications to
        # individual documents.
        # Here's a transformation function to be applied to documents.
        def transform(doc):
            doc['_source']['x'] = doc['_source']['y'] ** 2
            return doc
        # Apply that transformation to documents in indexes matching the pattern
        # "my_index_*" and to all document types.
        return {
            'my_index_*': {'*': transform}
        }
```

The `transform_templates` method is pretty straightforward: It accepts as
an argument the state of templates as they currently are, and returns the
state of templates as they ought to be.

The `transform_documents` method is a little more interesting. It returns
a dictionary which maps index patterns to other dictionaries mapping document
type patterns to the transformation function that should be applied to each
document. In the above example, the `transform` function will be called
for every document in an index matching the pattern `my_index_*` and with
a document type matching the pattern `*`.

You could get a quite detailed log of what that migration would do to
the data in Elasticsearch like so:

``` text
migrates run my_first_migration --path path/to/migrations.py --dry --detail *
```

And then, once you're satisfied that the migration does what you expect it
to, you could apply the migration like this:

``` text
migrates run my_first_migration --path path/to/migrations.py
```

Migrates keeps a history of what migrations were applied and when in an
Elasticsearch index named `migrates_history`. If you were to add another
migration to that script above and name it, say, `my_second_migration`,
and then you were to run this:

``` text
migrates run --path path/to/migrations.py
```

Migrates would see that `my_first_migration` was already applied to the data
currently in Elasticsearch, and `my_second_migration` not yet applied, and so
it would run `my_second_migration` and that migration only.

You could then view your complete migration history by running:

``` text
migrates history
```

## Usage

Migrates is run using the format `migrates <command> <arguments...> <options>`
where `command` is one of the recognized commands listed below, `arguments`
are zero or more ordered arguments related to that command (the number of such
arguments expected varies by command), and `options` are zero or more unordered
named arguments given in the format `--flag` or `--option values...`.

The recognized commands are `help`, `run`, `reindex`, `history`, `migrations`,
`restore_templates`, `restore_indexes`, `restore_history`, `restore_cleanup`,
`remove_history`, and `remove_dummies`.

The `restore_*` commands pertain to recovering Elasticsearch state in the event
of a failed migration _and_ a failed normal recovery. Don't worry, if something
goes so wrong migrates should tell you how to fix it.

The `remove_*` commands can be used to remove Elasticsearch data that migrates
creates.

For a complete explanation of the commands and the options they accept, please
use `migrates help <command>`.

### help

Show information and usage instructions for a command, or general usage
when no command is given.

``` text
migrates help
migrates help run
```

### run

When a list of migration names is explicitly given, those migrations
are run in the order they were provided.
When no list of names is given, pending migrations are run. (Pending
migrations include those which have been registered by the user but,
according to the migration history found in Elasticsearch, have never
been run.) Pending migrations are run in ascending timestamp order.

``` text
migrates run --host 192.0.2.10:9200 --path my/migrations/path
migrates run my_migration_name --dry --path my/migrations/path
```

### reindex

Reindex the contents of an index or indexes, optionally to a different
destination index than where the documents were originally located.
This functionality can be used, for example, to update the settings
and mappings of an index after changing a template which applies to it.
When "=>" is present in an index option, it indicates that documents in
the index on the left side should be reindexed into the index on the
right side.
When "=>" is not present, documents are reindexed back into the same
index that they came from.

``` text
migrates reindex my_index another_index
migrates reindex "source_index=>destination_index"
migrates reindex "index_prefix_*"
migrates reindex my_index a_index=>b_index --host 192.0.2.10:9200 --dry
```

### history

Describe the migrations that have been applied to Elasticsearch data
according to the history index that migrates maintains.
Timestamps are interpreted as UTC. They must be either of the format
"%%Y-%%m-%%d" or "%%Y-%%m-%%dT%%H:%%M:%%SZ".
Accepts zero, one, or two timestamp arguments. If there are no such
arguments, all migration history is shown. If there's one, migration
history since that time is shown. If there are two, migration history
starting with the first time and ending with the second time is shown.

``` text
migrates history --host 192.0.2.10:9200
migrates history 2012-01-01
migrates history 2012-02-28T10:00:00Z 2012-04-01T13:00:00:00Z
```

### migrations

List and describe the migrations known by migrates.

``` text
migrates migrations --host 192.0.2.10:9200 --path my/migrations/path
migrates migrations --pending --path my/migrations/path
```

### restore_templates

Load templates from a json file and update the templates currently in
Elasticsearch to reflect them.
This may be used to recover Elasticsearch state after a failed
migration, if normal recovery fails or is prematurely terminated.

``` text
migrates restore_templates my/templates.json
```

### restore_indexes

Given a json file describing indexes that were affected by a recent
migration attempt, restore documents from dummy indexes back to their
original locations.
This may be used to recover Elasticsearch state after a failed
migration, if normal recovery fails or is prematurely terminated.

``` text
migrates restore_indexes my/indexes.json
```

### restore_history

Load migration history information from a json file and update
migrates' history index in Elasticsearch to include that data.
This may be used to recover Elasticsearch state after a failed
migration, if normal recovery fails or is prematurely terminated.

``` text
migrates restore_history my/history.json
```

### restore_cleanup

Clean up old recovery files that are written at the beginning of
migration to be used to restore Elasticsearch state in case of a
migration failure and normal recovery failure.

``` text
migrates restore_cleanup
migrates restore_cleanup --older-than 2000-01-01
```

### remove_history

Remove migrates' migration history index from Elasticsearch.
Migration history is stored in the "migrates_history" index unless
otherwise specified.

``` text
migrates remove_history --host 192.0.2.10:9200
```

### remove_dummies

Intermediate "dummy" indexes are created during the migration
process and, unless otherwise specified, removed at the end of the
process after a successful migration or failure recovery has taken
place.
This command indiscriminately removes anything that looks like
one of migrates' dummy indexes. This means any index matching the
pattern "migrates_dummy_*", assuming that migrates hasn't been told
to write and look for its dummies somewhere else. Be careful!

``` text
migrates remove_dummies --host 192.0.2.10:9200
```

## Running tests

Automated tests for this repository are currently a work in progress!
