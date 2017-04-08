import sys, traceback
from migrates import Logger

from . import test_transformations
from . import test_cli
from . import test_reindex

tests = [
    ('test_transformations', test_transformations),
    ('test_cli', test_cli),
    ('test_reindex', test_reindex),
]



def __main__():
    logger = Logger()
    
    results_log = sys.argv[1] if len(sys.argv) >= 2 else 'migrates_test_results.log'
    
    failures = []
    exceptions = []
    
    for test_key, test_module in tests:
        try:
            logger.important('Running test "%s".', test_key)
            test_module.__main__()
        except Exception as e:
            logger.exception('Test "%s" failed.', test_key)
            failures.append(test_key)
            exceptions.append(traceback.format_exc(e))
        else:
            logger.important('Test "%s" succeeded.', test_key)
    
    logger.important('Finished running %s tests, encountered %s failures.',
        len(tests), len(failures)
    )
    
    with open(results_log, 'a') as results_file:
        results_file.write('RESULTS:\n')
        for test_key, test_module in tests:
            results_file.write('%s: %s\n' % (
                ('FAILED' if test_key in failures else 'PASSED'), test_key
            ))
        if exceptions:
            results_file.write('EXCEPTIONS:\n')
            for exception in exceptions:
                results_file.write(exception + '\n')
            
    
if __name__ == '__main__':
    __main__()