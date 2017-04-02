import test_transformations
import test_cli

from migrates import Logger

def __main__():
    logger = Logger()
    
    try:
        logger.important('Running test "test_transformations".')
        test_transformations.__main__()
    except:
        logger.error('Test "test_transformations" failed.')
    else:
        logger.important('Test "test_transformations" succeeded.')
        
    try:
        logger.important('Running test "test_cli".')
        test_cli.__main__()
    except:
        logger.error('Test "test_cli" failed.')
    else:
        logger.important('Test "test_cli" succeeded.')

if __name__ == '__main__':
    __main__()
