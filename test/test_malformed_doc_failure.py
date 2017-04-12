"""
This is an automated test for verifying that migration behavior is consistent
regardless of whether several migrations are evaluated during a single
migration process, or over several processes.
"""

import elasticsearch

import migrates
from .test_utils import iterate_test_data, remove_test_data



@migrates.register('migration_malformed_doc_test_0', '2017-01-01')
class migration_malformed_doc_test_0(object):
    @staticmethod
    def transform_documents():
        def transform(doc):
            del doc['_index']
            return doc
        return {
            'migrates_test_malformed_doc': {'test': transform}
        }



document_count = 100

def insert_test_data(connection):
    with migrates.Batch(connection, migrates.Logger()) as batch:
        for i in range(0, document_count):
            batch.add({
                '_op_type': 'index',
                '_index': 'migrates_test_malformed_doc',
                '_type': 'test',
                '_id': str(i),
                '_source': {'x': i, 'y': 0}
            })

def validate_test_data(connection):
    x_set = set()
    for doc in iterate_test_data(connection):
        x_set.add(doc['_source']['x'])
        if doc['_source']['y'] != 0:
            return False
    return len(x_set) == document_count



def patch_revert_indexes_migration(self):
    raise ValueError('Simulated normal recovery failure.')
    
def __main__():
    logger = migrates.Logger()
    connection = elasticsearch.Elasticsearch()
    
    logger.log('Removing data from previous tests, if present.')
    remove_test_data(connection)
    
    try:
        logger.log('Inserting test data into Elasticsearch.')
        insert_test_data(connection)
        assert validate_test_data(connection)
        
        logger.log('Running migration with transformation returning a malformed document.')
        mig = migrates.Migrates(connection)
        mig.logger.silent = True
        result = mig.migrate([mig.get('migration_malformed_doc_test_0')])
        
        logger.log('Validating resulting data.')
        assert result.fail_state is mig.FailState.MigrateDocuments
        assert validate_test_data(connection)
        
    finally:
        logger.log('Cleaning up test data from Elasticsearch.')
        remove_test_data(connection)



if __name__ == '__main__':
    __main__()

