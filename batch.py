"""
This module implements an Elasticsearch bulk API wrapper.
"""

import time
import elasticsearch

class Batch(object):
    """
    Provides a wrapper for the Elasticsearch bulk API.
    """
    
    def __init__(self, connection, logger, size=1000, indexes_size=5):
        """
        Initialize a Batch object given an Elasticsearch connection object,
        a batch size `size` indicating the number of documents to trigger a
        flush when met, and another size `indexes_size` to trigger a flush when
        the number of different indexes involved in the bulk action exceeds
        that value.
        Note that the latter limit is to help prevent bulk index errors
        resulting from filled queues; the number of items added to the bulk
        queue at once correlates with the number of affected indexes.
        """
        self.connection = connection
        self.logger = logger
        self.size = size
        self.indexes_size = indexes_size
        self.indexes = set()
        self.actions = list()
        
    def add(self, action):
        """
        Add an action to the batch. An action is represented by a dictionary in
        the format described by the Elasticsearch API docs here:
        https://elasticsearch-py.readthedocs.io/en/master/helpers.html#bulk-helpers
        """
        self.actions.append(action)
        self.indexes.add(action['_index'])
        if len(self.actions) >= self.size or len(self.indexes) >= self.indexes_size:
            self.flush()
    
    def update(self, actions):
        for action in actions:
            self.add(action)
    
    def flush(self, max_attempts=3, attempts=0):
        """
        Flush the queue. This invokes the Elasticsearch API's bulk helper.
        It will attempt the operation several times in case it fails.
        """
        if self.actions:
            try:
                elasticsearch.helpers.bulk(self.connection, self.actions)
            except elasticsearch.helpers.BulkIndexError as e:
                if attempts < max_attempts:
                    self.logger.warning('Bulk action failed; trying again in a few seconds...')
                    time.sleep(5)
                    self.flush(max_attempts=max_attempts, attempts=attempts + 1)
                else:
                    raise e
            else:
                if attempts != 0:
                    self.logger.info(
                        'Bulk action succeeded after %d attempts.', attempts + 1
                    )
        if attempts == 0:
            self.indexes = set()
            self.actions = list()
            time.sleep(1)
        
    def __enter__(self):
        return self
    def __exit__(self, exception_type, exception_value, traceback):
        if exception_value is None:
            self.flush()
