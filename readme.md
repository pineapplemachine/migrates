# migrates

The migrates tool offers a solution for migrating data stored in Elasticsearch.

More info coming soon - this repo is still under construction!

## Setup

To install migrates as a dependency so that it can be imported in migration
scripts, run `pip install migrates` or, alternatively, download this repository
and run `pip install .` in its root directory.

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

## How To

Migrates makes it possible to write Elasticsearch migrations as simple Python
scripts. Elasticsearch data is read once and written once during the migration
process; migrations are structured in such a way that their modifications to
Elasticsearch templates and documents are applied sequentially.

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
    def transform_documents():
        # A transformation function to be applied to documents in Elasticsearch
        def transform(doc):
            doc['_source']['x'] = doc['_source']['y'] ** 2
            return doc
        # Apply that transformation to documents in indexes matching the pattern
        # "migrates_test_*" and to all document types.
        return {
            'migrates_test_*': {'*': transform}
        }
```

Then you could get a very detailed log of what that migration would do to
the data in Elasticsearch like so:

``` text
migrates run my_first_migration --path path/to/migrations.py --dry --detail *
```

And then, once you're satisfied that the migration does what you expect it
to, you can apply the migration like this:

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

And, if you wanted to, you could clear your migration history like so, and all
registered migrations would become recognized as pending:

```
migrates remove_history
```


