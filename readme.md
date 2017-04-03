# migrates

Migrates offers a solution for migrating data stored in Elasticsearch.
It is written and maintained by Sophie Kirschner (sophiek@pineapplemachine.com)
and is distributed under the
[GNU GPL v3.0](https://github.com/pineapplemachine/migrates/blob/master/LICENSE)
license.

Migrates is tested with Python 2.7.13 and 3.6.1, and with Elasticsearch
1.7.2, 2.4.2, and 5.3.0. It is tested with
[elasticsearch-py](https://www.github.com/elastic/elasticsearch-py)
1.7.0 and 5.3.0.
Though migrates itself should be compatible with a broad range of versions of
elasticsearch-py, some later versions of the package may not be compatible with
older versions of Elasticsearch.

In addition to elasticsearch-py, migrates also depends on
[colorama](https://www.github.com/tartley/colorama) for log prettification.
Migrates still functions without colorama, but your logs would be
substaintally less colorful that way.

Though migrates is designed such that a failed operation should never cause
irrecoverable data loss, _please don't take my word for it_. If your data is
important then back it up often, and certainly do so before using migrates.
In case something _does_ go wrong, migrates will attempt to automatically
recover your data. If recovery fails, it will tell you what to do to try
again. Try not to worry — migrates doesn't make any changes to your data
before making sure the original data exists somewhere else first.

Though that doesn't cancel out the risk of a misguided migration successfully
doing something with your data that you ended up not wanting to do.
Be careful, and make liberal use of migrates' dry run feature!

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

### Options

Here are listed some of the most important options. For more information and
for a complete listing, please using `migrates help <command>`.
Note that some options are not applicable to all commands.

#### host

The `--host` option is for specifying one or more Elasticsearch hosts to operate
on. If no hosts are specified, migrates defaults to `127.0.0.1:9200`.

#### path

One or more paths to either Python package directories or individual Python
files can be specified using the `--path` option.
These modules will be imported so that any migrations that they register
can be recognized and handled by migrates. For example, if you implemented your
migrations in a `my_migrations.py` script, you would want to run something like
`migrates run --path path/to/my_migrations.py`.

#### dry

The `--dry` flag indicates that migrates should do a dry run, where it reports
everything that would happen during a normal run, without actually modifying
any data. Every command that would normally modify data respects the `--dry`
flag, not only `run`.

#### detail

The `--detail` option takes one or more pattern strings and when, during
migration, a template or index name matches any of the patterns given here,
extra information will be given about the changes that are taking place.
Templates matching a pattern will have their complete original and updated
contents outputted, and one document per index and document type will also
have the original and updated versions outputted when the containing index
matches any of the patterns.
To show detailed information about changes to all templates and indexes,
you can run `migrates run --detail *`.

### Commands

Here are summaries of some of the most important commands that migrates makes
available.
For a complete explanation of the commands and the options they accept, please
use `migrates help` and `migrates help <command>`.

#### run

The `run` command is used to run a series of migrations specified by name, or
any pending migrations. (Pending migrations are those that you've registered
with migrates but that haven't been run on a given Elasticsearch host yet.)

To run a migration named `my_migration` you could do this:

``` text
migrates run my_migration --path my/migrations/path
```

To run pending migrations in ascending timestamp order:

``` text
migrates run --path my/migrations/path
```

Don't forget to make use of the dry run and detail features!
This would tell you the migrations that would run and how they would affect
your data, without actually modifying it.

``` text
migrates run --path my/migrations/path --dry --detail *
```

#### history

The `history` command is for listing migration history for a given Elasticsearch
host. It tells you what migrations were run and when.

``` text
migrates history --host 192.0.2.10:9200
```

#### migrations

The `migrations` command lists migrations that have been registered with
migrates and describes them.

``` text
migrates migrations --path my/migrations/path
```

## Running tests

The `vagrant/` directory of this repository contains tools for provisioning
a Ubuntu VM using [vagrant](https://www.vagrantup.com/) and then running the
automated tests in the `test/` directory across different versions of Python,
Elasticsearch, and elasticsearch-py.

There's a readme with testing instructions in that directory
[here](https://github.com/pineapplemachine/migrates/blob/master/vagrant/readme.md).
