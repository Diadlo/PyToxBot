#
# Copyright (C) 2017 Polshakov Dmitry (Diadlo) <polsha3@gmail.com>
# All Rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

import pickle
import random
import sys
from pytox import Tox

from time import sleep
from os.path import exists


class ToxServer():
    def __init__(self, ip, port, pk):
        self.ip = ip
        self.port = port
        self.pk = pk

class ToxOptions():
    def __init__(self):
        self.ipv6_enabled = True
        self.udp_enabled = True
        self.proxy_type = 0  # 1=http, 2=socks
        self.proxy_host = ''
        self.proxy_port = 0
        self.start_port = 0
        self.end_port = 0
        self.tcp_port = 0
        self.savedata_type = 0  # 1=toxsave, 2=secretkey
        self.savedata_data = b''
        self.savedata_length = 0

    def load_profile(self, profile):
        self.savedata_data = open(profile, 'rb').read()
        self.savedata_length = len(self.savedata_data)
        self.savedata_type = Tox.SAVEDATA_TYPE_TOX_SAVE

class GenericBot(Tox):
    def __init__(self, name, profile, servers, config_name, opts=None):
        if opts is not None:
            super(GenericBot, self).__init__(opts)

        self.profile = profile
        self.servers = servers
        self.to_save = []
        self.config_name = config_name
        self.self_set_name(name)
        self.connect()

    def __enter__(self):
        self.load_settings(self.config_name)
        return self

    def __exit__(self, type, value, traceback):
        self.save_settings(self.config_name)

    def save_settings(self, conf):
        with open(conf, 'wb') as f:
            for save in self.to_save:
                pickle.dump(getattr(self, save), f)

    def load_settings(self, conf):
        if not exists(conf):
            return

        with open(conf, 'rb') as f:
            for save in self.to_save:
                setattr(self, save, pickle.load(f))

    def save_profile(self):
        with open(self.profile, 'wb') as f:
            f.write(self.get_savedata())

    def connect(self):
        server = random.choice(self.servers)
        self.bootstrap(server.ip, server.port, server.pk)

    def start(self):
        checked = False
        self.save_profile()

        try:
            while True:
                status = self.self_get_connection_status()

                if not checked and status:
                    print('Connected to DHT.')
                    checked = True

                if checked and not status:
                    print('Disconnected from DHT.')
                    self.connect()
                    checked = False

                self.iterate()
                sleep(0.01)
        except KeyboardInterrupt:
            self.save_profile()

    def on_friend_request(self, pk, message):
        self.friend_add_norequest(pk)
        self.save_profile()

    def answer(self, friendId, text):
        self.friend_send_message(friendId, Tox.MESSAGE_TYPE_NORMAL, text)
