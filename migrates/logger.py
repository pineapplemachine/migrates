"""
This module implements the logger used by migrates.
"""

import os, sys, traceback, datetime

# Use coloring to prettify the log if colorama is available.
# Since the colors aren't essential, just log boring style-less text
# if the dependency isn't there.
try:
    import colorama
    colors = True
except ImportError:
    colors = False

# Make confirmation prompts work for both Python 2 and Python 3
# http://stackoverflow.com/a/21731110/3478907
try:
    input = raw_input
except NameError:
    pass

class Logger(object):
    """
    For logging messages to the console and, optionally, to a log file.
    """
    
    def __init__(self, path=None, verbose=False, yes=False):
        self.verbose = verbose
        self.yes = yes
        self.path = None
        self.output_file = None
        self.set_path(path)
        if colors:
            colorama.init()
    
    def set_path(self, path):
        """Set a file path to log to, in addition to stdout."""
        self.path = path
        self.close()
        if path:
            self.output_file = open(path, 'ab')
            timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            self.output_file.write('Beginning migrates log from %s.\n' % timestamp)
    
    def close(self):
        """Close the associated log file, if any."""
        if self.output_file is not None:
            os.close(self.output_file)
            self.output_file = None
    
    def log(self, text, *args):
        """Log a line of text."""
        formatted = text % args if args else text
        print(formatted)
        if self.output_file is not None:
            self.output_file.write(formatted)
            self.output_file.write('\n')
    
    def debug(self, text, *args):
        """
        Log a line of text meant to communicate something trivial, but only
        if the logger is set to log verbosely.
        """
        if self.verbose:
            if colors:
                text = colorama.Fore.CYAN + text + colorama.Style.RESET_ALL
            self.log(text, *args)
    
    def error(self, text, *args):
        """Log a line of text meant to communicate an error."""
        if colors:
            text = (
                colorama.Fore.RED + colorama.Style.BRIGHT +
                text + colorama.Style.RESET_ALL
            )
        self.log(text, *args)
    
    def important(self, text, *args):
        """Log a line of text meant to communicate something very important."""
        if colors:
            text = (
                colorama.Fore.YELLOW + colorama.Style.BRIGHT +
                text + colorama.Style.RESET_ALL
            )
        self.log(text, *args)
        
    def exception(self, text, *args, **kwargs):
        """Log a line of text and information about an exception."""
        if 'exception' in kwargs:
            info = kwargs['exception']
        else:
            info = sys.exc_info()[-1]
        formatted = text % args if args else text
        self.error(formatted)
        self.log(traceback.format_exc(info))
    
    def confirm(self, text, *args):
        """
        Prompt the user for a yes or no response. Skip the prompt if the
        logger's "yes" flag was set.
        """
        if self.yes:
            return True
        else:
            formatted = text % args if args else text
            value = input(formatted + ' (y/n) ')
            return value == 'y' or value == 'Y'
