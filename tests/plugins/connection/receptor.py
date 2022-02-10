# (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
# (c) 2015, 2017 Toshio Kuratomi <tkuratomi@ansible.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

import os
import pty
import shutil
import subprocess
import fcntl
import getpass
import json

import ansible.constants as C
from ansible.errors import AnsibleError, AnsibleFileNotFound
from ansible.module_utils.compat import selectors
from ansible.module_utils.six import text_type, binary_type
from ansible.module_utils._text import to_bytes, to_native, to_text
from ansible.plugins.connection import ConnectionBase
from ansible.utils.display import Display
from ansible.utils.path import unfrackpath

from receptorctl.socket_interface import ReceptorControl

display = Display()

__metaclass__ = type

DOCUMENTATION = """
    name: receptor
    short_description: receptor
    description:
        - Use receptor as the connection transport
    author:
    version_added:
    notes:
        - Everything is ignored
"""


class Connection(ConnectionBase):

    transport = "receptor"

    def __init__(self, *args, **kwargs):

        super(Connection, self).__init__(*args, **kwargs)
        self.cwd = None
        self.default_user = getpass.getuser()

    def _connect(self):

        # Because we haven't made any remote connection we're running as
        # the local user, rather than as whatever is configured in remote_user.
        self._play_context.remote_user = self.default_user

        if not self._connected:
            display.vvv(
                "ESTABLISH RECEPTOR CONNECTION FOR USER: {0}".format(
                    self._play_context.remote_user
                ),
                host=self._play_context.remote_addr,
            )
            self._connected = True
        return self

    def exec_command(self, cmd, in_data=None, sudoable=True):
        """run a command on the local host"""

        super(Connection, self).exec_command(cmd, in_data=in_data, sudoable=sudoable)
        display.vvv("RECEPTOR: EXEC {0}".format(cmd))

        # Based on reverse engineering the remote protocol these following
        # commands that are executed.  It would be nice if these were
        # functions in the plugin spec so I didn't have to do this.
        if cmd == "/bin/sh -c 'echo ~{0} && sleep 0'".format(
            self._play_context.remote_user
        ):
            return (0, self.get_home_directory(), "")
        elif cmd == "/bin/sh -c 'echo \"`pwd`\" && sleep 0'":
            return (0, self.get_cwd(), "")
        elif cmd.startswith('/bin/sh -c \'( umask 77 && mkdir -p'):
            return (0, self.create_temp_dir(cmd), "")
        elif cmd.startswith("/bin/sh -c 'echo PLATFORM"):
            return (0, self.discover_platform(), "")
        elif "AnsiballZ" in cmd:
            return (0, self.run_ansiball(cmd), '')
        return (0, "", "")

    def get_home_directory(self):
        display.vvv("get_home_directory")
        return os.path.expanduser("~")

    def get_cwd(self):
        display.vvv("get_cwd")
        return os.get_cwd()

    def create_temp_dir(self, cmd):
        display.vvv("create_temp_dir")
        return subprocess.check_output(cmd, shell=True)

    def discover_platform(self):
        display.vvv("discover_platform")
        return b'PLATFORM\nLinux\nFOUND\n/home/ben/venv/ansible/bin/python3.9\n/usr/bin/python3.8\n/usr/bin/python3\n/usr/bin/python2.7\n/usr/bin/python\n/home/ben/venv/ansible/bin/python\nENDFOUND\n'

    def run_ansiball(self, cmd):
        '''return stdout=hello because this connection plugin does nothing'''
        display.vvv("run_ansiball")
        display.vvv("connecting to receptor")
        rc = ReceptorControl('/tmp/foo.sock')
        display.vvv("submitting work")
        with open('/tmp/AnsiballZ.py') as f:
            result = rc.submit_work('ansible-local', f.read(), node=self._play_context.remote_addr)
        display.vvv("waiting for results")
        resultsfile = rc.get_work_results(result['unitid'])
        return resultsfile.read()

    def put_file(self, in_path, out_path):
        """transfer a file from local to local"""

        super(Connection, self).put_file(in_path, out_path)
        display.vvv(u"PUT {0} TO {1}".format(in_path, out_path), host=self._play_context.remote_addr)
        # Save the ansiball for inspection
        shutil.copy(in_path, '/tmp/AnsiballZ.py')

    def fetch_file(self, in_path, out_path):
        """fetch a file from local to local -- for compatibility"""

        super(Connection, self).fetch_file(in_path, out_path)
        display.vvv(u"FETCH {0} TO {1}".format(in_path, out_path), host=self._play_context.remote_addr)

    def close(self):
        """terminate the connection; nothing to do here"""
        self._connected = False
