"""
This is an automated test for verifying that migration behavior is consistent
regardless of whether several migrations are evaluated during a single
migration process, or over several processes.
"""

import elasticsearch

import migrates
from .test_utils import iterate_test_data, remove_test_data



test_template_0 = {
    "template": "migrates_test",
    "order": 0,
    "settings": {},
    "aliases": {},
    "mappings": {
        "test": {
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"}
            }
        }
    }
}

test_template_1 = {
    "template": "migrates_test",
    "order": 0,
    "settings": {},
    "aliases": {},
    "mappings": {
        "test": {
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "z": {"type": "integer"}
            }
        }
    }
}



@migrates.register('migration_seq_test_0', '2017-01-01')
class migration_seq_test_0(object):
    @staticmethod
    def transform_documents():
        def transform(doc):
            doc['_source']['y'] = doc['_source']['x'] ** 2
            return doc
        return {
            'migrates_test_seq': {'test': transform}
        }
    @staticmethod
    def transform_templates(templates):
        templates['migrates_test_template'] = test_template_0
        return templates

@migrates.register('migration_seq_test_1', '2017-01-02')
class migration_seq_test_1(object):
    @staticmethod
    def transform_documents():
        def transform(doc):
            doc['_source']['z'] = doc['_source']['y'] ** 2
            return doc
        return {
            'migrates_test_seq': {'test': transform}
        }
    @staticmethod
    def transform_templates(templates):
        test_template = templates['migrates_test_template']
        test_template['mappings']['test']['properties']['z'] = {
            "type": "integer"
        } 
        return templates



document_count = 500

def insert_test_data(connection):
    with migrates.Batch(connection, migrates.Logger()) as batch:
        for i in range(0, document_count):
            batch.add({
                '_op_type': 'index',
                '_index': 'migrates_test_seq',
                '_type': 'test',
                '_id': str(i),
                '_source': {'x': i}
            })

def validate_test_data(connection):
    test_template = connection.indices.get_template('migrates_test_template')[
        'migrates_test_template'
    ]
    assert(test_template == test_template_1)
    count = 0
    for doc in iterate_test_data(connection):
        assert doc['_source']['y'] == doc['_source']['x'] ** 2
        assert doc['_source']['z'] == doc['_source']['y'] ** 2
        count += 1
    assert count == document_count



def __main__():
    logger = migrates.Logger()
    connection = elasticsearch.Elasticsearch()
    
    logger.log('Removing data from previous tests, if present.')
    remove_test_data(connection)
    
    try:
        logger.log('Inserting test data into Elasticsearch.')
        insert_test_data(connection)
        
        mig = migrates.Migrates(connection)
        mig.logger.quiet = True
        
        logger.log('Running migrations separately.')
        mig.migrate([mig.get('migration_seq_test_0')])
        mig.migrate([mig.get('migration_seq_test_1')])
        validate_test_data(connection)
        
        logger.log('Removing and reinserting test data.')
        remove_test_data(connection)
        insert_test_data(connection)
        
        logger.log('Running migrations together.')
        mig.migrate([mig.get('migration_seq_test_0'), mig.get('migration_seq_test_1')])
        validate_test_data(connection)
        
    finally:
        logger.log('Cleaning up test data from Elasticsearch.')
        remove_test_data(connection)



if __name__ == '__main__':
    __main__()

