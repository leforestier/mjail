import re
import os
from mjail.cmd_helpers import to_tempfile

class SSHDConf(object):
    def __init__(self, path):
        self._lines = list(map(str.rstrip, open(path).readlines()))
        self._path = path
        
    def set_option(self, option, value):
        rgx = re.compile('^(?P<comment>#?)\s*%s\s+(?P<value>.*)$' % option)
        correct_line = "%s %s" % (option, value)
        def match_line(line):
            mobj = rgx.match(line)
            if mobj:
                return True, correct_line
            else:
                return False, line
        present = False
        for i, line in enumerate(self._lines):
            match, new_line = match_line(line)
            present = present or match
            if match:
                self._lines[i] = new_line
        if not present:
            self._lines.append(correct_line)
            
    def get(self, option, default = None):
        rgx = re.compile('^%s\s+(.*)$' % option)
        for line in self._lines:
            mobj = rgx.match(line)
            if mobj:
                return mobj.group(1)
        return default
            

    def __str__(self):
        return '\n'.join(self._lines)
        
    def overwrite(self):
        temp_path = to_tempfile(str(self), prefix = self._path)
        os.rename(temp_path, self._path)
        
    
    
