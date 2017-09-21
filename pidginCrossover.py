#!/usr/bin/env python
# coding: UTF-8

# emoji, humanize, parsedatetime, pydbus, youtube-dl, and PyGObject are dependencies.
# "sudo pip install emoji pygobject humanize parsedatetime pydbus youtube-dl --upgrade" will do that for you.
from __future__ import print_function  # This does not break Python 3 compatibility.

import traceback
import re
from datetime import datetime, timedelta
from json import dumps, loads
from math import ceil
from multiprocessing import Process, Queue, Lock
from random import randint
from emoji import demojize, emojize  # This dependency is 👍
from emoji.unicode_codes import UNICODE_EMOJI as emojis
from gi.repository import GObject, GLib
from humanize import naturaldelta, naturaltime
from os import mkfifo
from os import system as executeCommand
from pydbus import SessionBus
from parsedatetime import Calendar as datetimeParser
from time import strptime, sleep
from six import string_types
from youtube_dl import YoutubeDL as ydl

# Utility Functions:
# -----------------------------------------------
def dump(obj):
    """
    Dumps an object's properties into the console.
    :param obj: The object to dump
    """
    for attr in dir(obj):
        if hasattr(obj, attr):
            print(u"obj.{} = {}".format(attr, getattr(obj, attr)))


def readFile(path):
    """
    Reads, then parses the file at the given path as json.

    :param path: The file path of the file.
    :type path: string_types
    :return: The file parsed as json.
    """
    try:
        with open(path, mode=u"r+") as fileHandle:  # With is nice and clean.
            out = None
            strFile = fileHandle.read(-1)
            if out is None and strFile != u"":
                try:
                    out = loads(strFile)  # json.loads is WAY faster than ast.literal_eval!
                except ValueError:
                    pass
    except IOError:
        return None
    return out


readFiles = lambda *paths: map(readFile, paths)  # Runs readFile on all of the paths provided.


def getChats():
    """
    Returns all valid chat ids, filtering out any duplicate or invalid chats.

    :return: All valid chat ids, filtering out any duplicate or invalid chats.
    """
    rawChats = purple.PurpleGetConversations()
    chatIDs = dict()
    for i in rawChats:
        info = (purple.PurpleConversationGetAccount(i), purple.PurpleConversationGetTitle(i))
        if info not in chatIDs or chatIDs[info] < i <= 10000 or purple.PurpleConversationGetType(i) != 2:
            chatIDs[info] = i
    return tuple(chatIDs.values())


def updateFile(path, value):
    """
    Replaces the contents of the file at the given path with the given value.

    :param path: The file path of the file to overwrite.
    :type path: string_types
    :param value: The string_types string to overwrite the file with.
    :type value: string_types
    """

    def serializeDate(string):
        if isinstance(string, datetime):
            return string.strftime(dtFormatStr)
        return None

    with open(path, mode=u"w") as openFile:  # To update a file
        openFile.write(dumps(value, openFile, indent=4, default=serializeDate))
        # The default function allows it to dump datetime objects.


# Fixes rounding errors.
naturalTime = lambda time: naturaltime(time + timedelta(seconds=1))
naturalDelta = lambda time: naturaldelta(time - timedelta(seconds=1))


def getNameFromArgs(act, name, conv=None):
    """
    Gets a user's actual name given the account and name.
    :param act: The account from the argSet.
    :param name: The user's name from the argSet.
    :param conv: The conversation from the argSet.
    :return: The user's nickname, or their actual name if no nick was found.
    """
    realName = purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(act, name))
    chat = None  # This is here so PyCharm doesn't complain about chat not existing in the return statement.
    if conv is not None:
        chat = getChatName(conv)
    return nicks[chat].get(realName, realName) if conv is not None and chat in nicks else realName


getChatName = lambda chatId: purple.PurpleConversationGetTitle(chatId)  # Gets the name of a chat given the chat's ID.


def getTime(currTime):
    """
    Given a natural time string, such as "in 30 minutes", returns that time as a datetime object.

    :param currTime: A natural time string, such as "in 30 minutes" or "7 PM".
    :type currTime: string_types
    :return: The natural time as a datetime object.
    :rtype: datetime
    """
    return parser.parseDT(currTime)[0]


getCommands = lambda argSet: u"Valid Commands: {}\nValid Aliases: {}".format(u", ".join(sorted(commands.keys())),
    u", ".join(sorted(aliases[getChatName(argSet[3])].keys())))  # Returns a list of all of the commands.


def getFullConvName(partialName):
    """
    Returns a full conversation title given a partial title.

    :param partialName: The incomplete name of the conversation.
    :type partialName: string_types
    :return: The conversation ID.
    :rtype: int
    """
    conversations = [purple.PurpleConversationGetTitle(conv) for conv in getChats()]
    # Check the beginning first, if none start with the partial name, find it in there somewhere.
    return next((i for i in conversations if i[:len(partialName)] == partialName), None) or next(
        (i for i in conversations if partialName in i), None)


# Returns the conversation ID of a conversation given its partial name.
getConvFromPartialName = lambda partialName: getConvByName(getFullConvName(partialName))


def simpleReply(argSet, message):
    """
    Sends the message to the chat matching the given argSet.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param message: The message to send out.
    :type message: string_types
    """
    sendMessage(argSet[-2], argSet[-2], u"", message)  # Replies to a chat


# Gets the ID of a conversation, given its name. Does not work if a message has not been received from that chat yet.
getConvByName = lambda name: next(
    (i for i in getChats() if purple.PurpleConversationGetTitle(i) == name), None)

logFile = open(u"Pidgin_Crossover_Messages.log", mode=u"a")

def log(msg):
    """
    Writes msg into the console and appends it to the log file.
    :param msg: The string to write.
    :type msg: string_types
    """
    print(msg)
    # PyCharm thinks a TextIOWrapper is not an instance of Optional[IO]. PyCharm is incorrect.
    # noinspection PyTypeChecker
    print(msg, file=logFile)

# Returns what it says on the tin.
isListButNotString = lambda obj: isinstance(obj, (list, tuple, set)) and not isinstance(obj, string_types)
# ---------------------------------------

# Read files for persistent values.
messageLinks, puns, aliases, atLoc, scheduledEvents, nicks = readFiles(u"messageLinks.json", u"Puns.json",
    u"Aliases.json", u"atLoc.json", u"scheduledEvents.json", u"nicks.json")

commandDelimiter = u"!"  # What character(s) the commands should start with.
lastMessage = u""  # The last message, to prevent infinite looping.
defaultLocMinutes = 45
defaultLocTime = u"{} minutes".format(defaultLocMinutes) # What to use when someone goes somewhere without specifying a length of time.
now = datetime.now
lastMessageTime = now()
startTime = now()
parser = datetimeParser()
messageLinks = messageLinks or {}
puns = puns or {}
aliases = aliases or {}
atLoc = atLoc or {}
scheduledEvents = scheduledEvents or []
aliasVars = [  # Replace the string with the result from the lambda below.
    (u"%sendername", lambda argSet: getNameFromArgs(argSet[0], argSet[1], argSet[3])),
    (u"%botname", lambda argSet: purple.PurpleAccountGetAlias(argSet[0])),
    (u"%chattitle", lambda argSet: purple.PurpleConversationGetTitle(argSet[3])),
    (u"%chatname", lambda argSet: purple.PurpleConversationGetName(argSet[3]))
]
nicks = nicks or {}
dtFormatStr = u"%a, %d %b %Y %H:%M:%S UTC"
dateFormatStr = u"%a, %b %m %Y at %I:%M%p"
pipePath = u"pidginBotPipe"
terminalName = u"konsole" # This will need to be changed if you don't use KDE!
confirmMessage = False
confirmationListenerProcess = None
running = True
exitCode = 0


def replaceAliasVars(argSet, message):
    """
    Given the original message, replaces any alias vars (see above) with their proper values.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param message: The message to replace. Will not use the message in argSet.
    :type message: string_types
    :return The message, with all of the alias variables replaced.
    :rtype string_types
    """
    newMsg = message  # Don't touch the original
    for i in aliasVars:
        try:
            newMsg = newMsg.replace(i[0], i[1](argSet))
        except:
            pass
    return newMsg

def restartFinch():
    print(u"Restarting Finch...")
    executeCommand(u"killall -q finch")

    # This is not the most compatible way of doing this, but switching it to another terminal would be easy.
    executeCommand(u"{} -e \"finch\" & > /dev/null > /dev/null".format(terminalName))
    # TODO: See if this sleep delay can be lowered?
    sleep(.25)

def getPun(argSet, punFilter):
    """
    Gets a random pun, or a random pun that satisfies the provided filter.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param punFilter: A string filtering the puns out.
    :type punFilter: string_types
    :return: A random pun from puns.json.
    :rtype string_types
    """
    chat = getChatName(argSet[3])
    puns[chat] = puns[chat] if chat in puns else []
    if len(puns[chat]) == 0:
        return u"No puns found!"
    if not punFilter:
        return puns[chat][randint(0, len(puns[chat]) - 1)]
    validPuns = list(filter(lambda pun: str(punFilter) in str(pun), puns[chat]))
    return (validPuns[randint(0, len(validPuns) - 1)]) if len(validPuns) > 0 else (
        u"Does not punpute! Random Pun: " + puns[chat][randint(0, len(puns) - 1)])


def Help(argSet, page=u"", *_):
    """
    Returns help text for the given command, or a page listing all commands.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param page: The page number it should be on, as a string_types string.
    :type page: string_types
    """
    iteratableCommands = tuple(sorted(commands.keys()))  # A tuple containing all of the keys in iteratableCommands.
    commandsPerPage = 10  # How many commands to show per page.
    cmd = page[len(commandDelimiter):] if page.startswith(commandDelimiter) else page
    if cmd and cmd.lower() in helpText:  # If the help text for a given command was asked for
        simpleReply(argSet, helpText[cmd.lower()])
    elif not page or (page and page.isdigit()):  # If a page number was asked for
        page = int(page) if page and page.isdigit() else 1
        helpEntries = [u"Help page {}/{}".format(int(min(page, int(ceil(1.0 * len(iteratableCommands) / commandsPerPage)))),
            int(ceil(1.0 * len(iteratableCommands) / commandsPerPage)))]
        for i in range(max(0, (page - 1) * commandsPerPage), min(page * commandsPerPage, len(iteratableCommands))):
            helpEntries.append(u"\n" + iteratableCommands[i] + u": " + (
                helpText[iteratableCommands[i]] if iteratableCommands[i] in helpText else u""))
        simpleReply(argSet, u"".join(helpEntries))
    else:
        simpleReply(argSet, u"No command \"{}\" found.".format(page))


def Link(argSet, chat, *chats):
    """
    Links chats to chat. Supports partial names.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param chat: The partial name of the chat to link the current chat to.
    :type chat: string_types
    :param chats: A list of all of the chats available.
    :type chats: tuple
    """
    fullChatName = getFullConvName(chat)
    fullChatNames = set([getFullConvName(chat) for chat in chats])
    if fullChatName in messageLinks:
        messageLinks[fullChatName].intersection(fullChatNames)
    else:
        messageLinks[fullChatName] = fullChatNames
    if len(messageLinks[fullChatName]) == 1:
        messageLinks[fullChatName] = messageLinks[fullChatName][0]
    updateFile(u"messageLinks.json", messageLinks)
    simpleReply(argSet, u"{} linked to {}.".format(u", ".join(str(i) for i in fullChatNames), fullChatName))


def Unlink(argSet, chat, *chats):
    """
    Unlinks chats from chat. Supports partial names.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param chat: The partial name of the chat to unlink from the current chat.
    :type chat: string_types
    :param chats: A list of all of the chats available.
    :type chats: tuple
    """
    fullChatName = getFullConvName(chat)
    removedChats = []
    if fullChatName not in messageLinks:  # If you wanted a chat that doesn't exist, just return.
        simpleReply(argSet, u"No chat \"{}\" found.".format(chat))
        return
    for i in chats:  # Remove each chat
        fullName = getFullConvName(i)
        if fullName == messageLinks[fullChatName]:
            messageLinks.pop(fullChatName)  # Remove the last message link from this chat.
            simpleReply(argSet, u"{} unlinked from {}.".format(fullName, fullChatName))
            return
        elif isListButNotString(messageLinks[fullChatName]) and fullName in messageLinks[fullChatName]:
            removedChats.append(messageLinks[fullChatName].pop(messageLinks[fullChatName].index(fullName)))
            if len(messageLinks[fullChatName]) == 0:
                del messageLinks[fullChatName]
    updateFile(u"messageLinks.json", messageLinks)  # Update the messageLinks file.
    simpleReply(argSet, u"{} unlinked from {}.".format(u", ".join(removedChats), fullChatName))


def addPun(argSet, pun):
    """
    Adds a pun to the pun list, then updates the file.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param pun: The pun to add to the pun list.
    :type pun: string_types
    """
    chat = getChatName(argSet[3])
    puns[chat] = puns[chat] if chat in puns else []
    puns[chat].append(str(pun))
    updateFile(u"Puns.json", puns)
    simpleReply(argSet, u"\"{}\" added to the pun list.".format(pun))


def removePun(argSet, pun):
    """
    Removes a pun from the pun list, then updates the file.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param pun: The pun to remove from the pun list.
    :type pun: string_types
    """
    chat = getChatName(argSet[3])
    puns[chat] = puns[chat] if chat in puns else []
    fullPun = next((fullPun for fullPun in puns if str(pun) in puns[chat]), None)
    if fullPun is None:
        simpleReply(argSet, u"No pun found containing \"{}\".".format(pun))
        return
    puns[chat].remove(fullPun)
    simpleReply(argSet, u"\"{}\" removed from the pun list.".format(fullPun))
    updateFile(u"Puns.json", puns)


def addAlias(argSet, *_):
    """
    Adds an alias for a command, or replies what an alias runs.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    """
    chat = getChatName(argSet[3])
    aliases[chat] = aliases[chat] if chat in aliases else {}
    message = argSet[2][7 + len(commandDelimiter):]
    if message == u"":
        return
    command = (message[:message.find(u" ")] if u" " in message else message).lower()
    command = command[len(commandDelimiter):] if command[:len(commandDelimiter)] == commandDelimiter else command
    argsMsg = message[message.find(u" ") + 1 + len(commandDelimiter):]
    args = [str(arg) for arg in argsMsg.split(u" ")]
    if u" " not in message:  # If the user is asking for the command run by a specific alias.
        if str(command) not in aliases[chat]:  # If the alias asked for does not exist.
            simpleReply(argSet, u"No alias \"{}\" found.".format(str(command)))
            return
        simpleReply(argSet, u'"' + commandDelimiter + aliases[chat][str(command)][0] + u'"')
        return
    if str(command) in commands:
        simpleReply(argSet, u"That name is already used by a command!")
        return
    cmd = argsMsg[(len(commandDelimiter) if argsMsg.startswith(commandDelimiter) else 0):(
        u" " in argsMsg and argsMsg.find(u" ") or len(argsMsg))]
    if cmd not in commands:
        simpleReply(argSet, u"{}{} is not a command!".format(commandDelimiter, cmd))
        return
    aliases[chat][str(command)] = (argsMsg, args)
    simpleReply(argSet, u"\"{}\" bound to \"{}\".".format(commandDelimiter + command, commandDelimiter + argsMsg))
    updateFile(u"Aliases.json", aliases)


def removeAlias(argSet, alias=u"", *_):
    """
    Removes an alias to a command.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param alias: The alias for the command.
    :type alias: string_types
    """
    chat = getChatName(argSet[3])
    aliases[chat] = aliases[chat] if chat in aliases else {}
    if not alias:
        simpleReply(argSet, u"Enter an alias to remove!")
        return
    if alias[:len(commandDelimiter)] == commandDelimiter:
        alias = alias[len(commandDelimiter):]
    if alias in aliases[chat]:
        aliases[chat].pop(alias)
    else:
        simpleReply(argSet, u"No alias \"{}\" found.".format(alias))
        return
    simpleReply(argSet, u"\"{}\" unaliased.".format(alias))
    updateFile(u"Aliases.json", aliases)


def getFullUsername(argSet, partialName, nick=True):
    """
    Returns a user's alias given their partial name.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param partialName: The partial name of a user.
    :type partialName: string_types
    :param nick: Whether or not it should return the user's nickname.
    :type nick: bool
    :return: A user's alias.
    :rtype: string_types
    """
    chat = getChatName(argSet[3])

    # Special case the bot's name
    botName = purple.PurpleAccountGetAlias(argSet[0])
    if partialName.lower() == botName[:len(partialName)].lower() or partialName.lower() in botName.lower():
        return botName if (u""+botName) not in nicks[chat] or not nick else nicks[chat][u""+botName]

    buddies = [purple.PurpleConvChatCbGetName(user) for user in
        purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]
    names = [getNameFromArgs(argSet[0], buddy) for buddy in buddies]
    names.append(purple.PurpleAccountGetAlias(argSet[0]))
    rng = range(len(names))
    # Check the beginning first, otherwise, check if the partialname is somewhere in the name.
    name = (next((names[i] for i in rng if names[i][:len(partialName)].lower() == partialName.lower()), None) or
            next((names[i] for i in rng if partialName.lower() in names[i].lower()), None))
    if nick and name is not None and chat in nicks and (u"" + name) in nicks[chat]:
        return nicks[chat][u"" + name]
    return name


def getUserFromName(argSet, partialName, nick=True):
    """
    Returns the "name" of a user given their partial name.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param partialName: The partial name of a user.
    :type partialName: string_types
    :param nick: Whether or not it should check nicknames.
    :type nick: bool
    :return: A user's "name".
    :rtype: string_types
    """
    chat = getChatName(argSet[3])

    # Special case the bot's name
    botName = purple.PurpleAccountGetAlias(argSet[0])
    if partialName.lower() == botName[:len(partialName)].lower() or partialName.lower() in botName.lower():
        return botName if (u""+botName) not in nicks[chat] or not nick else nicks[chat][u""+botName]

    buddies = [purple.PurpleConvChatCbGetName(user) for user in
        purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]
    names = [getNameFromArgs(argSet[0], buddy) for buddy in buddies]
    rng = range(len(buddies))
    # Check the beginning first, otherwise, check if the partialname is somewhere in the name.
    name = (next((buddies[i] for i in rng if names[i][:len(partialName)].lower() == partialName.lower()), None) or
            next((buddies[i] for i in rng if partialName.lower() in names[i].lower()), None))
    if nick and name is not None and chat in nicks and (u"" + name) in nicks[chat]:
        return nicks[chat][u"" + name]
    return name


def Mimic(argSet, user=None, firstWordOfCmd=None, *_):
    """
    Runs a command as a different user.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param user: The partial name of the user to mimic.
    :type user: string_types
    :param firstWordOfCmd: The first word of the command to run, for syntax checking.
    :type firstWordOfCmd: string_types
    """
    if user is None or firstWordOfCmd is None:
        simpleReply(argSet, u"You need to specify the user to mimic and the command to mimic!")
        return
    fullUser = getUserFromName(argSet, user, False)

    if fullUser is None:
        simpleReply(argSet, u"No user by the name \"{}\" found.".format(user))
        return

    if fullUser == purple.PurpleAccountGetAlias(argSet[0]): # If mimic is attempted on the bot
        simpleReply(argSet, u"You can't use mimic on me! I'm invincible!")
        return
    # The command, after the user argument.
    cmd = argSet[2][6 + len(commandDelimiter):][argSet[2][6 + len(commandDelimiter):].find(u" ") + 1:].lower()

    if not runCommand((argSet[0], fullUser, cmd, argSet[3], argSet[4]), cmd.split(u" ")[0][len(commandDelimiter):],
            *cmd.split(u" ")[len(commandDelimiter):]):
        simpleReply(argSet, u"That's not a command!")


def loc(argSet, *_):
    """
    Tells the chat you've gone somewhere.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    """
    findSpace = argSet[2].find(u" ")
    time = False
    location = None
    if findSpace is not None:
        findSpace2 = argSet[2].find(u" ", findSpace + 1)
        location = argSet[2][findSpace + 1:findSpace2] if len(argSet[2]) > len(
            commandDelimiter) + 4 and argSet[2].count(u" ") > 1
        time = argSet[2][findSpace2 + 1:]
    Loc(argSet, time=time or argSet[2], location=location)


def Loc(argSet, location=u"GDS", time=defaultLocTime):
    """
    Tells the chat you've gone somewhere. Has default values for ease of implementation.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param time: The time in which you will be staying at the location.
    :type time: string_types
    :param location: The location you're going to.
    :type location: string_types
    """
    chat = getChatName(argSet[3])
    time = time if len(time) != 0 else defaultLocTime
    atLoc[chat] = atLoc[chat] if chat in atLoc else {}
    # Update the time
    name = getNameFromArgs(argSet[0], argSet[1], argSet[3])
    atLoc[chat][name] = [now(), location, time]
    if u"in " in time or u"at " in time:
        newArgset=list(argSet)
        newArgset[2] = u"{0}schedule {1} {0}loc {2} {3}".format(commandDelimiter, time, location, defaultLocTime)
        messageListener(*newArgset, notOverflow=True)
        return

    simpleReply(argSet,u"{} is going to {} for {}.".format(getNameFromArgs(*argSet[:2]), location, time))
    updateFile(u"atLoc.json", atLoc)


def leftLoc(argSet, *_):
    """
    Tells the chat you've left wherever you are.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    """
    chat = getChatName(argSet[3])
    atLoc[chat] = atLoc[chat] if chat in atLoc else {}
    name = getNameFromArgs(*argSet[:2])
    if name in atLoc[chat]:
        thisLoc = atLoc[chat][name]
        thisLoc[0] = datetime(1901, 1, 1, 1, 1, 1, 1)
        simpleReply(argSet,
            u"{} left {}.".format(name, thisLoc[1]))
        updateFile(u"atLoc.json", atLoc)
    else:
        simpleReply(argSet, u"{} isn't anywhere!".format(name))


def AtLoc(argSet, *_):
    """
    Replies with who is at the given location, or where everyone is if the location is not specified.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    """

    def toDate(string):
        """
        Converts the serialized datetime back to a datetime object, or uses now otherwise.

        :param string: The serialized datetime, as a string_types string.
        :type string: string_types
        :return: The unserialized string, as a datetime object.
        :rtype datetime
        """
        if type(string) == datetime:
            return string
        try:
            return datetime.strptime(string, dtFormatStr)
        except:
            return now()

    def toDelta(string):
        """
        Converts a serialized string back into a datetime object.

        :param string: The serialized string.
        :type string: string_types
        :return: The serialized string, as a datetime object.
        :rtype: timedelta
        """
        if type(string) == timedelta:
            if string > timedelta():
                return string
            else:
                return timedelta(minutes=defaultLocMinutes)
        try:
            return strptime(string, u"%H:%M:%S")
        except:
            return timedelta(minutes=defaultLocMinutes)

    location = argSet[2][len(commandDelimiter) + 6:] if u" " in argSet[2] else u"anywhere"
    chat = getChatName(argSet[3])
    atLoc[chat] = atLoc[chat] if chat in atLoc else {}

    # Filter out people who have been somewhere recently.
    lastHour = [name for name in atLoc[chat].keys() if
        now() - toDate(atLoc[chat][name][0]) < toDelta(atLoc[chat][name][2]) and (
            atLoc[chat][name][1] == location or location == u"anywhere")]
    # Write the names to a string.
    strPeopleAtLoc = u"\n".join([u"{} went to {} {} ago. ".format(
        n, atLoc[chat][n][1], naturalDelta(now() - toDate(atLoc[chat][n][0]))) for n in lastHour])
    if lastHour:
        simpleReply(argSet, strPeopleAtLoc)
    else:  # If no one has been to a location
        simpleReply(argSet,
            u"No one went {} recently.".format(location if location == u"anywhere" else u"to " + location))


def scheduleEvent(argSet, *_):
    """
    Schedules the given command to run at the given time.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    """
    msg = argSet[2][len(commandDelimiter) + 9:]
    if commandDelimiter in msg:
        timeStr = msg[:msg.find(commandDelimiter) - 1]
        cmdStr = msg[msg.find(commandDelimiter):]
    else:
        simpleReply(argSet, u"You need a command to run, with the command delimiter \"{}\"".format(commandDelimiter))
        return
    newArgset = list(argSet)
    newArgset[2] = cmdStr
    newArgset[0] = purple.PurpleAccountGetUsername(argSet[0])
    scheduledEvents.append((getTime(timeStr), newArgset))
    updateFile(u"scheduledEvents.json", scheduledEvents)
    simpleReply(argSet, u"\"{}\" scheduled to run {}.".format(cmdStr, naturalTime(getTime(timeStr))))


def getEvents(argSet, *_):
    """
    Tells the user what events they have scheduled.
    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    """
    eventStrs = [u"[{}] {}: {} ({})".format(scheduledEvents.index(event),
        naturalTime(datetime.strptime(event[0], dtFormatStr) if type(event[0]) != datetime else event[0]), event[1][2],
        (datetime.strptime(event[0], dtFormatStr) if type(event[0]) != datetime else event[0]).strftime(dateFormatStr))
        for event in scheduledEvents if getNameFromArgs(argSet[0], *event[1][1:2]) == getNameFromArgs(*argSet[0:2])]
    if len(list(eventStrs)) == 0:
        simpleReply(argSet, u"You don't have any events scheduled!")
    else:
        simpleReply(argSet, u"\n".join(eventStrs))


def getAllEvents(argSet, *_):
    """
    Replies with all of the scheduled events.
    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    """
    eventStrs = [u"[{}] {}: {} ({})".format(scheduledEvents.index(event),
        naturalTime(datetime.strptime(event[0], dtFormatStr) if type(event[0]) != datetime else event[0]), event[1][2],
        (datetime.strptime(event[0], dtFormatStr) if type(event[0]) != datetime else event[0]).strftime(dateFormatStr))
        for event in scheduledEvents]
    if len(list(eventStrs)) == 0:
        simpleReply(argSet, u"No events have been scheduled.")
    else:
        simpleReply(argSet, u"\n".join(eventStrs))


def removeEvent(argSet, index, *_):
    """
    Removes a scheduled event.
    :param argSet: The set of values passed in to messageListener
    :type argSet: tuple
    :param index: The index of the event to be removed.
    :type index: int
    """
    index = int(index)
    if getNameFromArgs(argSet[0], *scheduledEvents[index][1][1:2]) == getNameFromArgs(*argSet[:2]):
        scheduledEvents.pop(index)
        simpleReply(argSet, u"Event at index {} removed.".format(index))
    else:
        simpleReply(argSet, u"You don't have an event scheduled with that index!")


def setNick(argSet, user, *nick):
    """
    Sets a user's nickname.
    :param argSet: The set of values passed in to messageListener.
    :param user: The partial name of the user whose nick is to be set.
    :param nick: The new nickname.
    """
    fullName = getFullUsername(argSet, user, False)
    chat = getChatName(argSet[3])
    nick = u" ".join(nick)
    if fullName is not None:
        if chat not in nicks:
            nicks[chat] = {}
        nicks[chat][fullName] = nick
        simpleReply(argSet, u"{}'s nickname set to \"{}\".".format(fullName, nick))
        updateFile(u"nicks.json", nicks)
    else:
        simpleReply(argSet, u"No user by the name {} found.".format(user))


def removeNick(argSet, user):
    """
    Removes the nickname from a user.
    :param argSet: The set of values passed in to messageListener.
    :param user: The partial name of the user whose nick is to be removed.
    """
    fullName = getFullUsername(argSet, user)
    chat = getChatName(argSet[3])
    if chat not in nicks:
        nicks[chat] = {}
    nicks[chat].pop(fullName)
    simpleReply(argSet, u"{}'s nickname removed.".format(fullName))
    updateFile(u"nicks.json", nicks)


def getNicks(argSet):
    """
    Returns all of the nicknames.
    :param argSet: The set of values passed in to messageListener.
    """
    chat = getChatName(argSet[3])
    if chat not in nicks:
        simpleReply(argSet, u"No nicks have been set in this chat yet!")
        return
    simpleReply(argSet, u"\n".join(u"{}: {}".format(str(k), str(v)) for k, v in nicks[chat].items()))


dice = [u"0⃣", u"1⃣", u"2⃣", u"3⃣", u"4⃣", u"5⃣", u"6⃣", u"7⃣", u"8⃣", u"9⃣️⃣️"]  # 1-9 in emoji form


def numToEmoji(s):
    """
    Replaces numbers with emojis.

    :param s: The string to replace the numbers of with emojis.
    :type s: string_types
    :return: The provided string with its numbers replaced with emojis.
    :rtype: string_types
    """
    for i in range(len(dice)):
        s = s.replace(u"" + str(i), dice[i])  # Force string_types strings for Python 2 and Python 3.
    return s


def exitProcess(code):
    """
    Exits like sys.exit, killing any other processes run by this one.
    :param code: the exit code.
    """
    if confirmationListenerProcess is not None:
        confirmationListenerProcess.terminate()
    global running, exitCode
    running = False # Go away, GLib.timeout.
    mainloop.quit() # Go away, GObject.
    exitCode = code

def restartBot():
    """
    Restarts finch and the bot.
    """
    restartFinch()
    exitProcess(0)


def diceRoll(argSet, diceStr="", *_):
    """
    Returns a dice roll of the given dice.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param diceStr: The string used to specify the type of dice, in the form [numDice]d[diceSides]
    :type diceStr: string_types
    """
    numDice, numSides = 1, 6  # Defaults to 1d6
    if u"d" in diceStr.lower():
        numDice, numSides = int(diceStr[:diceStr.lower().find(u"d")]), int(diceStr[diceStr.lower().find(u"d") + 1:])
    elif diceStr.isdigit():
        numDice = int(diceStr)
    rolls = [randint(1, numSides) for _ in range(numDice)]  # Roll the dice
    simpleReply(argSet,
        numToEmoji(u"".join(str(s) + u" " for s in rolls) + u"\nSum={}\nMax={}\nMin={}".format(sum(rolls), max(rolls),
            min(rolls))))


def to(argSet, *args):
    """
    Provides %target as an alias variable, then replies with the parsed string.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    """
    if len(args) == 0:
        simpleReply(argSet, u"You need to provide some arguments!")
        return
    user = args[-1]
    name = getFullUsername(argSet, user, False)
    nick = getFullUsername(argSet, user, True) or name
    if name is not None:
        msg = argSet[2]
        simpleReply(argSet,
            replaceAliasVars(argSet, msg[len(commandDelimiter) + 3:msg.rfind(u" ")]).replace(u"%target", nick))
    else:
        simpleReply(argSet, u"No user containing {} found.".format(user))


def findNthInstance(n, haystack, needle):
    """
    Finds the nth instance of needle in haystack.
    :type n: int
    :param n: How many instances to look for.
    :type haystack: string_types
    :param haystack: What to search through
    :type needle: string_types
    :param needle: What to look for.
    :return: n, or 0 if none is found.
    """
    index = -1
    for i in range(n):
        index = haystack.find(needle, index + len(needle))
        if index == -1:
            return 0
    return index


def getYTURL(queryMsg):
    """
    Gets the URL of the first YouTube video when searching for queryMsg.
    :type queryMsg: string_types
    :param queryMsg: The search term to use to find the video.
    :rtype: string_types
    :return: The URL of the YouTube video, as a string.
    """
    dl = ydl()
    with dl:
        info = dl.extract_info(u"ytsearch1:" + queryMsg, download=False)[u"entries"][0]
        return u"{1} - https://youtube.com/watch?v={0}".format(info[u"id"], info[u"title"])


commands = {  # A dict containing the functions to run when a given command is entered.
    u"help": Help,
    u"ping": lambda argSet, *_: simpleReply(argSet, u"Pong!"),
    u"chats": lambda argSet, *_: simpleReply(argSet,
        u"" + str([u"{} ({})".format(purple.PurpleConversationGetTitle(conv), conv) for conv in getChats()])[
        1:-1].replace(
            u"u'", u"'")),
    u"args": lambda argSet, *_: simpleReply(argSet, u"" + str(argSet)),
    u"echo": lambda argSet, *_: simpleReply(argSet,
        argSet[2][argSet[2].lower().find(u"echo") + 4 + len(commandDelimiter):]),
    u"exit": lambda *_: exitProcess(37),
    u"msg": lambda argSet, msg="", *_: sendMessage(argSet[-2], getConvFromPartialName(msg), u"",
        getNameFromArgs(*argSet[:2]) + ": " + argSet[2][
        argSet[2][4 + len(commandDelimiter):].find(u" ") + 5 + len(commandDelimiter):]),
    u"link": lambda argSet, *args: Link(argSet, *args),
    u"unlink": lambda argSet, *args: Unlink(argSet, *args),
    u"links": lambda argSet, *_: simpleReply(argSet, u"" + str(messageLinks)),
    u"pun": lambda argSet, pun=u"", *_: simpleReply(argSet, getPun(argSet, pun)),
    u"addpun": lambda argSet, *_: addPun(argSet, argSet[2][7 + len(commandDelimiter):]),
    u"removepun": lambda argSet, pun, *_: removePun(argSet, pun),
    u"alias": addAlias,
    u"unalias": removeAlias,
    u"aliases": lambda argSet, *_: simpleReply(argSet,
        u"Valid aliases: {}".format(u", ".join(sorted(aliases[getChatName(argSet[3])].keys()))).replace(u"u'", u"'")),
    u"me": lambda argSet, *_: simpleReply(argSet, replaceAliasVars(argSet, u"*{} {}.".format(
        getNameFromArgs(argSet[0], argSet[1], argSet[3]), argSet[2][3 + len(commandDelimiter):]))),
    u"botme": lambda argSet, *_: simpleReply(argSet, u"*{} {}.".format(purple.PurpleAccountGetAlias(argSet[0]),
        argSet[2][6 + len(commandDelimiter):])),
    u"randomemoji": lambda argSet, amt=1, *_: simpleReply(argSet, u"".join(
        [u"" + str(tuple(emojis.values())[randint(0, len(emojis) - 1)]) for _ in range(int(amt) or 1)])),
    u"mimic": Mimic,
    u"users": lambda argSet, *_: simpleReply(argSet, emojize(str(
        [getNameFromArgs(argSet[0], purple.PurpleConvChatCbGetName(user)) for user in
            purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]), use_aliases=True)),
    u"loc": loc,
    u"gds": lambda argSet, *_: Loc(argSet, time=argSet[2][len(commandDelimiter) + 4:]),
    u"loconly": lambda argSet, *_: Loc(argSet, location=argSet[2][len(commandDelimiter) + 8:]),
    u"atloc": AtLoc,
    u"leftloc": leftLoc,
    u"diceroll": diceRoll,
    u"restart": lambda *_: restartBot(),
    u"commands": lambda argSet, *_: simpleReply(argSet, getCommands(argSet)),
    u"to": to,
    u"schedule": scheduleEvent,
    u"events": getEvents,
    u"allevents": getAllEvents,
    u"unschedule": removeEvent,
    u"nicks": getNicks,
    u"setnick": setNick,
    u"removenick": removeNick,
    u"lastreboot": lambda argSet, *_: simpleReply(argSet,
        u"{}, ({})".format(naturalTime(startTime), startTime.strftime("%a, %b %m %Y at %I:%M%p"))),
    u"htmlescape": lambda argSet, *_: simpleReply(argSet, purple.PurpleMarkupStripHtml(argSet[2][11:])),
    u"replace": lambda argSet, start, end, *_: simpleReply(argSet,
        re.compile(re.escape(start), re.IGNORECASE).sub(end, argSet[2][findNthInstance(3, argSet[2], u" ") + 1:])),
    u"yt": lambda argSet, *query: simpleReply(argSet, getYTURL(argSet[2])),
}

helpText = {  # The help text for each command.
    u"help": u"Prints out the syntax and usage of each command.",
    u"ping": u"Replies \"Pong!\". Useful for checking if the bot is working.",
    u"chats": u"Lists all chats the bot knows of by name and ID.",
    u"args": u"Prints out the arguments received from this message.",
    u"echo": u"Repeats the message said.",
    u"exit": u"Exits the bot.",
    u"msg": u"Sends a message to the specified chat. Matches incomplete names.",
    u"link": u"Links from the first chat to the following chats.",
    u"unlink": u"Unlinks the second and further chats from the first chat.",
    u"links": u"Prints out the current message links.",
    u"pun": u"Replies with a random pun.",
    u"addpun": u"Adds a pun to the list of random puns.",
    u"alias": u"Links a name to a command, or prints out the command run by an alias.",
    u"unalias": u"Unlinks a name from a command.",
    u"aliases": u"Lists all of the aliases.",
    u"removepun": u"Removes a pun from the list of puns.",
    u"me": u"Replies \"*(username) (message)\", e.g. \"*Gian Laput is French.\"",
    u"botme": u"Replies \"*(bot's name) (message)\", e.g. \"*NickBot DeLello died.\"",
    u"randomemoji": u"Replies with the specified number of random emojis.",
    u"mimic": u"Runs the specified command as if it was run by the specified user.",
    u"users": u"Lists all of the users in the current chat.",
    u"loc": u"Tells the chat you've gone somewhere.",
    u"gds": u"Tells the chat you're going to GDS for some period of time.",
    u"loconly": u"Tells the chat you're going somewhere for an hour.",
    u"atloc": u"Replies with who's said they're somewhere within the last hour and where they are.",
    u"leftloc": u"Tells the chat you've left somewhere.",
    u"diceroll": u"Rolls the specified number of dice, returning the min, max, and sum of the rolls. 1d6 by default.",
    u"restart": u"Restarts the bot.",
    u"commands": u"Lists all of the commands.",
    u"to": u"Sends a message with the provided person as a 'target'. Mainly used for aliases.",
    u"aliasvars": u"%sendername, %botname, %chattitle, %chatname",
    u"schedule": u"Runs a command after the specified amount of time.",
    u"events": u"Lists all of the events you have scheduled.",
    u"allevents": u"Lists all scheduled events.",
    u"unschedule": u"Unschedules the event with the given index. (The index should be from {}events)".format(
        commandDelimiter),
    u"nicks": u"Lists the nicknames of all users in the chat. If they don't have one, their name will not show up!",
    u"setnick": u"Changes the nickname of the specified user.",
    u"removenick": u"Removes a user's nickname.",
    u"lastreboot": u"Returns when the bot was started up.",
    u"replace": u"Replaces the text in the last argument(s) using the first and second.",
    u"yt": u"Searches for a YouTube video using the query provided, and replies with the first result's URL."
}


def runCommand(argSet, command, *args):
    """
    Runs the command given the argSet and the command it's trying to run.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param command: The command to run.
    :type command: string_types
    :return: If the given command could be run, either as a command or an alias.
    :rtype: bool
    """
    command = (command or argSet[2][:argSet[2].find(u" ")]).lower()
    chat = getChatName(argSet[3])
    aliases[chat] = aliases[chat] if chat in aliases else {}
    if command in commands:
        commands[command](argSet, *args)
        return True
    elif command in aliases[chat]:
        message = argSet[2]
        msgLow = message.lower()
        cmd = aliases[chat][command]
        command = message[len(commandDelimiter):message.find(u" ") if u" " in message else len(message)].lower()
        # Swap the command for the right one
        message = message[:msgLow.find(command)] + command + message[msgLow.find(command) + len(command):]
        newMsg = replaceAliasVars(argSet, message.replace(command, cmd[0], 1))
        # Get the extra arguments to the function and append them at the end.
        extraArgs = newMsg.split(u" ")[1:]
        commands[cmd[1][0]]((argSet[0], argSet[1], newMsg, argSet[3], argSet[4]), *extraArgs)  # Run the alias's command
        return True
    return False


def sendMessage(sending, receiving, nick, message):
    """
    Sends a message on the given chat.

    :param sending: The id of the sending chat.
    :type sending: int
    :param receiving: The id of the receiving chat.
    :type receiving: int
    :param nick: The nickname of the user, for logging purposes
    :type nick: string_types
    :param message: The message to send out.
    :type message: string_types
    """
    if receiving is None:  # If the conversation can't be found by libpurple, it'll just error anyway.
        return

    if message[0:len(commandDelimiter)] == commandDelimiter:  # Do not send out commands! No! Bad!
        message = (u"_" if commandDelimiter[0] != u"_" else u" ") + message

    # Actually send the messages out.
    if purple.PurpleConversationGetType(receiving) == 2:  # 2 means a group chat.
        conv = purple.PurpleConvChat(receiving)
        purple.PurpleConvChatSend(conv, (nick + u": " if nick else u"") + emojize(message, True).replace(u"\n",u"<br>"))
    else:
        conv = purple.PurpleConvIm(receiving)
        purple.PurpleConvImSend(conv, (nick + u": " if nick else u"") + emojize(message, True).replace(u"\n",u"<br>"))

    # I could put this behind debug, but I choose not to. It's pretty enough.
    sendTitle = purple.PurpleConversationGetTitle(sending)
    receiveTitle = purple.PurpleConversationGetTitle(receiving)
    try:  # Logging errors should not break things.
        # Removes emojis from messages, not all consoles support emoji, and not all files like emojis written to them.
        log(demojize(u"[{}] Sent \"{}\" from {} ({}) to {} ({}).".format(now().isoformat(),
            (nick + u": " + message if nick else message), sendTitle, sending, receiveTitle, conv)))
        logFile.flush()  # Update the log since it's been written to.
    except UnicodeError:
        pass


def messageListener(account, sender, message, conversation, flags, notOverflow=False):
    """
    The function that runs when a message is received.

    :param account: The account the message was received on.
    :type account: int
    :param sender: The name of the chat the message was sent from.
    :type sender: string_types
    :param message: The received message.
    :type message: string_types
    :param conversation: The conversation in which this message was received.
    :type conversation: int
    :param flags: Any flags for this message, such as the type of message.
    :type flags: tuple
    :param notOverflow: Overrides overflow protection.
    :type notOverflow: bool
    """
    global lastMessageTime
    argSet = (account, sender, message, conversation, flags)
    if purple.PurpleAccountGetUsername(account) == sender:
        return
    if not notOverflow:
        if now() - lastMessageTime < timedelta(seconds=.1):
            print(u"Overflow!", account, sender, message, conversation, flags)  # Debug stuff
            lastMessageTime = now()
            return
    lastMessageTime = now()
    # Strip HTML from Hangouts messages.
    message = purple.PurpleMarkupStripHtml(message) if message.startswith(u"<") else message

    nick = getNameFromArgs(account, sender)  # Name which will appear on the log.

    try:  # Logs messages. Logging errors will not prevent commands from working.
        log(u"{}: {}\n".format(nick, (u"" + str(message))))
        logFile.flush()
    except UnicodeError:
        pass
    # Run commands if the message starts with the command character.
    if message[:len(commandDelimiter)] == commandDelimiter:
        command = message[len(commandDelimiter):message.find(u" ") if u" " in message else len(message)].lower()
        args = message.split(u" ")[1:]
        try:
            if not runCommand(argSet, command.lower(), *args):
                simpleReply(argSet, u"Command/alias \"{}\" not found. {}".format(
                    command, getCommands(argSet)))
        except SystemExit:
            return
        except KeyboardInterrupt:
            return
        except:
            simpleReply(argSet, u"Command errored! Error message: \"{}\"".format(traceback.format_exc()))
        return  # Commands are not to be sent out to other chats!

    # If the message was not a command, continue.
    global lastMessage
    if message == lastMessage:  # Makes sure the messages don't loop infinitely.
        return
    title = purple.PurpleConversationGetTitle(conversation)
    if title in messageLinks:  # Gets conversations by their title, so they work across libpurple reboots.
        if isListButNotString(messageLinks[title]):
            for receiving in messageLinks[title]:  # It can send to multiple chats.
                receiving = getConvByName(receiving)
                sendMessage(conversation, receiving, nick, message)
        else:
            receiving = getConvByName(messageLinks[title])
            sendMessage(conversation, receiving, nick, message)
    lastMessage = nick + u": " + message  # Remember the last message to prevent infinite looping.


def processEvents(threshold=timedelta(seconds=2)):
    eventRemoved = False
    for event in scheduledEvents:
        if isinstance(event[0], string_types):  # If it's reading it from the serialized version...
            eventTime = datetime.strptime(event[0], dtFormatStr)  # Convert it back to a datetime
        else:
            eventTime = event[0]
        if timedelta() < now() - eventTime:  # If the event is due to be scheduled...
            if now() - eventTime < min(threshold, timedelta(seconds=5)):  # Make sure the event was supposed to be run
                # less than 5 seconds before now, otherwise, don't run the function, but still discard of it.
                try:
                    accounts = purple.PurpleAccountsGetAll()
                    newArgset = event[1]
                    newArgset[0] = next((i for i in accounts if purple.PurpleAccountGetUsername(i) == newArgset[0]),
                        None)
                    if newArgset[0] is None:
                        raise Exception(u"Account not found.")
                    messageListener(*newArgset)
                except:
                    pass
            scheduledEvents.remove(event)  # Discard the event
            eventRemoved = True
    if eventRemoved:  # If any events were removed, update the file.
        updateFile(u"scheduledEvents.json", scheduledEvents)
    return True


def periodicLoop():
    """
    Used for any tasks that may need to run in the background.

    :return: True
    :rtype: True
    """
    processEvents()
    if confirmMessage:
        confirmName()
    return running


def confirmName():
    """
    Goes through the nameRequestQueue and confirms the name for each, if it's confirmed, it runs messageListener.
    """
    global lock, nameRequestQueue
    nameQueue = []
    with lock:
        while True:
            try:
                elem = nameRequestQueue.get(False)
            except:
                break
            nameQueue.append(elem)
    for nameTuple in nameQueue:
        print(u"Requesting name for " + str(nameTuple))
        if nameTuple[1] != getNameFromArgs(*nameTuple[0][:2]):
            newArgset = nameTuple[0]
            print(u"Running messageListener with " + str(newArgset))
            messageListener(*newArgset)


messageQueue = Queue()
nameRequestQueue = Queue()
localQueue = set()


def queueMessage(account, sender, message, conversation, flags):
    """
    Queues a message to be verified by the other bot.
    :param account: The account of the bot.
    :param sender: The name of the sender of the message.
    :param message: The message sent.
    :param conversation: The conversation the message was sent in.
    :param flags: Any modifiers to the message, such as if it was a picture message.
    """
    if purple.PurpleConversationGetType(conversation) == 1 or message == commandDelimiter + u"reboot":
        messageListener(account, sender, message, conversation, flags)
        return
    global lock
    argSet = (account, sender, message, conversation, flags)
    global messageQueue
    queuedMessage = (argSet, now())
    with lock:
        messageQueue.put(queuedMessage, False)


def onMessageConfirmation(otherArgset):
    """
    Takes a message confirmed by the other bot and puts it in the nameRequestQueue if it is valid.
    :param otherArgset:
    :return:
    """
    global messageQueue, localQueue, nameRequestQueue, lock
    removeQueue = set()
    with lock:
        while not messageQueue.empty():
            localQueue.add(messageQueue.get(False))

    for msg in localQueue:
        if now() - msg[1] < timedelta(minutes=5) and msg[0][1:3] == otherArgset[1:3]:
            with lock:
                nameRequestQueue.put((msg[0], msg[0][-1], otherArgset))
        else:
            removeQueue.add(msg)
    localQueue -= removeQueue


def confirmationListener():
    """
    Listens for messages confirmed by the other bot. Currently implemented using named pipes, but may be reimplemented
    later to use networking.
    """
    try:
        mkfifo(pipePath)
    except OSError:
        pass  # The pipe already exists
    while True:
        msgPipe = open(pipePath, "r")
        message = msgPipe.read()

        msgPipe.close()
        sleep(.1)
        print(u"Confirmed {}".format(message))
        try:
            onMessageConfirmation(tuple(loads(message)))
        except ValueError:
            pass  # Invalid JSON can happen when data is left over in the pipe, but this can be safely ignored.

bus = SessionBus()  # Initialize the DBus interface
purple = bus.get(u"im.pidgin.purple.PurpleService", u"/im/pidgin/purple/PurpleObject")  # Connect to libpurple clients.
# Surprisingly, im.pidgin.* and im/pidgin/* work for Finch too. Not sure why.

# Run the message listener for IMs and Chats.
purple.ReceivedImMsg.connect(queueMessage if confirmMessage else messageListener)
purple.ReceivedChatMsg.connect(messageListener)
purple.ConnectionError.connect(restartFinch)

lock = Lock()
if confirmMessage:
    confirmationListenerProcess = Process(target=confirmationListener)
    confirmationListenerProcess.start()

# TODO: These may be removable, but that needs to be tested
GObject.threads_init()
GLib.threads_init()

GLib.timeout_add_seconds(1, periodicLoop)  # Run periodicLoop once per second.
mainloop = GObject.MainLoop()
mainloop.run()  # Actually run the program.


exit(exitCode)  # Make sure the process exists with the correct error code.
