"""
This is an automated test for verifying that migration behavior is consistent
regardless of whether several migrations are evaluated during a single
migration process, or over several processes.
"""

import elasticsearch

import migrates
from .test_utils import callmigrates, remove_test_data



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



@migrates.register('migration_template_fail_test_0', '2017-01-01')
class migration_template_fail_test_0(object):
    @staticmethod
    def transform_templates(templates):
        templates['migrates_test_template'] = test_template
        return templates
    @staticmethod
    def transform_documents():
        return {
            'migrates_test_*': {'*': lambda doc: doc}
        }

@migrates.register('migration_template_fail_test_1', '2017-01-02')
class migration_template_fail_test_1(object):
    @staticmethod
    def transform_templates(templates):
        raise ValueError('Simulated template migration failure.')



original_migrate_templates = migrates.Migrates.migrate_templates

def patch_migrate_templates(self, original, updated):
    # This one is a bit contrived because:
    # 1. The call should simulate a partial failure, i.e. data in Elasticsearch
    # was modified and needs to be recovered after the failure.
    original_migrate_templates(self, original, updated)
    # 2. This method is called a second time during normal recovery, and at
    # that point the call should succeed so that normal recovery can be tested.
    migrates.Migrates.migrate_templates = original_migrate_templates
    # And 3. the first call does need to actually fail.
    raise ValueError('Simulated persistence failure.')

def patch_revert_template_migration(self):
    raise ValueError('Simulated normal recovery failure.')
    
def __main__():
    logger = migrates.Logger()
    connection = elasticsearch.Elasticsearch()
    
    logger.log('Removing data from previous tests, if present.')
    remove_test_data(connection)
    
    try:
        mig = migrates.Migrates(connection, restore_path='')
        mig.logger.silent = True
        
        logger.log('Getting current Elasticsearch templates.')
        original_templates = mig.get_templates()
        
        logger.log('Testing a transformation failure during template migration.')
        result = mig.migrate([
            mig.get('migration_template_fail_test_0'),
            mig.get('migration_template_fail_test_1'),
        ])
        assert result.fail_state is mig.FailState.TransformTemplates
        assert mig.get_templates() == original_templates
        
        logger.log('Testing normal recovery from a persistence failure during template migration.')
        migrates.Migrates.migrate_templates = patch_migrate_templates
        result = mig.migrate([mig.get('migration_template_fail_test_0')])
        assert result.fail_state is mig.FailState.PersistTemplates
        assert mig.get_templates() == original_templates
        
        logger.log('Running failing migration and simulating a normal recovery failure.')
        migrates.Migrates.migrate_templates = patch_migrate_templates
        migrates.Migrates.revert_template_migration = patch_revert_template_migration
        result = mig.migrate([mig.get('migration_template_fail_test_0')])
        assert result.fail_state is mig.FailState.PersistTemplates
        # Verify assumption that the migration modified template data and that
        # recovery of the original template data did in fact fail.
        assert mig.get_templates() != original_templates
        
        logger.log('Testing manual template recovery.')
        callmigrates('restore_templates "%s" -y' % result.restore_templates_path)
        assert mig.get_templates() == original_templates
        
    finally:
        logger.log('Cleaning up test data from Elasticsearch.')
        remove_test_data(connection)



if __name__ == '__main__':
    __main__()
