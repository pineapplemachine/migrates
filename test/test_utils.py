import subprocess
from elasticsearch import helpers as eshelpers

import migrates



def callmigrates(args):
    return subprocess.check_output([
        'python -m migrates.__main__ ' + args
    ], shell=True).decode('utf-8')



def iterate_test_data(connection, index='migrates_test_*'):
    for document in eshelpers.scan(
        client=connection,
        preserve_order=True,
        index=index,
        query=migrates.Migrates.scan_query
    ):
        yield document
