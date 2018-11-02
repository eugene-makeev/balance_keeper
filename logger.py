import time

# duplication of print logging into file
import sys
from colors import COLORS

UNIX_NEWLINE = '\n'
WINDOWS_NEWLINE = '\r\n'
MAC_NEWLINE = '\r'

g_new_line = True

class Tee(object):
    def __init__(self, name, mode):
        self.file = open(name, mode)
        self.stdout = sys.stdout

    def __del__(self):
        self.close()

    def write(self, data):
        global g_new_line
        append_time = ''
        # print once on new line
        if data == UNIX_NEWLINE or data == WINDOWS_NEWLINE or data == MAC_NEWLINE:
            g_new_line = True
        elif g_new_line:
            append_time = 'GMT ' + time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time())) + ': '
            g_new_line = False

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
