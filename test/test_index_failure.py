"""
This is an automated test for verifying that migration behavior is consistent
regardless of whether several migrations are evaluated during a single
migration process, or over several processes.
"""

import elasticsearch

import migrates
from .test_utils import callmigrates, iterate_test_data, remove_test_data



test_template = {
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



@migrates.register('migration_index_fail_test_0', '2017-01-01')
class migration_index_fail_test_0(object):
    @staticmethod
    def transform_documents():
        def transform(doc):
            doc['_source']['y'] = doc['_source']['x'] ** 2
            return doc
        return {
            'migrates_test_index_fail': {'test': transform}
        }
    @staticmethod
    def transform_templates(templates):
        templates['migrates_test_template'] = test_template
        return templates

@migrates.register('migration_index_fail_test_1', '2017-01-02')
class migration_index_fail_test_1(object):
    @staticmethod
    def transform_documents():
        def transform(doc):
            if doc['_source']['x'] >= document_count / 2:
                raise ValueError('Simulated index migration failure.')
            return doc
        return {
            'migrates_test_index_fail': {'test': transform}
        }

@migrates.register('migration_index_fail_test_2', '2017-01-03')
class migration_index_fail_test_2(object):
    @staticmethod
    def transform_documents():
        def transform(doc):
            doc['_source']['y'] = doc['_source']['x'] ** 3
            return doc
        return {
            'migrates_test_index_fail': {'test': transform}
        }



document_count = 500

def insert_test_data(connection):
    with migrates.Batch(connection, migrates.Logger()) as batch:
        for i in range(0, document_count):
            batch.add({
                '_op_type': 'index',
                '_index': 'migrates_test_index_fail',
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
        
        mig = migrates.Migrates(connection, restore_path='')
        mig.logger.silent = True
        migrations = [
            mig.get('migration_index_fail_test_0'),
            mig.get('migration_index_fail_test_1'),
            mig.get('migration_index_fail_test_2'),
        ]
        
        logger.log('Getting current Elasticsearch templates.')
        original_templates = mig.get_templates()
        
        logger.log('Testing normal recovery from an index migration failure.')
        result = mig.migrate(migrations)
        assert result.fail_state is mig.FailState.MigrateDocuments
        assert validate_test_data(connection)
        assert mig.get_templates() == original_templates
        
        logger.log('Running failing migration and simulating normal index recovery failure.')
        migrates.Migrates.revert_indexes_migration = patch_revert_indexes_migration
        result = mig.migrate(migrations)
        assert result.fail_state is mig.FailState.MigrateDocuments
        assert not validate_test_data(connection)  # Recovery should have failed
        
        logger.log('Testing manual index recovery.')
        callmigrates('restore_indexes "%s" -y' % result.restore_indexes_path)
        assert validate_test_data(connection)
        assert mig.get_templates() == original_templates
        
    finally:
        logger.log('Cleaning up test data from Elasticsearch.')
        remove_test_data(connection)



if __name__ == '__main__':
    __main__()

