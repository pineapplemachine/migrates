"""
This is an automated test for verifying migration behavior and stability.
"""

from __future__ import division

import elasticsearch
from elasticsearch import helpers as eshelpers

import migrates



test_template = {
    "template": "migrates_test_*",
    "order": 0,
    "settings": {},
    "aliases": {},
    "mappings": {
        "test_0": {
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"}
            }
        },
        "test_1": {
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"}
            }
        },
        "test_2": {
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"}
            }
        }
    }
}



def remove_test_data(connection):
    try:
        connection.indices.delete('migrates_test_*')
    except elasticsearch.exceptions.NotFoundError:
        pass
    try:
        connection.indices.delete_template('migrates_test_template')
    except elasticsearch.exceptions.NotFoundError:
        pass

def insert_test_data(connection):
    with migrates.Batch(connection, migrates.Logger()) as batch:
        for i in range(0, 1200):
            batch.add({
                '_op_type': 'index',
                '_index': 'migrates_test_' + str(i // 200),
                '_type': 'test_' + str(i % 3),
                '_id': str(i),
                '_source': {
                    'x': i % 100, 'y': i % 100
                }
            })

def iterate_test_data(connection):
    for document in eshelpers.scan(
        client=connection,
        preserve_order=True,
        index='migrates_test_*',
        doc_type='test_*',
        query=migrates.Migrates.scan_query
    ):
        yield document

def validate_test_template(connection):
    template = connection.indices.get_template('migrates_test_template')
    assert template['migrates_test_template'] == test_template

def remove_migration_history(connection):
    try:
        connection.indices.delete('migrates_history')
    except elasticsearch.exceptions.NotFoundError:
        pass



@migrates.register('migration_test_0', '2017-01-01')
class migration_test_0(object):
    @staticmethod
    def transform_documents():
        def transform(doc):
            doc['_source']['y'] = doc['_source']['x'] ** 2
            return doc
        return {
            'migrates_test_0': {'test_0': transform}
        }

@migrates.register('migration_test_all', '2017-01-02')
class migration_test_all(object):
    @staticmethod
    def transform_documents():
        def transform(doc):
            doc['_source']['y'] = doc['_source']['x'] ** 2
            return doc
        return {
            'migrates_test_*': {'test_*': transform}
        }
    @staticmethod
    def transform_templates(templates):
        templates['migrates_test_template'] = test_template
        return templates

@migrates.register('migration_test_remove', '2017-01-02')
class migration_test_remove(object):
    @staticmethod
    def transform_documents():
        return {
            'migrates_test_*': {'test_*': lambda doc: None}
        }



def __main__():
    logger = migrates.Logger()
    connection = elasticsearch.Elasticsearch()
    
    logger.log('Removing current migration history')
    remove_migration_history(connection)
    
    logger.log('Removing data from previous tests, if present.')
    remove_test_data(connection)
    
    logger.log('Inserting test data into Elasticsearch.')
    insert_test_data(connection)
    
    try:
        mig = migrates.Migrates(connection)
        mig.logger.quiet = True
        
        logger.log('Testing a migration dry run.')
        mig.dry = True
        mig.migrate([mig.get('migration_test_0'), mig.get('migration_test_all')])
        for document in iterate_test_data(connection):
            assert doc['_source']['y'] == doc['_source']['x']
        
        logger.log('Testing migration applying to one index and document type.')
        mig.dry = False
        mig.migrate([mig.get('migration_test_0')])
        for document in iterate_test_data(connection):
            if document['_index'] == 'migrates_test_0' and document['_type'] == 'test_0':
                assert doc['_source']['y'] == doc['_source']['x'] ** 2
            else:
                assert doc['_source']['y'] == doc['_source']['x']
        
        logger.log('Testing migration applying to several indexes and document types.')
        mig.migrate([mig.get('migration_test_all')])
        for document in iterate_test_data(connection):
            assert doc['_source']['y'] == doc['_source']['x'] ** 2
        validate_test_template(connection)
        
        logger.log('Testing migration for removing documents.')
        mig.migrate([mig.get('migration_test_remove')])
        for document in iterate_test_data(connection):
            assert False
        
        logger.log('Validating migration history.')
        history = connection.search(index='migrates_history')
        assert history['hits']['total'] == 3
        
    finally:
        # All done! Do some cleanup.
        logger.log('Cleaning up test data from Elasticsearch.')
        remove_test_data(connection)



if __name__ == '__main__':
    __main__()
