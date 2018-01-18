#
# @file   group.py
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

import inspect
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
        template = 'Group %d | %s | Peers: %d | Title: %s'
        return template % (id, type, peers, title)


class CommandInfo():
    def __init__(self, object, func):
        # Remove 'cmd_'
        self.name = func[4:]

        cmd = getattr(object, func)
        doc = cmd.__doc__
        if doc is None:
            doc = ''

        temp = doc.split(' ', 1)
        try:
            self._order = int(temp[0])
            self.doc = temp[1].strip()
        except:
            self._order = 0
            self.doc = doc.strip()

        # Skip 'self' and 'friendId'
        self.vars = inspect.getargspec(cmd)[0][2:]

    def order(self):
        return self._order

    def __str__(self):
        vars = ''
        for v in vars:
            vars += '<%s> ' % v

        return '%s%s : %s' % (self.name, vars, self.doc)


class GroupBot(GenericBot):
    def __init__(self, profile, servers, opts=None):
        super(GroupBot, self).__init__('PyGroupBot', profile, servers, 'autoinvite.conf', opts)

        groupId = self.conference_new()
        self.groups = {groupId: ToxGroup(self, groupId)}
        # PK -> set(groupId)
        self.autoinvite = {}
        self.to_save = ['autoinvite']

        print('ID: %s' % self.self_get_address())

    def cmd_id(self, friendId):
        '''1 Print my Tox ID '''
        self.answer(friendId, self.self_get_address())

    def cmd_list(self, friendId):
        '''2 Print list all avaliable chats '''
        groups_info = [str(g) for (_, g) in self.groups.items()]
        text = '\n'.join(groups_info)
        self.answer(friendId, text)

    def cmd_help(self, friendId):
        '''3 Print this text '''
        functions = filter(lambda s: s.startswith('cmd_'), dir(self))
        commands = []
        for f in functions:
            commands.append(CommandInfo(self, f))

        commands.sort(key=CommandInfo.order)
        text = 'Usage:\n'
        for cmd in commands:
            text += '   %s\n' % str(cmd)

        self.answer(friendId, text)

    def cmd_invite(self, friendId, groupId=0, password=''):
        '''4 Invite in chat with groupId. Default id is 0 '''
        groupId = int(groupId)
        group = self.groups[groupId]
        if password != group.password:
            self.answer(friendId, "Wrong password")
            return

        self.conference_invite(friendId, groupId)

    def cmd_group(self, friendId, password=''):
        '''5 Create new group '''
        groupId = self.conference_new()
        self.groups[groupId] = ToxGroup(self, groupId, password)
        self.conference_invite(friendId, groupId)

    def cmd_autoinvite(self, friendId, groupId=0, password=''):
        '''6 Autoinvite in group. Default id is 0, try without password '''
        groupId = int(groupId)
        group = self.groups[groupId]
        if password != group.password:
            self.answer(friendId, "Wrong password")
            return

        pk = self.friend_get_public_key(friendId)
        self.autoinvite[pk].add(groupId)
        self.conference_invite(friendId, groupId)

    def cmd_deautoinvite(self, friendId, groupId=0):
        '''7 Disable autoinvite in group. Default id is 0 '''
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
                error = "Can't invite %d in group with id %d"
                print(error % (friendId, groupId))

    def on_friend_message(self, friendId, type, message):
        temp = message.split(' ')
        name = temp[0]
        params = temp[1:]

        try:
            method = getattr(self, 'cmd_' + name)
        except AttributeError:
            try:
                self.answer(friendId, '%s is unsupported command' % name)
                self.cmd_help(friendId)
            except Exception as e:
                print(str(e))
            finally:
                return

        try:
            method(friendId, *params)
        except Exception as e:
            error = 'Error while handle %s (%s)' % (name, str(e))
            self.answer(friendId, error)

opts = None
opts = ToxOptions()
opts.udp_enabled = True

profile = 'groupbot.tox'
if len(sys.argv) == 2:
    profile = sys.argv[1]

if exists(profile):
    opts.savedata_data = open(profile, 'rb').read()
    opts.savedata_length = len(opts.savedata_data)
    opts.savedata_type = Tox.SAVEDATA_TYPE_TOX_SAVE

servers = [
    ToxServer("192.210.149.121", 33445, "F404ABAA1C99A9D37D61AB54898F56793E1DEF8BD46B1038B9D822E8460FAB67")
]

with GroupBot(profile, servers, opts) as t:
    t.start()
