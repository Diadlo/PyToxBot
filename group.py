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
from pytox import Tox
from os.path import exists
from time import time, gmtime


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
    def __init__(self, name, tox, groupId, password=''):
        self.name = name
        self.tox = tox
        self.groupId = groupId
        self.password = password

    def __str__(self):
        id = self.groupId
        type = 'T'
        peers = self.tox.conference_peer_count(id)
        title = self.tox.conference_get_title(id)
        template = '%s | %s(%d) | %s'
        return template % (self.name, type, peers, title)


class Message:
    def __init__(self, name, text):
        self.name = name
        self.date = time()
        self.text = text

    def __str__(self):
        t = gmtime(self.date)
        date = '%d:%d:%d' % (t.tm_hour, t.tm_min, t.tm_sec)
        return "[%s UTC] %s: %s" % (date, self.name, self.text)


class GroupBot(GenericBot):
    def __init__(self, profile, servers, opts=None):
        super(GroupBot, self).__init__('PyGroupBot', profile, servers, 'autoinvite.conf', opts)

        self.online_count = 0
        groupId = self.conference_new()
        self.groups = {'default': ToxGroup('default', self, groupId)}
        # PK -> set(groupname)
        self.autoinvite = {}
        # groupname -> [messages]
        self.messages = {'default': []}
        # PK -> time
        self.last_online = {}
        # PK -> groupname
        self.autohistory = {}
        # PK -> ToxGroup
        self.reserve = {}
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
        '''30 Print my current status and info '''
        uptime = get_uptime()
        friend_count = self.self_get_friend_list_size()
        text = ('Uptime: %s\n'
                'Friends: %d (%d online)\n'
                'Sources on GitHub: https://github.com/Diadlo/PyGroupBot\n'
                % (uptime, friend_count, self.online_count))
        self.answer(friendId, text)

    def cmd_invite(self, friendId, name, password=''):
        '''40 Invite in chat with groupId '''
        group = self.groups[name]
        groupId = group.groupId
        if password != group.password:
            self.answer(friendId, "Wrong password")
            return

        self.conference_invite(friendId, groupId)
        self.answer(friendId, 'You was invited to group "%s"' % name)

    def cmd_join(self, friendId, name, password=''):
        '''41 Same as 'invite' '''
        self.cmd_invite(friendId, name, password)

    def add_group(self, friendId, groupId, name, password):
        self.groups[name] = ToxGroup(name, self, groupId, password)
        self.messages[name] = []
        self.conference_invite(friendId, groupId)

    def cmd_group(self, friendId, name, password=''):
        '''50 Create new group with name '''
        if name in self.groups:
            self.answer(friendId, "Group with this name already exists")
            return

        groupId = self.conference_new()
        self.add_group(friendId, groupId, name, password)
        self.conference_set_title(groupId, name)
        self.answer(friendId, 'Group "%s" created' % name)

    def cmd_autoinvite(self, friendId, name, password=''):
        '''60 Autoinvite in group. Default try without password '''
        group = self.groups[name]
        groupId = group.groupId
        if password != group.password:
            self.answer(friendId, "Wrong password")
            return

        pk = self.friend_get_public_key(friendId)
        self.autoinvite[pk].add(name)
        self.conference_invite(friendId, groupId)
        self.answer(friendId, 'You will be autoinvited to group "%s" when you'
                'connect' % name)

    def cmd_deautoinvite(self, friendId, name):
        '''70 Disable autoinvite in group '''
        pk = self.friend_get_public_key(friendId)
        self.autoinvite[pk].remove(name)
        self.answer(friendId, 'Autoinvite for "%s" was disabled' % name)

    def cmd_log(self, friendId, name, count=100):
        '''80 Show *count* messages from chat. Default count is 100 '''
        # Last count messages
        start = -1 * int(count)
        messages = self.messages[name][start:]
        for msg in messages:
            self.answer(friendId, str(msg))

    def cmd_autohistory(self, friendId, name):
        '''90 Set group to automatically receive offline history '''
        pk = self.friend_get_public_key(friendId)
        self.autohistory[pk] = name
        self.answer(friendId, 'You will receive messages which was in "%s"'
                'chat since your last visit' % name)

    def cmd_deautohistory(self, friendId):
        '''100 Disable autohistory '''
        pk = self.friend_get_public_key(friendId)
        del self.autohistory[pk]
        self.answer(friendId, 'Autohistory for "%s" was disabled' % name)

    def cmd_reserve(self, friendId, name, password=''):
        '''110 Same as 'group' but instead of creation wait invite from you'''
        if name in self.groups:
            self.answer(friendId, "Group with this name already exists")
            return

        pk = self.friend_get_public_key(friendId)
        self.reserve[pk] = ToxGroup(name, self, -1, password)
        self.answer(friendId, 'Group "%s" reserved' % name)

    def offline_messages(self, groupname, friendId, last_online):
        messages = self.messages[groupname]
        to_send = filter(lambda msg: msg.date > last_online, messages)
        self.answer(friendId, "Messages from your last visit:")
        for msg in to_send:
            self.answer(friendId, str(msg))

    def on_friend_quit(self, friendId):
        pk = self.friend_get_public_key(friendId)
        self.last_online[pk] = time()

    def on_friend_come(self, friendId):
        pk = self.friend_get_public_key(friendId)

        # Autohistory only for first group
        if pk in self.autohistory:
            groupname = self.autohistory[pk]
            groupId = self.groups[groupname].groupId
            last_online = self.last_online.get(pk, -1)
            if last_online != -1:
                self.offline_messages(groupId, friendId, last_online)

        autoinvite_groups = self.autoinvite[pk]
        for groupname in autoinvite_groups:
            try:
                groupId = self.groups[groupname].groupId
                self.conference_invite(friendId, groupId)
            except:
                error = "Can't invite %d in group %s"
                print(error % (friendId, groupname))

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
        self.handle_command(friendId, message)

    def on_conference_message(self, groupId, peerId, type, msg_text):
        name = self.conference_peer_get_name(groupId, peerId)
        msg = Message(name, msg_text)

        groups = [g for g in self.groups.values() if g.groupId == groupId]
        if groups is not None:
            group_name = groups[0].name
            self.messages[group_name].append(msg)

        self.handle_gcommand(groupId, msg_text)

    def on_conference_invite(self, friendId, type, cookie):
        groupId = self.conference_join(friendId, cookie)
        pk = self.friend_get_public_key(friendId)
        g = self.reserve.get(pk)
        self.reserve[pk] = None
        if g is None:
            return

        self.add_group(friendId, groupId, g.name, g.password)

    def gcmd_id(self, groupId):
        id_text = self.self_get_address()
        self.ganswer(groupId, id_text)

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
