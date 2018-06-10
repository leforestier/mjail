from subprocess import check_call, check_output
import os
from tempfile import mkstemp

def cmd(*args, **kwargs):
    return check_call(args, **kwargs)
    
def output(*args, **kwargs):
    return check_output(args, **kwargs).decode('utf-8')
    
def to_tempfile(strg, prefix = None):
    handle, temp_path = mkstemp(prefix = prefix)
    os.write(handle, strg.encode('utf-8'))
    os.close(handle)
    return temp_path
    
def rc_conf_mod(strg, f = '/etc/rc.conf'):
    try:
        rc_conf = open(f).read()
    except FileNotFoundError:
        pass
    else:
        if not rc_conf.endswith('\n'):
            rc_conf += '\n'
            temp_path = to_tempfile(rc_conf, prefix = f)
            os.rename(temp_path, f)
    cmd('sysrc', '-f', f, strg)
    
