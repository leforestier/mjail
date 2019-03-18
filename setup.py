from setuptools import setup

with open('README.rst') as fd:
    long_description = fd.read()

setup(
    name='mjail',
    version='0.1.1',
    install_requires = ['docopt>=0.6.2', 'jailconf>=0.2.0'],
    packages=['mjail'],
    scripts=['bin/mjail'],
    author = 'Benjamin Le Forestier',
    author_email = 'benjamin@leforestier.org',
    url = 'https://github.com/leforestier/mjail',
    keywords = ["jail", "freebsd", "jail.conf"],
    description = "Minimalist command line tool to manage FreeBSD jails",
    long_description = long_description,
    classifiers = [
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5', # required for the IpV4Network constructor
        'Programming Language :: Python :: 3.6',
        'Operating System :: POSIX :: BSD :: FreeBSD',
        'Topic :: System :: Operating System',
        'Topic :: System :: Systems Administration'
       
    ]  
)
