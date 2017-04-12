import sys, traceback
from migrates import Logger

from . import test_transformations
from . import test_sequence
from . import test_cli
from . import test_reindex
from . import test_malformed_doc_failure
from . import test_index_failure
from . import test_template_failure

tests = [
    ('test_transformations', test_transformations),
    ('test_sequence', test_sequence),
    ('test_cli', test_cli),
    ('test_reindex', test_reindex),
    ('test_malformed_doc_failure', test_malformed_doc_failure),
    ('test_index_failure', test_index_failure),
    ('test_template_failure', test_template_failure),
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
