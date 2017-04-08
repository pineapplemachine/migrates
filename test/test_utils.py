import subprocess
import elasticsearch
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

def remove_test_data(connection):
    try:
        connection.indices.delete('migrates_test_*')
    except elasticsearch.exceptions.NotFoundError:
        pass
    try:
        connection.indices.delete_template('migrates_test_template')
    except elasticsearch.exceptions.NotFoundError:
        pass
