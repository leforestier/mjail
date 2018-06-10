import jailconf

def get_jail_conf():
    try:
        return jailconf.load('/etc/jail.conf')
    except FileNotFoundError:
        raise Exception("No /etc/jail.conf. You need to run `mjail init`.")
        

