# coding: UTF-8
"""
A bot controlling an instance of pidgin/finch in order to send/receive messages.
"""

# humanize, parsedatetime, pydbus, youtube-dl, and PyGObject are dependencies.
# "sudo pip install pygobject humanize parsedatetime pydbus youtube-dl --upgrade" will do that for you.
from __future__ import print_function  # This does not break Python 3 compatibility.

import traceback
import re
from argparse import ArgumentError
from io import open
from datetime import datetime, timedelta
from itertools import chain
from json import dumps, loads
from math import ceil
from random import randint

from gi.repository import GObject, GLib
from humanize import naturaldelta, naturaltime
from os import system as executeCommand
from pydbus import SessionBus
from parsedatetime import Calendar as datetimeParser
from time import strptime, sleep
from six import string_types, u
from youtube_dl import YoutubeDL as ydl


# Utility Functions:
# -----------------------------------------------
def dump(obj):
    """
    Dumps an object's properties into the console.
    @param obj The object to dump
    """
    map(lambda attr: print(u"obj.{} = {}".format(attr, getattr(obj, attr))), dir(obj))


def readFile(path):
    """
    Reads, then parses the file at the given path as json.

    @param path The file path of the file.
    @type path string_types
    @return The file parsed as json.
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

    @return All valid chat ids, filtering out any duplicate or invalid chats.
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

    @param path The file path of the file to overwrite.
    @type path string_types
    @param value The string_types string to overwrite the file with.
    @type value string_types
    """

    serializeDate = lambda dtOrStr: dtOrStr.strftime(dtFormatStr) if isinstance(dtOrStr, datetime) else None
    with open(path, mode=u"w", encoding=u"utf-8") as openFile:  # To update a file
        openFile.write(dumps(value, indent=4, default=serializeDate, ensure_ascii=False))
        # The default function allows it to dump datetime objects.


# Fixes rounding errors.
naturalTime = lambda time: naturaltime(time + timedelta(seconds=1))
naturalDelta = lambda time: naturaldelta(time - timedelta(seconds=1))


def getNameFromArgs(act, name, conv=None):
    """
    Gets a user's actual name given the account and name.
    @param act The account from the argSet.
    @param name The user's name from the argSet.
    @param conv The conversation from the argSet.
    @return The user's nickname, or their actual name if no nick was found.
    """
    act = purple.PurpleConversationGetAccount(conv) if conv is not None else act
    buddy = purple.PurpleFindBuddy(act, name)
    realName = purple.PurpleBuddyGetAlias(buddy) or purple.PurpleBuddyGetName(buddy)
    chat = None  # This is here so PyCharm doesn't complain about chat not existing in the return statement.
    if conv is not None:
        chat = getChatName(conv)
    return (nicks[chat].get(realName, realName) if conv is not None and chat in nicks else realName) or name


getChatName = lambda chatId: purple.PurpleConversationGetTitle(chatId)  # Gets the name of a chat given the chat's ID.


def getTime(currTime):
    """
    Given a natural time string, such as "in 30 minutes", returns that time as a datetime object.

    @param currTime A natural time string, such as "in 30 minutes" or "7 PM".
    @type currTime string_types
    @return The natural time as a datetime object.
    @rtype datetime
    """
    return parser.parseDT(currTime)[0]


def _formatCommandAndAliases(lst, formatStr):
    """
    Formats the commands and aliases alphabetically in a nice way.
    @param lst The list of commands/aliases.
    @type lst list
    @param formatStr The format string to use with the list of aliases.
    @type formatStr string_types
    @return The commands and aliases formatted alphabetically, as a unicode string.
    @rtype string_types
    """
    lastValue = None
    alphabeticalLists = []
    currentList = []
    for i in range(len(lst)):
        val = lst[i]
        if lastValue is None:
            lastValue = val
            currentList.append(val)
        elif lastValue[:1] != val[:1]:
            lastValue = val
            alphabeticalLists.append(currentList)
            currentList = []
        else:
            currentList.append(val)
    return formatStr.format(u"\n".join((u", ".join(alphabeticalList) for alphabeticalList in alphabeticalLists)))


def getAliases(argSet):
    """
    Returns all of the valid aliases, formatted nicely.
    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @return All of the valid aliases, formatted nicely.
    @rtype string_types
    """
    availableAliases = dict()
    convTitle = purple.PurpleConversationGetTitle(argSet[3])
    if convTitle in messageLinks:
        if isListButNotString(messageLinks[convTitle]):
            for conv in messageLinks[convTitle]:
                if conv in aliases:
                    availableAliases.update(aliases[conv])
        elif messageLinks[convTitle] in aliases:
            availableAliases.update(aliases[messageLinks[convTitle]])
    availableAliases.update(aliases[getChatName(argSet[3])])
    aliasList = list(sorted(availableAliases.keys()))
    return _formatCommandAndAliases(aliasList, u"Valid aliases: {}")


def getCommands(argSet):
    """
    Returns a list of all of the commands.
    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @return A list of all of the commands.
    @rtype string_types
    """
    commandList = list(sorted(commands.keys()))
    return _formatCommandAndAliases(commandList, u"Valid Commands: {}") + "\n" + getAliases(argSet)


def getFullConvName(partialName):
    """
    Returns a full conversation title given a partial title.

    @param partialName The incomplete name of the conversation.
    @type partialName string_types
    @return The conversation ID.
    @rtype int
    """
    conversations = [purple.PurpleConversationGetTitle(conv) for conv in getChats()]
    # Check the beginning first, if none start with the partial name, find it in there somewhere.
    return next((i for i in conversations if i[:len(partialName)] == partialName), None) or \
           next((i for i in conversations if partialName in i), None)


# Returns the conversation ID of a conversation given its partial name.
getConvFromPartialName = lambda partialName: getConvByName(getFullConvName(partialName))


def simpleReply(argSet, message):
    """
    Sends the message to the chat matching the given argSet.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param message The message to send out.
    @type message string_types
    """
    sendMessage(argSet[-2], argSet[-2], u"", message)  # Replies to a chat

    # Forwards the message to linked chats.
    conversation = argSet[3]
    nick = purple.PurpleAccountGetAlias(argSet[0])

    title = purple.PurpleConversationGetTitle(conversation)
    if title in messageLinks:  # Gets conversations by their title, so they work across libpurple reboots.
        if isListButNotString(messageLinks[title]):
            for receiving in messageLinks[title]:  # It can send to multiple chats.
                receiving = getConvByName(receiving)
                sendMessage(conversation, receiving, nick, message)
        else:
            receiving = getConvByName(messageLinks[title])
            sendMessage(conversation, receiving, nick, message)


# Gets the ID of a conversation, given its name. Does not work if a message has not been received from that chat yet.
getConvByName = lambda name: next(
    (i for i in getChats() if purple.PurpleConversationGetTitle(i) == name), None)

logFile = open(u"Pidgin_Crossover_Messages.log", mode=u"a")


def log(msg):
    """
    Writes msg into the console and appends it to the log file.
    @param msg The string to write.
    @type msg string_types
    """
    print(msg)
    # PyCharm thinks a TextIOWrapper is not an instance of Optional[IO]. PyCharm is incorrect.
    # noinspection PyTypeChecker
    print(msg, file=logFile)


# Returns what it says on the tin.
isListButNotString = lambda obj: isinstance(obj, (list, tuple, set)) and not isinstance(obj, string_types)

# Read files for persistent values.
messageLinks, puns, aliases, atLoc, scheduledEvents, nicks = readFiles(u"messageLinks.json", u"Puns.json",
    u"Aliases.json", u"atLoc.json", u"scheduledEvents.json", u"nicks.json")

commandDelimiter = u"!"  # What character(s) the commands should start with.
lastMessage = u""  # The last message, to prevent infinite looping.
defaultLocMinutes = 45
defaultLocTime = u"{} minutes".format(defaultLocMinutes)  # What to use when someone goes somewhere by default.
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
running = True
exitCode = 0
restartingBot = False
messageQueue = []
overflowThreshold = 3
runInTerminal = False
libpurpleClient = u"pidgin -c $PWD/.purple"


def replaceAliasVars(argSet, message):
    """
    Given the original message, replaces any alias vars (see above) with their proper values.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param message The message to replace. Will not use the message in argSet.
    @type message string_types
    @return Themessage, with all of the alias variables replaced.
    @rtype string_types    """
    newMsg = message  # Don't touch the original
    for i in aliasVars:
        try:
            newMsg = newMsg.replace(i[0], i[1](argSet))
        except:
            pass
    return newMsg


def restartFinch(*_):
    """
    Restarts finch using bash.
    :param _: All parameters are ignored.
    :return: None
    """
    global restartingBot
    if restartingBot:
        return
    print(u"Restarting libpurple client...")
    restartingBot = True
    executeCommand(u"killall -q {}".format(libpurpleClient))
    if runInTerminal:
        executeCommand(u"x-terminal-emulator -e \"{}\" &".format(libpurpleClient))
    else:
        executeCommand(libpurpleClient + u" &")
    sleep(1)
    restartingBot = False


def getPun(argSet, punFilter):
    """
    Gets a random pun, or a random pun that satisfies the provided filter.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param punFilter A string filtering the puns out.
    @type punFilter string_types
    @return A random pun from puns.json.
    @rtype string_types    """
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

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param page The page number it should be on, as a string_types string.
    @type page string_types
    """
    iteratableCommands = tuple(sorted(commands.keys()))  # A tuple containing all of the keys in iteratableCommands.
    commandsPerPage = 10  # How many commands to show per page.
    cmd = page[len(commandDelimiter):] if page.startswith(commandDelimiter) else page
    if cmd and cmd.lower() in helpText:  # If the help text for a given command was asked for
        simpleReply(argSet, helpText[cmd.lower()])
    elif not page or (page and page.isdigit()):  # If a page number was asked for
        page = int(page) if page and page.isdigit() else 1
        helpEntries = [
            u"Help page {}/{}".format(int(min(page, int(ceil(1.0 * len(iteratableCommands) / commandsPerPage)))),
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

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param chat The partial name of the chat to link the current chat to.
    @type chat string_types
    @param chats A list of all of the chats available.
    @type chats tuple
    """
    fullChatName = getFullConvName(chat)
    fullChatNames = sorted([getFullConvName(chat) for chat in chats])
    if fullChatName is None:
        simpleReply(argSet, u"No chat by name {} found.".format(chat))
        return
    for i in range(len(fullChatNames)):
        if fullChatNames[i] is None:
            simpleReply(argSet, u"No chat by name {} found.".format(chats[i]))
            return
    if fullChatName in messageLinks:
        messageLinks[fullChatName] = set(messageLinks[fullChatName])
        messageLinks[fullChatName].intersection(fullChatNames)
    else:
        messageLinks[fullChatName] = [fullChatNames, ]
    if len(messageLinks[fullChatName]) == 1:
        messageLinks[fullChatName] = messageLinks[fullChatName][0]
    updateFile(u"messageLinks.json", messageLinks)
    simpleReply(argSet, u"{} linked to {}.".format(u", ".join(str(i) for i in fullChatNames), fullChatName))


def Unlink(argSet, chat, *chats):
    """
    Unlinks chats from chat. Supports partial names.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param chat The partial name of the chat to unlink from the current chat.
    @type chat string_types
    @param chats A list of all of the chats available.
    @type chats tuple
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

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param pun The pun to add to the pun list.
    @type pun string_types
    """
    chat = getChatName(argSet[3])
    puns[chat] = puns[chat] if chat in puns else []
    puns[chat].append(str(pun))
    updateFile(u"Puns.json", puns)
    simpleReply(argSet, u"\"{}\" added to the pun list.".format(pun))


def removePun(argSet, pun):
    """
    Removes a pun from the pun list, then updates the file.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param pun The pun to remove from the pun list.
    @type pun string_types
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

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    """
    chat = getChatName(argSet[3])
    aliases[chat] = aliases[chat] if chat in aliases else {}
    message = argSet[2][7 + len(commandDelimiter):]
    if message == u"":
        return
    command = (message[:message.find(u" ")] if u" " in message else message).lower()
    command = command[len(commandDelimiter):] if command[:len(commandDelimiter)] == commandDelimiter else command
    argsMsg = message[message.find(u" ") + 1 + len(commandDelimiter):]
    if u" " not in message:  # If the user is asking for the command run by a specific alias.
        for _chat in messageLinks[chat]:
            if str(command) in aliases[_chat]:  # If the alias asked for does not exist.
                chat = _chat
                break
        else:
            simpleReply(argSet, u"No alias \"{}\" found.".format(str(command)))
            return
        simpleReply(argSet, u'"' + commandDelimiter + aliases[chat][str(command)] + u'"')
        return
    if str(command) in commands:
        simpleReply(argSet, u"That name is already used by a command!")
        return
    cmd = argsMsg[(len(commandDelimiter) if argsMsg.startswith(commandDelimiter) else 0):(
            u" " in argsMsg and argsMsg.find(u" ") or len(argsMsg))]
    if cmd not in commands:
        simpleReply(argSet, u"{}{} is not a command!".format(commandDelimiter, cmd))
        return
    aliases[chat][str(command)] = argsMsg
    simpleReply(argSet, u"\"{}\" bound to \"{}\".".format(commandDelimiter + command, commandDelimiter + argsMsg))
    updateFile(u"Aliases.json", aliases)


def removeAlias(argSet, alias=u"", *_):
    """
    Removes an alias to a command.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param alias The alias for the command.
    @type alias string_types
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

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param partialName The partial name of a user.
    @type partialName string_types
    @param nick Whether or not it should return the user's nickname.
    @type nick bool
    @return A user's alias.
    @rtype string_types
    """
    return getUserFromName(argSet, partialName, nick)


def getUserFromName(argSet, partialName, nick=True):
    """
    Returns the "name" of a user given their partial name.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param partialName The partial name of a user.
    @type partialName string_types
    @param nick Whether or not it should check nicknames.
    @type nick bool
    @return A user's "name".
    @rtype string_types
    """
    chat = getChatName(argSet[3])

    # Special case the bot's name
    botName = purple.PurpleAccountGetAlias(argSet[0])
    if partialName.lower() == botName[:len(partialName)].lower() or partialName.lower() in botName.lower():
        return botName if chat not in nicks or (u"" + botName) not in nicks[chat] or not nick else nicks[chat][
            u"" + botName]

    chats = [argSet[3]]
    if messageLinks[chat]:
        chats += [_chat for _chat in getChats() if getChatName(_chat) in messageLinks[chat]]
    users = dict()
    _users = list(chain([purple.PurpleConvChatGetUsers(purple.PurpleConvChat(int(chat)))] for chat in chats))
    for i in range(len(_users)):
        users[chats[i]] = _users[i][0]
    buddies = dict()
    for _chat, _users in users.items():
        buddies[_chat] = []
        for i in range(len(_users)):
            buddies[_chat].append(purple.PurpleConvChatCbGetName(_users[i]))
    names = []
    for _chat, _buddies in buddies.items():
        for buddy in _buddies:
            names.append(getNameFromArgs(argSet[0], buddy, _chat))
    del names[len(names) - 1]
    rng = range(len(names))
    # Check the beginning first, otherwise, check if the partialname is somewhere in the name.
    name = (next((names[i] for i in rng if names[i][:len(partialName)].lower() == partialName.lower()), None) or
            next((names[i] for i in rng if partialName.lower() in names[i].lower()), None))
    if nick and name is not None and chat in nicks and (u"" + name) in nicks[chat]:
        return nicks[chat][u"" + name]
    return name


def Mimic(argSet, user=None, firstWordOfCmd=None, *_):
    """
    Runs a command as a different user.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param user The partial name of the user to mimic.
    @type user string_types
    @param firstWordOfCmd The first word of the command to run, for syntax checking.
    @type firstWordOfCmd string_types
    """
    if user is None or firstWordOfCmd is None:
        simpleReply(argSet, u"You need to specify the user to mimic and the command to mimic!")
        return
    fullUser = getUserFromName(argSet, user, False)

    if fullUser is None:
        simpleReply(argSet, u"No user by the name \"{}\" found.".format(user))
        return
    elif fullUser == purple.PurpleAccountGetAlias(argSet[0]):  # If mimic is attempted on the bot
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

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    """
    findSpace = argSet[2].find(u" ")
    time = False
    location = None
    if findSpace is not None:
        findSpace2 = argSet[2].find(u" ", findSpace + 1)
        location = argSet[2][findSpace + 1:findSpace2] if \
            len(argSet[2]) > len(commandDelimiter) + 4 and argSet[2].count(u" ") > 1 else None
        time = argSet[2][findSpace2 + 1:]
    Loc(argSet, time=time or argSet[2], location=location)


def Loc(argSet, location=u"GDS", time=defaultLocTime):
    """
    Tells the chat you've gone somewhere. Has default values for ease of implementation.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param time The time in which you will be staying at the location.
    @type time string_types
    @param location The location you're going to.
    @type location string_types
    """
    chat = getChatName(argSet[3])
    time = time if len(time) != 0 else defaultLocTime
    atLoc[chat] = atLoc[chat] if chat in atLoc else {}
    # Update the time
    name = getNameFromArgs(argSet[0], argSet[1], argSet[3])
    atLoc[chat][name] = [now(), location, time]
    if u"in " in time or u"at " in time:
        newArgset = list(argSet)
        newArgset[2] = u"{0}schedule {1} {0}loc {2} {3}".format(commandDelimiter, time, location, defaultLocTime)
        messageListener(*newArgset)
        return

    simpleReply(argSet, u"{} is going to {} for {}.".format(getNameFromArgs(*argSet[:2]), location, time))
    updateFile(u"atLoc.json", atLoc)


def leftLoc(argSet, *_):
    """
    Tells the chat you've left wherever you are.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
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

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    """

    def toDate(string):
        """
        Converts the serialized datetime back to a datetime object, or uses now otherwise.

        @param string The serialized datetime, as a string_types string.
        @type string string_types
        @return The unserialized string, as a datetime object.
        @rtype datetime        """
        if type(string) == datetime:
            return string
        try:
            return datetime.strptime(string, dtFormatStr)
        except:
            return now()

    def toDelta(string):
        """
        Converts a serialized string back into a datetime object.

        @param string The serialized string.
        @type string string_types
        @return The serialized string, as a datetime object.
        @rtype timedelta
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
        now() - toDate(atLoc[chat][name][0]) < toDelta(atLoc[chat][name][2]) and
        (atLoc[chat][name][1] == location or location == u"anywhere")]
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

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
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
    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    """
    eventStrs = [u"[{}] {}: {} ({})".format(
        scheduledEvents.index(event),
        naturalTime(datetime.strptime(event[0], dtFormatStr) if type(event[0]) != datetime else event[0]),
        event[1][2],
        (datetime.strptime(event[0], dtFormatStr) if type(event[0]) != datetime else event[0]).strftime(dateFormatStr))
        for event in scheduledEvents if getNameFromArgs(argSet[0], *event[1][1:2]) == getNameFromArgs(*argSet[0:2])]
    if len(list(eventStrs)) == 0:
        simpleReply(argSet, u"You don't have any events scheduled!")
    else:
        simpleReply(argSet, u"\n".join(eventStrs))


def getAllEvents(argSet, *_):
    """
    Replies with all of the scheduled events.
    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
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
    @param argSet The set of values passed in to messageListener
    @type argSet tuple
    @param index The index of the event to be removed.
    @type index int
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
    @param argSet The set of values passed in to messageListener.
    @param user The partial name of the user whose nick is to be set.
    @param nick The new nickname.
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
    @param argSet The set of values passed in to messageListener.
    @param user The partial name of the user whose nick is to be removed.
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
    @param argSet The set of values passed in to messageListener.
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

    @param s The string to replace the numbers of with emojis.
    @type s string_types
    @return The provided string with its numbers replaced with emojis.
    @rtype string_types
    """
    for i in range(len(dice)):
        s = s.replace(u"" + str(i), dice[i])  # Force string_types strings for Python 2 and Python 3.
    return s


def exitProcess(code):
    """
    Exits like sys.exit, killing any other processes run by this one.
    @param code the exit code.
    """
    global running, exitCode
    running = False  # Go away, GLib.timeout.
    mainloop.quit()  # Go away, GObject.
    exitCode = code


def restartBot(argSet):
    """
    Restarts finch and the bot.
    """
    simpleReply(argSet, u"Restarting...")
    exitProcess(0)


def diceRoll(argSet, diceStr=u"", *_):
    """
    Returns a dice roll of the given dice.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param diceStr The string used to specify the type of dice, in the form [numDice]d[diceSides]
    @type diceStr string_types
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

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    """
    if len(args) == 0:
        simpleReply(argSet, u"You need to provide some arguments!")
        return
    user = args[-1]
    name = getFullUsername(argSet, user, False)
    nick = getFullUsername(argSet, user) or name
    if name is not None:
        msg = argSet[2]
        simpleReply(argSet,
            replaceAliasVars(argSet, msg[len(commandDelimiter) + 3:msg.rfind(u" ")]).replace(u"%target", nick))
    else:
        simpleReply(argSet, u"No user containing {} found.".format(user))


def findNthInstance(n, haystack, needle):
    """
    Finds the nth instance of needle in haystack.
    @type n int
    @param n How many instances to look for.
    @type haystack string_types
    @param haystack What to search through
    @type needle string_types
    @param needle What to look for.
    @return n, or 0 if none is found.
    """
    if n < 1:
        raise ArgumentError(message=u"You can't look for the nonpositive instance of something!")
    numFound = 0
    for i in range(len(haystack) - len(needle) + 1):
        numFound += haystack[i:i + len(needle)] == needle
        if numFound == n:
            return i
    return 0


def getYTURL(queryMsg):
    """
    Gets the URL of the first YouTube video when searching for queryMsg.
    @type queryMsg string_types
    @param queryMsg The search term to use to find the video.
    @rtype string_types
    @return The URL of the YouTube video, as a string.
    """
    dl = ydl()
    with dl:
        info = dl.extract_info(u"ytsearch1:" + queryMsg, download=False)[u"entries"][0]
        return u"{1} - https://youtube.com/watch?v={0}".format(info[u"id"], info[u"title"])


def listUsers(argSet, *_):
    """
    Lists all of the users in this chat and all connected ones.
    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    """
    chat = getChatName(argSet[3])
    chats = [argSet[3]]
    if messageLinks[chat]:
        chats += [_chat for _chat in getChats() if getChatName(_chat) in messageLinks[chat]]
    users = dict()
    _users = list(chain([purple.PurpleConvChatGetUsers(purple.PurpleConvChat(int(chat)))] for chat in chats))
    for i in range(len(_users)):
        users[chats[i]] = _users[i][0]
    buddies = dict()
    for _chat, _users in users.items():
        buddies[_chat] = []
        for i in range(len(_users)):
            buddies[_chat].append(purple.PurpleConvChatCbGetName(_users[i]))
    names = []
    for _chat, _buddies in buddies.items():
        for buddy in _buddies:
            names.append(getNameFromArgs(argSet[0], buddy, _chat))
    del names[len(names)-1]
    simpleReply(argSet, str(sorted(names)))


commands = {  # A dict containing the functions to run when a given command is entered.
    u"addpun": lambda argSet, *_: addPun(argSet, argSet[2][7 + len(commandDelimiter):]),
    u"alias": addAlias,
    u"aliases": lambda argSet, *_: simpleReply(argSet, getAliases(argSet)),
    u"allevents": getAllEvents,
    u"args": lambda argSet, *_: simpleReply(argSet, u"" + str(argSet)),
    u"atloc": AtLoc,
    u"botme": lambda argSet, *_: simpleReply(argSet,
        u"*{} {}.".format(purple.PurpleAccountGetAlias(argSet[0]), argSet[2][6 + len(commandDelimiter):])),
    u"chats": lambda argSet, *_: simpleReply(argSet,
        u"" + str([u"{} ({})".format(purple.PurpleConversationGetTitle(conv), conv) for conv in getChats()])[
        1:-1].replace(u"u'", u"'")),
    u"commands": lambda argSet, *_: simpleReply(argSet, getCommands(argSet)),
    u"diceroll": diceRoll,
    u"echo": lambda argSet, *_: simpleReply(argSet,
        argSet[2][argSet[2].lower().find(u"echo") + 4 + len(commandDelimiter):]),
    u"events": getEvents,
    u"exit": lambda *_: exitProcess(37),
    u"gds": lambda argSet, *_: Loc(argSet, time=argSet[2][len(commandDelimiter) + 4:]),
    u"help": Help,
    u"htmlescape": lambda argSet, *_: simpleReply(argSet, purple.PurpleMarkupStripHtml(argSet[2][11:])),
    u"lastreboot": lambda argSet, *_: simpleReply(argSet,
        u"{}, ({})".format(naturalTime(startTime), startTime.strftime("%a, %b %m %Y at %I:%M%p"))),
    u"leftloc": leftLoc,
    u"link": lambda argSet, *args: Link(argSet, *args),
    u"links": lambda argSet, *_: simpleReply(argSet, u"" + str(messageLinks)),
    u"loc": loc,
    u"loconly": lambda argSet, *_: Loc(argSet, location=argSet[2][len(commandDelimiter) + 8:]),
    u"me": lambda argSet, *_: simpleReply(argSet, replaceAliasVars(argSet,
        u"*{} {}.".format(getNameFromArgs(argSet[0], argSet[1], argSet[3]), argSet[2][3 + len(commandDelimiter):]))),
    u"mimic": Mimic,
    u"msg": lambda argSet, msg="", *_: sendMessage(argSet[-2], getConvFromPartialName(msg), u"",
        getNameFromArgs(*argSet[:2]) + ": " + argSet[2][
        argSet[2][4 + len(commandDelimiter):].find(u" ") + 5 + len(commandDelimiter):]),
    u"nicks": getNicks,
    u"ping": lambda argSet, *_: simpleReply(argSet, u"Pong!"),
    u"pun": lambda argSet, pun=u"", *_: simpleReply(argSet, getPun(argSet, pun)),
    u"removenick": removeNick,
    u"removepun": lambda argSet, pun, *_: removePun(argSet, pun),
    u"replace": lambda argSet, start, end, *_: simpleReply(argSet,
        re.compile(re.escape(start), re.IGNORECASE).sub(end, argSet[2][findNthInstance(3, argSet[2], u" ") + 1:])),
    u"restart": lambda argSet, *_: restartBot(argSet),
    u"schedule": scheduleEvent,
    u"setnick": setNick,
    u"to": to,
    u"unalias": removeAlias,
    u"unlink": lambda argSet, *args: Unlink(argSet, *args),
    u"unschedule": removeEvent,
    u"users": listUsers,
    u"yt": lambda argSet, *query: simpleReply(argSet, getYTURL(argSet[2])),
}
helpText = {  # The help text for each command.
    u"addpun": u"Adds a pun to the list of random puns.",
    u"alias": u"Links a name to a command, or prints out the command run by an alias.",
    u"aliases": u"Lists all of the aliases.",
    u"aliasvars": u"%sendername, %botname, %chattitle, %chatname",
    u"allevents": u"Lists all scheduled events.",
    u"args": u"Prints out the arguments received from this message.",
    u"atloc": u"Replies with who's said they're somewhere within the last hour and where they are.",
    u"botme": u"Replies \"*(bot's name) (message)\", e.g. \"*NickBot DeLello died.\"",
    u"chats": u"Lists all chats the bot knows of by name and ID.",
    u"commands": u"Lists all of the commands.",
    u"diceroll": u"Rolls the specified number of dice, returning the min, max, and sum of the rolls. 1d6 by default.",
    u"echo": u"Repeats the message said.",
    u"events": u"Lists all of the events you have scheduled.",
    u"exit": u"Exits the bot.",
    u"gds": u"Tells the chat you're going to GDS for some period of time.",
    u"help": u"Prints out the syntax and usage of each command.",
    u"lastreboot": u"Returns when the bot was started up.",
    u"leftloc": u"Tells the chat you've left somewhere.",
    u"link": u"Links from the first chat to the following chats.",
    u"links": u"Prints out the current message links.",
    u"loc": u"Tells the chat you've gone somewhere.",
    u"loconly": u"Tells the chat you're going somewhere for an hour.",
    u"me": u"Replies \"*(username) (message)\", e.g. \"*Gian Laput is French.\"",
    u"mimic": u"Runs the specified command as if it was run by the specified user.",
    u"msg": u"Sends a message to the specified chat. Matches incomplete names.",
    u"nicks": u"Lists the nicknames of all users in the chat. If they don't have one, their name will not show up!",
    u"ping": u"Replies \"Pong!\". Useful for checking if the bot is working.",
    u"pun": u"Replies with a random pun.",
    u"removenick": u"Removes a user's nickname.",
    u"removepun": u"Removes a pun from the list of puns.",
    u"replace": u"Replaces the text in the last argument(s) using the first and second.",
    u"restart": u"Restarts the bot.",
    u"schedule": u"Runs a command after the specified amount of time.",
    u"setnick": u"Changes the nickname of the specified user.",
    u"to": u"Sends a message with the provided person as a 'target'. Mainly used for aliases.",
    u"unalias": u"Unlinks a name from a command.",
    u"unlink": u"Unlinks the second and further chats from the first chat.",
    u"unschedule": u"Unschedules the event with the given index. (The index should be from {}events)".format(
        commandDelimiter),
    u"users": u"Lists all of the users in the current chat.",
    u"yt": u"Searches for a YouTube video using the query provided, and replies with the first result's URL."
}


def runCommand(argSet, command, *args):
    """
    Runs the command given the argSet and the command it's trying to run.

    @param argSet The set of values passed in to messageListener.
    @type argSet tuple
    @param command The command to run.
    @type command string_types
    @return If the given command could be run, either as a command or an alias.
    @rtype bool
    """
    command = (command or argSet[2][:argSet[2].find(u" ")]).lower()
    chat = getChatName(argSet[3])
    aliases[chat] = aliases[chat] if chat in aliases else {}
    if command in commands:
        commands[command](argSet, *args)
        return True
    else:
        cmd = aliases[chat][command] if command in aliases[chat] else None
        convTitle = purple.PurpleConversationGetTitle(argSet[3])
        if convTitle in messageLinks:
            if isListButNotString(messageLinks[convTitle]):
                for conv in messageLinks[convTitle]:
                    if conv in aliases and command in aliases[conv]:
                        cmd = aliases[conv][command]
                        break
            else:
                if messageLinks[convTitle] in aliases and command in aliases[messageLinks[convTitle]]:
                    cmd = aliases[messageLinks[convTitle]][command]
        if cmd is not None:
            message = argSet[2]
            msgLow = message.lower()
            command = message[len(commandDelimiter):message.find(u" ") if u" " in message else len(message)].lower()
            # Swap the command for the right one
            message = message[:msgLow.find(command)] + command + message[msgLow.find(command) + len(command):]
            newMsg = replaceAliasVars(argSet, message.replace(command, cmd, 1))
            # Get the extra arguments to the function and append them at the end.
            extraArgs = newMsg.split(u" ")[1:]
            commands[cmd.split(u" ", 1)[0]]((argSet[0], argSet[1], newMsg, argSet[3], argSet[4]),
                *extraArgs)  # Run the alias's command
            return True
    return False


def sendMessage(sending, receiving, nick, message):
    """
    Sends a message on the given chat.

    @param sending The id of the sending chat.
    @type sending int
    @param receiving The id of the receiving chat.
    @type receiving int
    @param nick The nickname of the user, for logging purposes
    @type nick string_types
    @param message The message to send out.
    @type message string_types
    """
    if receiving is None:  # If the conversation can't be found by libpurple, it'll just error anyway.
        return

    protocol = purple.PurpleAccountGetProtocolName(purple.PurpleConversationGetAccount(receiving))
    boldOpeningChar = u"*" if protocol.lower() == u"facebook" else u"<b>"
    boldClosingChar = u"*" if protocol.lower() == u"facebook" else u"</b>"

    # Actually send the messages out.
    if purple.PurpleConversationGetType(receiving) == 2:  # 2 means a group chat.
        conv = purple.PurpleConvChat(receiving)
        purple.PurpleConvChatSend(conv, ((u"_" + boldOpeningChar if nick[:len(
            commandDelimiter)] == commandDelimiter else boldOpeningChar) + nick + boldClosingChar + u": " if nick else u"") + message.replace(
            u"\n", u"<br>"))
    else:
        conv = purple.PurpleConvIm(receiving)
        purple.PurpleConvImSend(conv, ((u"_" + boldOpeningChar if nick[:len(
            commandDelimiter)] == commandDelimiter else boldOpeningChar) + nick + boldClosingChar + u": " if nick else u"") + message.replace(
            u"\n", u"<br>"))

    # I could put this behind debug, but I choose not to. It's pretty enough.
    sendTitle = purple.PurpleConversationGetTitle(sending)
    receiveTitle = purple.PurpleConversationGetTitle(receiving)
    try:  # Logging errors should not break things.
        log(u"[{}] Sent \"{}\" from {} ({}) to {} ({}).".format(now().isoformat(),
            (nick + u": " + message if nick else message), sendTitle, sending, receiveTitle, conv))
        logFile.flush()  # Update the log since it's been written to.
    except UnicodeError:
        pass


def messageListener(account, sender, message, conversation, flags):
    """
    The function that runs when a message is received.

    @param account The account the message was received on.
    @type account int
    @param sender The name of the chat the message was sent from.
    @type sender string_types
    @param message The received message.
    @type message string_types
    @param conversation The conversation in which this message was received.
    @type conversation int
    @param flags Any flags for this message, such as the type of message.
    @type flags tuple
    """
    global lastMessageTime, lastMessage
    try:
        message = u"" + message.decode(encoding=u"utf-8", errors=u"ignore")
    except:
        message = u"" + message
    try:
        lastMessage = u"" + lastMessage.decode(encoding=u"utf-8", errors=u"ignore")
    except:
        lastMessage = u"" + lastMessage
    argSet = (account, sender, message, conversation, flags)
    print(*[u"" + u(repr(arg)) for arg in argSet])
    print(*[purple.PurpleMarkupStripHtml(u"" + u(repr(arg))) for arg in argSet])
    lastMessageTime = now()

    # Strip HTML from Hangouts messages.
    message = purple.PurpleMarkupStripHtml(message) if message.startswith(u"<") else message

    nick = getNameFromArgs(account, sender) or sender  # Name which will appear on the log.

    try:  # Logs messages. Logging errors will not prevent commands from working.
        log(u"[{}] {}: {}\n".format(now().isoformat(), nick, (u"" + str(message))))
        logFile.flush()
    except UnicodeError:
        pass
    # Run commands if the message starts with the command character.
    global wasCommand
    wasCommand = False
    if message[:len(commandDelimiter)] == commandDelimiter:
        wasCommand = True
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

    # Send messages to connected chats.
    try:
        if message == lastMessage:  # Makes sure the messages don't loop infinitely.
            return
    except:
        pass
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
    """
    Processes any events that are in the eventQueue.
    @param threshold How long after the event is supposed to run until it's discarded.
    @type threshold timedelta
    @return True
    @rtype bool
    """
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


def queueMessage(account, sender, message, conversation, flags):
    """
    Queues up a message for messageListener to allow for rate-limiting.
    @param account The account the message was received on.
    @type account int
    @param sender The name of the chat the message was sent from.
    @type sender string_types
    @param message The received message.
    @type message string_types
    @param conversation The conversation in which this message was received.
    @type conversation int
    @param flags Any flags for this message, such as the type of message.
    @type flags tuple
    """
    argSet = (account, sender, message, conversation, flags)
    if purple.PurpleAccountGetAlias(account) == sender or \
            purple.PurpleAccountGetAlias(account) == getNameFromArgs(account, sender) or \
            purple.PurpleAccountGetUsername(account) == sender:
        return
    messageQueue.append(argSet)


def periodicLoop():
    """
    Used for any tasks that may need to run in the background.

    @return True
    @rtype True
    """
    processEvents()
    msgQueueLen = len(messageQueue)
    if msgQueueLen > 0:
        if msgQueueLen <= overflowThreshold:
            for argSet in reversed(messageQueue):
                try:
                    messageListener(*argSet)
                except:
                    print(u"Error in messageListener!\n", traceback.format_exc())
        del messageQueue[:]  # Empties the queue

    return running


bus = SessionBus()  # Initialize the DBus interface
purple = bus.get(u"im.pidgin.purple.PurpleService", u"/im/pidgin/purple/PurpleObject")  # Connect to libpurple clients.

# Surprisingly, im.pidgin.* and im/pidgin/* work for Finch too. Not sure why.
purple.ReceivedImMsg.connect(queueMessage)
purple.ReceivedChatMsg.connect(queueMessage)

GLib.timeout_add_seconds(1, periodicLoop)  # Run periodicLoop once per second.
mainloop = GObject.MainLoop()
mainloop.run()  # Actually run the program.

exit(exitCode)  # Make sure the process exists with the correct error code.
