PyToxBot
========

This repo contains generic tox bot implementation, which hepls create new bots.

Also contains some bots that use this implementation.

GroupBot
--------

GroupoBot supports next features:

* create a group with name and with password
* show list of all groups
* show log from chat
* register existing group (using reserve)
* autoinvite in the group
* [autohistory](#autohistory)

### Autohistory

If you enable autohistory for some group, bot will send all offline messages to
you when you come online in the next time. Since bot use PM, feature can be
enabled only for one group. If you enable it for another, old autohistory is
reseted.
