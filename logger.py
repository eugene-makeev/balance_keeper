import time

# duplication of print logging into file
import sys
from colors import COLORS

UNIX_NEWLINE = '\n'
WINDOWS_NEWLINE = '\r\n'
MAC_NEWLINE = '\r'

class Tee(object):
    def __init__(self, name, mode):
        self.file = open(name, mode)
        self.stdout = sys.stdout

    def __del__(self):
        self.close()

    def write(self, data):
        if data != UNIX_NEWLINE and data != WINDOWS_NEWLINE and data != MAC_NEWLINE:
            append_time = 'GMT ' + time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time())) + ': '
        else:
            append_time = ''
        self.stdout.write(append_time + data)
        # TODO: optimize remove coloring
        for color in COLORS:
            data = data.replace(color, '')
        self.file.write(append_time + data)
        

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        if sys.stdout is self:
            sys.stdout = self.stdout
        self.file.close()

sys.stdout = Tee('balance_keeper_log.txt', 'a')
