# migrates

The migrates tool offers a solution for migrating data stored in Elasticsearch.

More info coming soon - this repo is still under construction!

## Setup

To install migrates as a dependency so that it can be imported in migration
scripts, run `pip install migrates` or, alternatively, download this repository
and run `pip install .` in its root directory.

To make migrates usable as a command line tool on unix platforms, you can add
this line to your bash profile:

``` text
alias migrates="python -m migrates.__main__"
```

## How To

Here's an example of a simple migration:

``` python
import migrates

@migrates.register(
    name='migration_test',
    date='2000-01-01',
    description='This is an example migration to square `x` and put it in `y`.'
)
class migration_test(object):
    @staticmethod
    def transform_documents():
        def transform(doc):
            doc['_source']['x'] = doc['_source']['y'] ** 2
            return doc
        return {
            'migrates_test_*': {'*': transform}
        }
```

