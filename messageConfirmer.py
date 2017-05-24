from gi.repository import GObject, GLib

from pydbus import SessionBus
from os import mkfifo
from json import dump, dumps

pipePath = u"pidginBotPipe"

def getNameFromArgs(act, name):
    """
    Gets a user's actual name given the account and name.
    :param act: The account from the argSet.
    :param name: The user's name from the argSet.
    :return: The user's nickname, or their actual name if no nick was found.
    """
    return purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(act, name))


def messageListener(*args):
    if args[2]==u"!reboot":
        exit(0)
    toDump = list(args)
    toDump.append(getNameFromArgs(*args[:2]))
    print(dumps(args))
    with open(pipePath,u"w") as msgPipe:
        dump(args,msgPipe)


bus = SessionBus()  # Initialize the DBus interface
purple = bus.get(u"im.pidgin.purple.PurpleService", u"/im/pidgin/purple/PurpleObject")  # Connect to libpurple clients.


# Run the message listener for IMs and Chats.
purple.ReceivedImMsg.connect(messageListener)
purple.ReceivedChatMsg.connect(messageListener)

try:
    mkfifo(pipePath)
except OSError:
    pass # The pipe already exists

GObject.MainLoop().run()
