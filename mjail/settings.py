import os

def cloned_if():
    return os.environ.get('MJAIL_CLONED_IF', 'lo8')
