-----
mjail
-----

*mjail* is a command line tool to create and manage jails on FreeBSD.

With *mjail*, you can create a jail in a single command and have a virtual machine ready to work with. 

For example, you can use *mjail* to create multiple independant ssh boxes on your remote server, and then be able to access them from your laptop, in the same way you'd access any Unix host, using ssh and a private key. 

*mjail* integrates with the *pf* firewall to allow quick management of port redirections to the jails.

*mjail* relies on ``jail.conf`` and so is compatible with the newest versions of FreeBSD. 

--------
Features
--------

Each of these features can be achieved by issuing a single `mjail` command.

- create a jail with an ip address on a virtual interface of the host
- create a jail that is accessible from the internet via ssh and a private key
- start/stop a jail
- delete a jail
- start a shell inside a jail
- update the base system of a jail
- redirect any internet facing port of the host to a port of a jail


*mjail* is a work in progress and, although I've been using it for my personal use for a few years, the project is still at its beginning and lacks some important features.

--------------------
Features coming soon
--------------------

(`help if you can!
<https://github.com/leforestier/mjail>`_)

- IPv6 support: this is the priority. For now the jail network on the host is IPv4 only.
- have a special jail that would act as a pkg mirror and/or a ports mirror (currently, jails manage their packages and ports in a totally independant way, I want to keep it that way while avoiding unnessary downloads from the FreeBSD infrastructure).
- zfs: mjail takes no advantage of zfs. To create jails, it just recursively copies directory trees from the file system. It would be good to have the possibility to use zfs to create and/or make snapshots of jails. I just don't jave the zfs knowledge required to do that at the moment.

-------------
Installation
-------------

You need to have the *pf* firewall and the *local_unbound* local DNS server enabled. Two simple commands will ensure this is the case. Run, as root:


.. code::

    sysrc pf_enable=YES
    sysrc local_unbound_enable=YES

(the mjail initialization described in the next section will start these services if they aren't already running on your system, so don't worry about that)

Then install *py36-pip*, which is the python module manager for python 3 (here for python 3.6, but you can also use *py35-pip* if you prefer, any pip for Python version 3.5 or superior will work). Run, as root:

.. code::

    pkg install py36-pip

Finally you can install mjail. Run, as root:

.. code::
    
    pip-3.6 install mjail
    
---------------
Initialization
---------------

Before creating your first jail, you must initialize your system. This is a simple command. Run as root:

.. code::

   mjail init
    
This will, among other things, create a local virtual network interface ``lo8`` on your host for use by the jails.
By default, the ``10.240.0.0/12`` ip range is used for the jails.
If for some reason you want to use a different ip range, you can specify it using the ``--ip4-network`` option.

The preceding command was equivalent to:

.. code::
    
    mjail init --ip4-network 10.240.0.0/12
    
*mjail* doesn't deal with IPv6 at the moment, but this should be implemented soon.
    
-----------------------------
Jails creation and management
-----------------------------

Create a jail
--------------

.. code::

    mjail create cooljail

This automatically gives this jail an ip address and it automatically starts the jail. The name of this jail is "cooljail". You will be able to use this name later on to stop the jail, start it or delete it for example. This is also the hostname of the jail.

You can check the list of jails that are currently running:

.. code::

    jls

    JID  IP Address      Hostname                      Path
    2   10.240.0.2       cooljail                     /var/mjail/instances/cooljail

If you don't want the jail to start immediately, use the ``--no-start`` option:

.. code:: sh

    mjail create cooljail --no-start
    
Stop a jail
------------

.. code::

    mjail stop cooljail
    
Delete a jail
--------------

.. code::

    mjail delete uncooljail
    
Start a jail
------------

If you have stopped a jail, or if you have created one using the ``--no-start`` option, your jail isn't running. Sad! To start it, run:

.. code::

    mjail start cooljail
    
Execute a command inside a jail
-------------------------------

.. code::

    mjail exec <jail_name> <command> [<arguments>...]
    
For example:

.. code::

    mjail exec cooljail cat /var/log/nginx/access.log
    

Start a shell inside the jail
------------------------------

.. code::

    # mjail shell cooljail
    
    root@cooljail:/ # echo "I'm inside the jail"
    I'm inside the jail

    
Create a jail that's accessible via ssh
---------------------------------------

For that you'll need a public/private ssh key pair. If you don't have one already, you can create one using the  following command (run this on your laptop, not on the remote server, as private keys shouldn't be stored on the server you want to access):

.. code:: sh

    $ ssh-keygen -f my-cool-key
    
You'll get two files. The private key is contained in ``my-cool-key`` and the public key is contained in ``my-cool-key.pub``.

.. code:: sh

    $ cat my-coolkey.pub
    
    ssh-rsa AAAAB3N...G7xAQt4LpCaEh/D+UpoChnJOXKV9 user@host
    

Assuming your public key looks like this,

.. code::

    MY_PUBLIC_KEY='ssh-rsa AAAAB3N...G7xAQt4LpCaEh/D+UpoChnJOXKV9 user@host'

you can create a jail that's accessible via ssh over a port of your choice issuing this single command:

.. code::

    # mjail create cooljail --ssh-box "$MY_PUBLIC_KEY" port 4444
    
**Important warning: don't choose the same ssh port as the port of the host or you'll be into trouble: you'd lose access to the host.**
    
Note that the jail is not facing the internet directly. `mjail` just instructs the `pf` firewall to redirect the ssh traffic over the port of your choice to the ssh daemon running inside the jail.
    
Then you can access your jail just like it was a new dedicated server.

.. code::

    ssh -p 4444 root@xx.xx.xx.xx
    
where xx.xx.xx.xx is the ip address of your host.

That's assuming you've added your ssh private key to the ssh-agent on your laptop using ``ssh-add``.
If not, just use:

.. code::

    ssh -i /path/to/my-cool-key -p 4444 root@xx.xx.xx.xx
    

Adding ssh access to a jail
----------------------------

If you created a jail using a simple ``mjail create myjail`` command, it has no ssh daemon running and you can't access it using ssh. To enable ssh access to the jail from the internet, use:

.. code::

    mjail set-up-sshd <jail_name> <public_key> port <host_port>
    
where:
    - ``<jail_name>`` is, well, the name of the jail
    - ``<public_key>`` is your public key as a string (for example ``'ssh-rsa AAAAB3N...G7xAQt4LpCaEh/D+UpoChnJOXKV9 user@host'``). If you generated your key using ``ssh-keygen`` it's the content of your ``key.pub`` file.
    - ``<host_port>``: the port of the host that you will connect to in order to connect to the ssh-daemon of the jail. Use a non common port, for exemple 4444. **Never use the same ssh port as the ssh port of the host or you'll lose ssh access to the host**.
    

Redirect an internet facing port from the host to a jail
--------------------------------------------------------

Jails created with `mjail` never face the internet directly. They have an ip on a local, virtual network interface, inside the host.
So how can you, say, run an internet server, such as Apache or Nginx inside a jail and access it from the internet?

By redirecting traffic from a port of the host to a port of the jail.

This is done with a simple command. Say you're running Nginx on port 80 inside your jail and you want Nginx to be accessible from the internet. You want to redirect the host's incoming traffic on port 80 to the port 80 of the jail.
This can be done using the command:

.. code::

    mjail rdr tcp 80 to cooljail 80
    
The general form of this command is 

.. code::

    mjail rdr (tcp|udp) <internet_facing_host_port> to <jail_name> <jail_port>
    
Of course, the ports don't need to be the same on the host and on the jail. If, for example, inside the jail you're running a Tornado web application on port 8080 and want to make it public on port 80 of the host, you'd issue a:

.. code::

    mjail rdr tcp 80 to cooljail 8080
    
You can cancel the redirection by running:

.. code::

    mjail cancel-rdr tcp 80
    
Packages
---------

Use the `pkg` command inside the jail to install packages. There is no difference with what you'd do if you weren't inside a jail. Each jail manages its own packages. So, you can for example, spawn a shell inside your jail, or connect to your jail using ssh, and then install the packages you want.

This way, when you develop scripts that install packages, you don't have to worry about your script running inside a jail or not.


Base system updates
-------------------

Base system updates have to be done from outside the jail.

To update the base system of a jail with the latest security patches:

.. code::

    mjail freebsd-update <jail_name>
    
Sometimes, it's required to upgrade to a new FreeBSD version because the one you're running no longer receives security patches. You can do that with:

.. code::
    
    mjail freebsd-update <jail_name> -r <to_version>
    
For example, if your jail is running FreeBSD 11.1, you can upgrade to 11.2

.. code::

    mjail freebsd-update cooljail -r 11.2

Only minor upgrades are supported (ie version 11.1 to 11.2, but not 11.x to 12.x) and even these haven't been thorougly tested at the moment. So, please regard it as an experimental feature.

-----------
GitHub repo
-----------

https://github.com/leforestier/mjail
