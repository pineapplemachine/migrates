"""
This is an automated test for verifying CLI behavior in several cases.
"""

import sys, re, subprocess
import elasticsearch
import migrates

logger = migrates.Logger()



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
        },
    }
}



@migrates.register('migration_0', '2017-01-01', 'Do a thing')
class migration_0(object):
    pass
@migrates.register('migration_1', '2017-01-02', 'Do another thing')
class migration_1(object):
    pass
@migrates.register('migration_2', '2017-01-03', 'Do yet another thing')
class migration_2(object):
    pass
@migrates.register('migration_3', '2017-01-04', 'Do another thing entirely')
class migration_3(object):
    @staticmethod
    def transform_templates(templates):
        templates['migrates_test_template'] = test_template
        return templates



migrations_text = """
2017-01-01T00:00:00Z: "migration_0", Do a thing
2017-01-02T00:00:00Z: "migration_1", Do another thing
2017-01-03T00:00:00Z: "migration_2", Do yet another thing
2017-01-04T00:00:00Z: "migration_3", Do another thing entirely
""".strip()

no_history_text = """
No migration history index is present in Elasticsearch.
""".strip()

new_history_regex = r"""
(?s).*\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ: "migration_0", Do a thing
\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ: "migration_1", Do another thing
\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ: "migration_2", Do yet another thing
\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ: "migration_3", Do another thing entirely.*
""".strip()

partial_history_regex = r"""
(?s).*\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ: "migration_1", Do another thing
\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ: "migration_2", Do yet another thing.*
""".strip()

run_migration_regex = r"""
(?s).*Writing original template data to path "(.+?)"\.
Writing migration information to path "(.+?)"\.
Writing affected index information to path "(.+?)"\..*
""".strip()



def call(args):
    return subprocess.check_output([
        'python -m migrates.__main__ ' + args
    ], shell=True).decode('utf-8')



def __main__():
    mig = migrates.Migrates()
    try:
        mig.connection.indices.delete_template('migrates_test_template')
    except elasticsearch.exceptions.NotFoundError:
        pass
    original_templates = mig.get_templates()
    
    logger.log('Testing migration registration and listing.')
    migrations = call('migrations --path %s' % sys.argv[0])
    assert migrations_text in migrations
    
    logger.log('Testing history removal, recording, and listing.')
    call('remove_history -y')
    assert no_history_text in call('history')
    run_migration = call('run --path %s -y' % sys.argv[0])
    assert re.match(new_history_regex, call('history'))
    call('remove_history -y')
    assert no_history_text in call('history')
    
    logger.log('Testing history when running specified migrations.')
    call('run migration_1 migration_2 --path %s -y' % sys.argv[0])
    assert re.match(partial_history_regex, call('history'))
    call('remove_history -y')
    assert no_history_text in call('history')
    
    logger.log('Verifying correctness of template migration.')
    updated_templates = mig.get_templates()
    assert 'migrates_test_template' in updated_templates
    del updated_templates['migrates_test_template']
    assert updated_templates == original_templates
    
    logger.log('Testing recovery functions.')
    migration_match = re.match(run_migration_regex, run_migration)
    templates_path = migration_match.group(1)
    migrations_path = migration_match.group(2)
    indexes_path = migration_match.group(3)
    
    logger.log('Testing templates recovery.')
    call('restore_templates "%s" --dry' % templates_path)
    assert 'migrates_test_template' in mig.get_templates()
    call('restore_templates "%s" -y' % templates_path)
    assert mig.get_templates() == original_templates
    
    logger.log('Testing migration history recovery.')
    call('remove_history -y')  # Note that template recovery creates a history entry
    call('restore_history "%s" --dry' % migrations_path)
    assert no_history_text in call('history')
    call('restore_history "%s" --y' % migrations_path)
    assert re.match(new_history_regex, call('history'))
    
    logger.log('All done!')



if __name__ == '__main__':
    __main__()
