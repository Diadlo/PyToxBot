#
# @file   echo.py
# @author Polshakov Dmitry (Diadlo) <polsha3@gmail.com>
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
import sys
from pytox import Tox

from time import sleep
from os.path import exists

SERVER = [
    "192.210.149.121",
    33445,
    "F404ABAA1C99A9D37D61AB54898F56793E1DEF8BD46B1038B9D822E8460FAB67"
]

DATA = 'groupbot.tox'

# echo.py features
# - accept friend request
# - echo back friend message
# - accept and answer friend call request
# - send back friend audio/video data
# - send back files friend sent

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


def save_to_file(tox, fname):
    data = tox.get_savedata()
    with open(fname, 'wb') as f:
        f.write(data)


def load_from_file(fname):
    return open(fname, 'rb').read()


class GenericBot(Tox):
    def __init__(self, name, opts=None):
        if opts is not None:
            super(GenericBot, self).__init__(opts)

        self.self_set_name(name)
        self.connect()

    def connect(self):
        self.bootstrap(SERVER[0], SERVER[1], SERVER[2])

    def start(self):
        checked = False
        save_to_file(self, DATA)

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
            save_to_file(self, DATA)

    def on_friend_request(self, pk, message):
        self.friend_add_norequest(pk)
        save_to_file(self, DATA)

class ToxGroup():
    def __init__(self, tox, groupId, password=''):
        self.tox = tox
        self.groupId = groupId
        self.password = password

    def __str__(self):
        id = self.groupId
        type = 'Text'
        peers = self.tox.conference_peer_count(id)
        title = self.tox.conference_get_title(id)
        res = 'Group %d | %s | Peers: %d | Title: %s' % (id, type, peers, title)
        return res

_AUTOINVITE_ = 'autoinvite.conf'

class GroupBot(GenericBot):
    def __init__(self, opts=None):
        super(GroupBot, self).__init__('PyGroupBot', opts)

        groupId = self.conference_new()
        self.groups = { groupId: ToxGroup(self, groupId) }
        # PK -> set(groupId)
        self.autoinvite = {}
        self.load_settings(_AUTOINVITE_)

        print('ID: %s' % self.self_get_address())

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.save_settings(_AUTOINVITE_)

    def save_settings(self, conf):
        with open(conf, 'wb') as f:
            pickle.dump(self.autoinvite, f)

    def load_settings(self, conf):
        try:
            with open(conf, 'rb') as f:
                self.autoinvite = pickle.load(f)
        except:
            pass

    def answer(self, friendId, text):
        self.friend_send_message(friendId, Tox.MESSAGE_TYPE_NORMAL, text)

    def cmd_help(self, id):
        self.answer(id, '''Usage:
    help : Print this text
    list : Print list all avaliable chats
    invite [<groupId> [<password>]] : Invite in chat with groupId. Default id is 0
    group : Create new group
    autoinvite [<groupId> [<password>]] : Autoinvite in group. Default id is 0
    deautoinvite [<groupId>] : Disable autoinvite in group. Default id is 0
''')

    def cmd_group(self, friendId, password=''):
        groupId = self.conference_new()
        self.groups[groupId] = ToxGroup(self, groupId, password)
        self.conference_invite(friendId, groupId)

    def cmd_invite(self, friendId, groupId=0, password=''):
        groupId = int(groupId)
        group = self.groups[groupId]
        if password != group.password:
            self.answer(friendId, "Wrong password")
            return

        self.conference_invite(friendId, groupId)

    def cmd_list(self, friendId):
        groups_info = [str(g) for (_, g) in self.groups.items()]
        text = '\n'.join(groups_info)
        self.answer(friendId, text);

    def cmd_autoinvite(self, friendId, groupId=0, password=''):
        groupId = int(groupId)
        group = self.groups[groupId]
        if password != group.password:
            self.answer(friendId, "Wrong password")
            return
            
        pk = self.friend_get_public_key(friendId)
        self.autoinvite[pk].add(groupId)
        self.conference_invite(friendId, groupId)

    def cmd_deautoinvite(self, friendId, groupId=0):
        groupId = int(groupId)
        pk = self.friend_get_public_key(friendId)
        self.autoinvite[pk].remove(groupId)

    def on_friend_connection_status(self, friendId, status):
        pk = self.friend_get_public_key(friendId)
        if pk not in self.autoinvite:
            self.autoinvite[pk] = set()

        if not status:
            return

        groups = self.autoinvite[pk]
        for groupId in groups:
            try:
                self.conference_invite(friendId, groupId)
            except:
                print("Can't invite %d in group with id %d" % friendId, groupId)

    def on_friend_message(self, friendId, type, message):
        name = self.friend_get_name(friendId)
        temp = message.split(' ')
        name = temp[0]
        params = temp[1:]

        try:
            method = getattr(self, 'cmd_' + name)
        except AttributeError:
            self.answer(friendId, '%s is unsupported command' % name)
            self.cmd_help(friendId)
            return

        try:
            method(friendId, *params)
        except:
            self.answer(friendId, 'Error while handle %s' % name)

opts = None
opts = ToxOptions()
opts.udp_enabled = True

if len(sys.argv) == 2:
    DATA = sys.argv[1]

if exists(DATA):
    opts.savedata_data = load_from_file(DATA)
    opts.savedata_length = len(opts.savedata_data)
    opts.savedata_type = Tox.SAVEDATA_TYPE_TOX_SAVE

with GroupBot(opts) as t:
    t.start()
