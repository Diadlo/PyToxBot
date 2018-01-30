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

import sys

from datetime import datetime
from generic_bot import GenericBot, ToxOptions, ToxServer
from os.path import exists
from time import time


BOT_START = time()


def get_uptime():
    current = time() - BOT_START
    secunds = current % 60
    current /= 60
    minutes = current % 60
    current /= 60
    hours = current % 60
    current /= 60
    days = current % 24
    return "%dd %dh %dm" % (days, hours, minutes)


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


class Message:
    def __init__(self, name, text):
        self.name = name
        self.date = time()
        self.text = text

    def __str__(self):
        date = datetime.fromtimestamp(self.date).strftime('%H:%M:%S')
        return "[%s] %s: %s" % (date, self.name, self.text)


class GroupBot(GenericBot):
    def __init__(self, profile, servers, opts=None):
        super(GroupBot, self).__init__('PyGroupBot', profile, servers, 'autoinvite.conf', opts)

        self.online_count = 0
        groupId = self.conference_new()
        self.groups = {groupId: ToxGroup(self, groupId)}
        # PK -> set(groupId)
        self.autoinvite = {}
        # groupId -> [messages]
        self.messages = {0: []}
        # PK -> time
        self.last_online = {}
        self.to_save = ['autoinvite']

        print('ID: %s' % self.self_get_address())

    def cmd_id(self, friendId):
        '''10 Print my Tox ID '''
        self.answer(friendId, self.self_get_address())

    def cmd_list(self, friendId):
        '''20 Print list all avaliable chats '''
        groups_info = [str(g) for (_, g) in self.groups.items()]
        text = '\n'.join(groups_info)
        self.answer(friendId, text)

    def cmd_info(self, friendId):
        '''30 Print my current status '''
        uptime = get_uptime()
        friend_count = self.self_get_friend_list_size()
        text = ('Uptime: %s\n'
                'Friends: %d (%d online)\n'
                % (uptime, friend_count, self.online_count))
        self.answer(friendId, text)

    def cmd_invite(self, friendId, groupId=0, password=''):
        '''40 Invite in chat with groupId. Default id is 0 '''
        groupId = int(groupId)
        group = self.groups[groupId]
        if password != group.password:
            self.answer(friendId, "Wrong password")
            return

        self.conference_invite(friendId, groupId)

    def cmd_group(self, friendId, password=''):
        '''50 Create new group '''
        groupId = self.conference_new()
        self.groups[groupId] = ToxGroup(self, groupId, password)
        self.conference_invite(friendId, groupId)

    def cmd_autoinvite(self, friendId, groupId=0, password=''):
        '''60 Autoinvite in group. Default id is 0, try without password '''
        groupId = int(groupId)
        group = self.groups[groupId]
        if password != group.password:
            self.answer(friendId, "Wrong password")
            return

        pk = self.friend_get_public_key(friendId)
        self.autoinvite[pk].add(groupId)
        self.conference_invite(friendId, groupId)

    def cmd_deautoinvite(self, friendId, groupId=0):
        '''70 Disable autoinvite in group. Default id is 0 '''
        groupId = int(groupId)
        pk = self.friend_get_public_key(friendId)
        self.autoinvite[pk].remove(groupId)

    def offline_messages(self, groupId, friendId, last_online):
        messages = self.messages[groupId]
        to_send = filter(lambda msg: msg.date > last_online, messages)
        self.answer(friendId, "Messages from your last visit:")
        for msg in to_send:
            self.answer(friendId, str(msg))

    def on_friend_quit(self, friendId):
        pk = self.friend_get_public_key(friendId)
        self.last_online[pk] = time()

    def on_friend_come(self, friendId):
        pk = self.friend_get_public_key(friendId)
        autoinvite_groups = self.autoinvite[pk]

        # Autohistory only for first group
        if 0 in autoinvite_groups:
            last_online = self.last_online.get(pk, -1)
            if last_online != -1:
                self.offline_messages(0, friendId, last_online)

        for groupId in autoinvite_groups:
            try:
                self.conference_invite(friendId, groupId)
            except:
                error = "Can't invite %d in group with id %d"
                print(error % (friendId, groupId))

    def on_friend_connection_status(self, friendId, online):
        pk = self.friend_get_public_key(friendId)
        if pk not in self.autoinvite:
            self.autoinvite[pk] = set()

        self.online_count += 1 if online else -1
        if online:
            self.on_friend_come(friendId)
        else:
            self.on_friend_quit(friendId)

    def on_friend_message(self, friendId, type, message):
        self.handle_command(friendId, type, message)

    def on_conference_message(self, groupId, peerId, type, message):
        name = self.conference_peer_get_name(groupId, peerId)
        msg = Message(name, message)
        self.messages[groupId].append(msg)

opts = ToxOptions()
opts.udp_enabled = True

profile = 'groupbot.tox'
if len(sys.argv) == 2:
    profile = sys.argv[1]

if exists(profile):
    opts.load_profile(profile)

servers = [
    ToxServer("biribiri.org",
    33445,
    "F404ABAA1C99A9D37D61AB54898F56793E1DEF8BD46B1038B9D822E8460FAB67"),
]

with GroupBot(profile, servers, opts) as t:
    t.start()
