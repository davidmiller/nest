"""
=======
nest.py
=======

Wherein we manipulate particular "nest" of python packages in a
particular virtualenv-ed environment.

>>> nest = Nest(path="/tmp/foo-env")
>>> nest.lay_eggs("requirements.txt")
>>> with nest.path_munging():
>>>     pass
"""
import contextlib
import os
import shlex
import subprocess
import sys
import uuid

import virtualenv
from fabric import operations
from fabric import api as fab
from fabric.contrib import files

def _venv_file():
    """
    Return the Virtualenv.py file.
    """
    if virtualenv.__file__.endswith('c'):
        return virtualenv.__file__[:-1]
    return virtualenv.__file__

def isvenv(path):
    """
    Boolean check to see if `path` is a virtualenv.
    """
    abspath = os.path.abspath(path)
    if not os.path.exists(abspath):
        return False
    contents = os.listdir(abspath)
    contents.sort()
    if contents == ["bin", "include", "lib", "local"]:
        return True
    return False

def build_nest(path, **kwargs):
    """
    Build a "nest" (Virtualenv) at `path`

    Arguments:
    - `path`: string
    """
    abspath = os.path.abspath(path)
    virtualenv.create_environment(abspath, **kwargs)
    return

class Nest(object):
    "A nest of Python packages !"

    def __init__(self, path=None, extra_paths=[]):
        self.path = os.path.abspath(path)
        self.extra_paths = extra_paths
        self.pip = os.path.join(self.path, "bin/pip")
        version_str = "%s.%s" % (sys.version_info.major, sys.version_info.minor)
        site_dir = os.path.join(self.path,
                                "lib/python%s/site-packages" % version_str)
        self.site_packages = site_dir

    def lay_eggs(self, requirements_file):
        """
        Lay the Python packges named in `requirements_file`.

        Arguments:
        - `requirements_file`: str
        """
        requirements = os.path.abspath(requirements_file)
        if not isvenv(self.path):
            build_nest(self.path)
        cmd = shlex.split("%s install -r %s" % (self.pip, requirements))
        pip = subprocess.Popen(cmd)
        pip.wait()
        return

    @contextlib.contextmanager
    def path_munging(self):
        """
        Contextmanager that allows us to execute the code
        contained within it using this nest
        """
        oldpath = sys.path
        try:
            print "Apply Nest"
            for path in self.extra_paths:
                sys.path.insert(0, path)
            sys.path.insert(0, self.site_packages)
            yield
        finally:
            print "Unapply Nest"
            sys.path = oldpath

class RemoteNest(object):
    """
    Make a Nest on a remote machine
    """

    def __init__(self, host, user, path, python=None):
        """
        Set attrs
        """
        self.host = host
        self.user = user
        self.host_string = '{0}@{1}'.format(host, user)
        self.path = path
        self.venv_name = uuid.uuid1()
        self.venv_path = os.path.join(path, self.venv_name)
        self.remote_venv_file = os.path.join(self.path, 'virtualenv.py')
        self.remote_pip = os.path.join(self.venv_path, 'bin/pip')
        self.remote_python = os.path.join(self.venv_path, 'bin/python')
        self.remote_activate = os.path.join(self.venv_path, 'bin/activate')
        self.python = python

    @contextlib.contextmanager
    def as_host(self):
        """
        A contextmanager that allows us to set this
        server's host as the active Fabric host, thus utilizing the pleasant
        Fabric API for remote SSH tasks

        >>> nest = RemoteNest("example.com", 8080)
        >>> with nest.as_host():
        >>>     print fab.env['host_string']
        ... example.com
        """
        host_string = fab.env.host_string
        fab.env.host_string = self.host_string
        try:
            yield
        finally:
            fab.env.host_string = host_string

    def isvenv(self):
        """
        Is the remote path a virtualenv already?
        """
        with self.as_host():
            return files.exists(self.remote_activate) and \
              files.exists(self.remote_pip) and \
              files.exists(self.remote_python)

    def build(self):
        """
        Build the remote nest.
        """
        with self.as_host():
            if not files.exists(self.path):
                fab.run('mkdir -p {0}'.format(self.path))

            operations.put(_venv_file(), self.remote_venv_file)
            if not self.python:
                self.python = fab.run('which python')

            fab.run('{python} {venv} --no-site-packages {name}'.format(
                python=self.python, venv=self.remote_venv_file, name=self.venv_name))

    def lay_eggs(self, requirements_file):
        """
        Lay the Python packges named in `requirements_file`.

        Arguments:
        - `requirements_file`: str
        """
        if not self.isvenv():
            self.build()

        installcmd = [
            self.remote_pip,
            'install'
            ] + open(os.path.abspath(requirements_file)).readlines()

        fab.run(" ".join(installcmd))

