import elasticsearch

import migrates
from .test_utils import callmigrates, iterate_test_data, remove_test_data



document_count = 1000



def insert_test_data(connection):
    with migrates.Batch(connection, migrates.Logger()) as batch:
        for i in range(0, document_count):
            batch.add({
                '_op_type': 'index',
                '_index': 'migrates_test_reindex',
                '_type': 'test_' + str(i % 3),
                '_id': str(i),
                '_source': {'x': i}
            })

def validate_test_data(connection, index):
    docs = set()
    for document in iterate_test_data(connection, index=index):
        docs.add(document['_source']['x'])
    assert len(docs) == document_count



def __main__():
    logger = migrates.Logger()
    connection = elasticsearch.Elasticsearch()
    
    logger.log('Removing old test data.')
    remove_test_data(connection)
    
    try:
        logger.log('Inserting new test data.')
        insert_test_data(connection)
        
        logger.log('Reindexing data back into the same index.')
        callmigrates('reindex migrates_test_reindex -y')
        
        logger.log('Validating resulting data.')
        validate_test_data(connection, index='migrates_test_reindex')
        
        logger.log('Reindexing data into a different index.')
        callmigrates('reindex "migrates_test_reindex=>migrates_test_reindex_2" -y')
        
        logger.log('Validating resulting data.')
        assert not connection.indices.exists('migrates_test_reindex')
        validate_test_data(connection, index='migrates_test_reindex_2')

    finally:
        logger.log('Cleaing up test data.')
        remove_test_data(connection)



if __name__ == '__main__':
    __main__()
