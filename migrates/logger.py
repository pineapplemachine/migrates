"""
This module implements the logger used by migrates.
"""

import os, sys, traceback, time, datetime

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
    
    def __init__(self, path=None, verbose=False, quiet=False, silent=False, yes=False):
        self.verbose = verbose
        self.quiet = quiet
        self.silent = silent
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
    
    def show(self, stdout, text, *args):
        """Log a line of text."""
        stdout = stdout and not self.silent
        if stdout or self.output_file is not None:
            formatted = text % args if args else text
        if stdout:
            print(formatted)
        if self.output_file is not None:
            self.output_file.write(formatted)
            self.output_file.write('\n')
        
    def log(self, text, *args):
        """Log a line of text."""
        self.show(not self.quiet, text, *args)
    
    def debug(self, text, *args):
        """
        Log a line of text meant to communicate something trivial, but only
        if the logger is set to log verbosely.
        """
        if self.verbose:
            if colors:
                text = colorama.Fore.CYAN + text + colorama.Style.RESET_ALL
            self.show(not self.quiet, text, *args)
    
    def error(self, text, *args):
        """Log a line of text meant to communicate an error."""
        if colors:
            text = (
                colorama.Fore.RED + colorama.Style.BRIGHT +
                text + colorama.Style.RESET_ALL
            )
        self.show(True, text, *args)
    
    def important(self, text, *args):
        """Log a line of text meant to communicate something very important."""
        if colors:
            text = (
                colorama.Fore.YELLOW + colorama.Style.BRIGHT +
                text + colorama.Style.RESET_ALL
            )
        self.show(True, text, *args)
        
    def exception(self, text, *args, **kwargs):
        """Log a line of text and information about an exception."""
        if 'exception' in kwargs:
            info = kwargs['exception']
        else:
            info = sys.exc_info()[-1]
        formatted = text % args if args else text
        self.error(formatted)
        self.show(True, traceback.format_exc(info))
    
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
    
    def wait(self, seconds):
        """Wait for a given number of seconds."""
        if self.quiet or self.silent:
            time.sleep(seconds)
        else:
            print('Waiting for %d seconds...' % seconds)
            step = max(1, seconds // 10)
            left = seconds % step
            for _ in range(seconds // step):
                sys.stdout.write('.')
                sys.stdout.flush()
                time.sleep(step)
            time.sleep(left)
            sys.stdout.write('\n')
            sys.stdout.flush()
