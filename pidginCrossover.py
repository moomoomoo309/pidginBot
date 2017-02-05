#!/usr/bin/env python
# coding: UTF-8

# emoji, humanize and PyGObject are dependencies. "pip install emoji pygobject humanize --upgrade" will do that for you.
from __future__ import print_function

from datetime import datetime, timedelta
from json import dumps, loads
from math import ceil
from random import randint
from sys import exit
from emoji import demojize, emojize  # This dependency is 👍
from emoji.unicode_codes import UNICODE_EMOJI as emojis
from gi.repository import GObject, GLib
from humanize import naturaldelta, naturaltime
from pydbus import SessionBus
from parsedatetime import Calendar as datetimeParser
from time import strptime


# Utility Functions:
# -----------------------------------------------
def readFile(path):
    """
    Reads, then parses the file at the given path as json.

    :param path: The file path of the file.
    :type path: unicode
    :return: The file parsed as json.
    """
    with open(path, mode="r") as fileHandle:  # With is nice and clean.
        out = None
        strFile = fileHandle.read(-1)
        if out is None and strFile != u"":
            try:
                out = loads(strFile)  # json.loads is WAY faster than ast.literal_eval!
            except ValueError:
                pass
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
    return chatIDs.values()


def updateFile(path, value):
    """
    Replaces the contents of the file at the given path with the given value.

    :param path: The file path of the file to overwrite.
    :type path: unicode
    :param value: The unicode string to overwrite the file with.
    :type value: unicode
    """

    def serializeDate(string):
        if isinstance(string, datetime):
            return string.strftime(u'%a, %d %b %Y %H:%M:%S UTC')
        return None

    with open(path, mode="w") as openFile:  # To update a file
        openFile.write(dumps(value, openFile, indent=4, default=serializeDate))
        # The default function allows it to dump datetime objects.


naturalTime = lambda time: naturaltime(time + timedelta(seconds=1))  # Fixes rounding errors.
naturalDelta = lambda time: naturaldelta(time - timedelta(seconds=1))  # Fixes rounding errors.

# Gets a user's actual name given the account and name.
getNameFromArgs = lambda act, name: purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(act, name))

getChatName = lambda chatId: purple.PurpleConversationGetTitle(chatId)  # Gets the name of a chat given the chat's ID.


def getTime(currTime):
    """
    Given a natural time string, such as "in 30 minutes", returns that time as a datetime object.

    :param currTime: A natural time string, such as "in 30 minutes" or "7 PM".
    :type currTime: unicode
    :return: The natural time as a datetime object.
    :rtype: datetime
    """
    return parser.parseDT(currTime)[0]


getCommands = lambda argSet: u"Valid Commands: {}, Valid Aliases: {}".format(u", ".join(sorted(commands.keys())),
    u", ".join(sorted(aliases[getChatName(argSet[3])].keys())))  # Returns a list of all of the commands.


def getFullConvName(partialName):
    """
    Returns a full conversation title given a partial title.

    :param partialName: The incomplete name of the conversation.
    :type partialName: unicode
    :return: The conversation ID.
    :rtype: int
    """
    conversations = [purple.PurpleConversationGetTitle(conv) for conv in getChats()]
    # Check the beginning first, if none start with the partial name, find it in there somewhere.
    return next((i for i in conversations if i[0:len(partialName)] == partialName), None) or next(
        (i for i in conversations if partialName in i), None)


# Returns the conversation ID of a conversation given its partial name.
getConvFromPartialName = lambda partialName: getConvByName(getFullConvName(partialName))


def simpleReply(argSet, message):
    """
    Sends the message to the chat matching the given argSet.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param message: The message to send out.
    :type message: unicode
    """
    sendMessage(argSet[-2], argSet[-2], u"", message)  # Replies to a chat


# Gets the ID of a conversation, given its name. Does not work if a message has not been received from that chat yet.
getConvByName = lambda name: next(
    (i for i in getChats() if purple.PurpleConversationGetTitle(i) == name), None)

logFile = open("Pidgin_Crossover_Messages.log", mode="a")
# Writes a string to the log file.
logStr = lambda string: logFile.write(str(u"[{}] {}\n".format(now().isoformat(), demojize(string))))
log = lambda string: [fct(string + u"\n") for fct in (print, logStr)]  # Prints and writes to the log file.

# Returns what it says on the tin.
isListButNotString = lambda obj: isinstance(obj, (list, tuple, set)) and not isinstance(obj, (str, unicode))
# ---------------------------------------

# Read files for persistent values.
messageLinks, puns, aliases, atLoc, scheduledEvents = readFiles(u"messageLinks.json", u"Puns.json", u"Aliases.json",
    u"atLoc.json", u"scheduledEvents.json")

commandDelimiter = u"!"  # What character(s) the commands should start with.
lastMessage = u""  # The last message, to prevent infinite looping.
now = datetime.now
lastMessageTime = now()
parser = datetimeParser()
messageLinks = messageLinks or {}
puns = puns or {}
aliases = aliases or {}
atLoc = atLoc or {}
scheduledEvents = scheduledEvents or []
aliasVars = [  # Replace the string with the result from the lambda below.
    ("%sendername", lambda argSet: getNameFromArgs(*argSet[:2])),
    ("%botname", lambda argSet: purple.PurpleAccountGetAlias(argSet[0])),
    ("%chattitle", lambda argSet: purple.PurpleConversationGetTitle(argSet[3])),
    ("%chatname", lambda argSet: purple.PurpleConversationGetName(argSet[3]))
]


def replaceAliasVars(argSet, message):
    """
    Given the original message, replaces any alias vars (see above) with their proper values.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param message: The message to replace. Will not use the message in argSet.
    :type message: unicode
    :return The message, with all of the alias variables replaced.
    :rtype unicode
    """
    newMsg = message  # Don't touch the original
    for i in aliasVars:
        newMsg = newMsg.replace(i[0], i[1](argSet))
    return newMsg


def getPun(argSet, punFilter):
    """
    Gets a random pun, or a random pun that satisfies the provided filter.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param punFilter: A string filtering the puns out.
    :type punFilter: unicode
    :return: A random pun from puns.json.
    :rtype unicode
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
    :param page: The page number it should be on, as a unicode string.
    :type page: unicode
    """
    iteratableCommands = commands.keys()  # A tuple containing all of the keys in iteratableCommands.
    commandsPerPage = 10  # How many commands to show per page.
    cmd = page[len(commandDelimiter):] if page.startswith(commandDelimiter) else page
    if cmd and cmd.lower() in helpText:  # If the help text for a given command was asked for
        simpleReply(argSet, helpText[cmd.lower()])
    elif not page or (page and page.isdigit()):  # If a page number was asked for
        page = int(page) if page and page.isdigit() else 1
        helpStr = u""
        helpStr += u"Help page {}/{}".format(int(min(page, ceil(1.0 * len(iteratableCommands) / commandsPerPage))),
            int(ceil(1.0 * len(iteratableCommands) / commandsPerPage)))
        for i in range(max(0, (page - 1) * commandsPerPage), min(page * commandsPerPage, len(iteratableCommands))):
            helpStr += u"\n" + iteratableCommands[i] + u": " + (
                helpText[iteratableCommands[i]] if iteratableCommands[i] in helpText else u"")
        simpleReply(argSet, helpStr)
    else:
        simpleReply(argSet, u"No command \"{}\" found.".format(page))


def Link(argSet, chat, *chats):
    """
    Links chats to chat. Supports partial names.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param chat: The partial name of the chat to link the current chat to.
    :type chat: unicode
    :param chats: A list of all of the chats available.
    :type chats: tuple
    """
    fullChatName = getFullConvName(chat)
    fullChatNames = [getFullConvName(chat) for chat in chats]
    if fullChatName in messageLinks:
        messageLinks[fullChatName].append(*fullChatNames)
    else:
        messageLinks[fullChatName] = fullChatNames
    if len(messageLinks[fullChatName]) == 1:
        messageLinks[fullChatName] = messageLinks[fullChatName][0]
    updateFile(u"messageLinks.json", messageLinks)
    simpleReply(argSet, u"{} linked to {}.".format(", ".join(str(i) for i in fullChatNames), fullChatName))


def Unlink(argSet, chat, *chats):
    """
    Unlinks chats from chat. Supports partial names.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param chat: The partial name of the chat to unlink from the current chat.
    :type chat: unicode
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
        elif isinstance(messageLinks[fullChatName], dict) and fullName in messageLinks[fullChatName]:
            removedChats.append(messageLinks[fullChatName].pop(messageLinks[fullChatName].index(fullName)))
    updateFile(u"messageLinks.json", messageLinks)  # Update the messageLinks file.
    simpleReply(argSet, u"{} unlinked from {}.".format(u", ".join(removedChats), fullChatName))


def addPun(argSet, pun):
    """
    Adds a pun to the pun list, then updates the file.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param pun: The pun to add to the pun list.
    :type pun: unicode
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
    :type pun: unicode
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
    if message == "":
        return
    command = (message[:message.find(u" ")] if u" " in message else message).lower()
    argsMsg = message[message.find(u" ") + 1 + len(commandDelimiter):]
    args = [str(arg) for arg in argsMsg.split(u" ")]
    if u" " not in message:  # If the user is asking for the command run by a specific alias.
        if str(command) not in aliases[chat]:  # If the alias asked for does not exist.
            simpleReply(argSet, u"No alias \"{}\" found.".format(str(command)))
            return
        simpleReply(argSet, u'"' + commandDelimiter + aliases[chat][str(command)][0] + '"')
        return
    if str(command) in commands:
        simpleReply(argSet, u"That name is already used by a command!")
        return
    cmd = argsMsg[(len(commandDelimiter) if argsMsg.startswith(commandDelimiter) else 0):(
        " " in argsMsg and argsMsg.find(u" ") or len(argsMsg))]
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
    :type alias: unicode
    """
    chat = getChatName(argSet[3])
    aliases[chat] = aliases[chat] if chat in aliases else {}
    if not alias:
        simpleReply(argSet, u"Enter an alias to remove!")
        return
    if alias[len(commandDelimiter):] in aliases[chat]:
        aliases[chat].pop(alias[len(commandDelimiter):])
    else:
        simpleReply(argSet, u"No alias \"{}\" found.".format(alias))
        return
    simpleReply(argSet, u"\"{}\" unaliased.".format(alias))
    updateFile(u"Aliases.json", aliases)


def getFullUsername(argSet, partialName):
    """
    Returns a user's alias given their partial name.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param partialName: The partial name of a user.
    :type partialName: unicode
    :return: A user's alias.
    :rtype: unicode
    """
    buddies = [purple.PurpleConvChatCbGetName(user) for user in
        purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]
    names = [getNameFromArgs(argSet[0], buddy) for buddy in buddies]
    # Check the beginning first, otherwise, check if the partialname is somewhere in the name.
    name = (next((names[i] for i in range(len(names)) if names[i][0:len(partialName)].lower() == partialName.lower()),
        None) or next((names[i] for i in range(len(names)) if partialName.lower() in names[i].lower()), None))
    return u"" + name if name is not None else None


def getUserFromName(argSet, partialName):
    """
    Returns the "name" of a user given their partial name.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param partialName: The partial name of a user.
    :type partialName: unicode
    :return: A user's "name".
    :rtype: unicode
    """
    buddies = [purple.PurpleConvChatCbGetName(user) for user in
        purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]
    names = [getNameFromArgs(argSet[0], buddy) for buddy in buddies]
    # Check the beginning first, otherwise, check if the partialname is somewhere in the name.
    name = (next((buddies[i] for i in range(len(names)) if names[i][0:len(partialName)].lower() == partialName.lower()),
        None) or next((buddies[i] for i in range(len(names)) if partialName.lower() in names[i].lower()), None))
    return u"" + name if name is not None else None


def Mimic(argSet, user=None, firstWordOfCmd=None, *_):
    """
    Runs a command as a different user.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param user: The partial name of the user to mimic.
    :type user: unicode
    :param firstWordOfCmd: The first word of the command to run, for syntax checking.
    :type firstWordOfCmd: unicode
    """
    if user is None or firstWordOfCmd is None:
        simpleReply(argSet, u"You need to specify the user to mimic and the command to mimic!")
        return
    fullUser = getUserFromName(argSet, user)
    if fullUser is None:
        simpleReply(argSet, u"No user by the name \"{}\" found.".format(user))
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
    time = argSet[2][len(commandDelimiter) + 4:argSet[2].find(u" ", len(commandDelimiter) + 4)]
    location = argSet[2][argSet[2].find(u" ", len(commandDelimiter) + 4) + 1:] if len(argSet[2]) > len(
        commandDelimiter) + 4 else u"GDS"
    Loc(argSet, time, location)


def Loc(argSet, time=u"30 minutes", location=u"GDS"):
    """
    Tells the chat you've gone somewhere. Has default values for ease of implementation.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param time: The time in which you will be staying at the location.
    :type time: unicode
    :param location: The location you're going to.
    :type location: unicode
    """
    chat = getChatName(argSet[3])
    time = time if len(time) != 0 else u"30 minutes"
    atLoc[chat] = atLoc[chat] if chat in atLoc else {}
    # Update the time
    name = purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(*argSet[:2]))
    atLoc[chat][name] = [now(), location, time]

    dateTime, appendMsg = None, ""
    try:
        dateTime = getTime(time)
    except:
        appendMsg = time
    simpleReply(argSet,
        u"{} is going to {}{} for {}.".format(
            getNameFromArgs(*argSet[:2]),
            location,
            (u" " + appendMsg if len(appendMsg) > 0 else ""),
            naturalDelta(now() - dateTime) if dateTime is not None else ""
        )
    )
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

        :param string: The serialized datetime, as a unicode string.
        :type string: unicode
        :return: The unserialized string, as a datetime object.
        :rtype datetime
        """
        if type(string) == datetime:
            return string
        try:
            return datetime.strptime(string, u'%a, %d %b %Y %H:%M:%S UTC')
        except:
            return now()

    def toDelta(string):
        """
        Converts a serialized unicode string back into a datetime object.

        :param string: The serialized unicode string.
        :type string: unicode
        :return: The serialized string, as a datetime object.
        :rtype: timedelta
        """
        if type(string) == timedelta:
            if string > timedelta():
                return string
            else:
                return timedelta(minutes=30)
        try:
            return strptime(string, u"%H:%M:%S")
        except:
            return timedelta(minutes=30)

    location = argSet[2][len(commandDelimiter) + 6:] if u" " in argSet[2] else u"anywhere"
    chat = getChatName(argSet[3])
    atLoc[chat] = atLoc[chat] if chat in atLoc else {}

    # Filter out people who have been somewhere in the last hour
    lastHour = [name for name in atLoc[chat].keys() if
        now() - toDate(atLoc[chat][name][0]) < toDelta(atLoc[chat][name][2]) and (
            atLoc[chat][name][1] == location or location == u"anywhere")]
    # Write the names to a string.
    strPeopleAtLoc = u"".join([u"{} went to {} {} ago. ".format(
        n, atLoc[chat][n][1], naturalDelta(now() - toDate(atLoc[chat][n][0]))) for n in lastHour])
    if lastHour:
        simpleReply(argSet, strPeopleAtLoc)
    else:  # If no one has been to a location
        simpleReply(argSet,
            u"No one went {} in the last hour.".format(location if location == u"anywhere" else u"to " + location))


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
        simpleReply(argSet, u"You need a command to run, with the command delimiter (u" + commandDelimiter + u").")
        return
    newArgset = list(argSet)
    newArgset[2] = cmdStr
    scheduledEvents.append((getTime(timeStr), newArgset))
    updateFile(u"scheduledEvents.json", scheduledEvents)
    simpleReply(argSet, u"\"{}\" scheduled to run {}.".format(cmdStr, naturalTime(getTime(timeStr))))


def getEvents(argSet, *_):
    """
    Tells the user what events they have scheduled.
    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    """
    eventStrs = [u"[{}] {}: {}".format(scheduledEvents.index(event),
        naturalTime(datetime.strptime(event[0], u'%a, %d %b %Y %H:%M:%S UTC') if type(event[0]) != datetime else event[0]),event[1][2])
        for event in scheduledEvents if getNameFromArgs(*event[1][0:2]) == getNameFromArgs(*argSet[0:2])]
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
    eventStrs = (u"[{}] {} in {}: {}".format(event[0], getNameFromArgs(*event[1][1][0:2]),
        naturalTime(datetime.strptime(event[1][0], u'%a, %d %b %Y %H:%M:%S UTC')
        if type(event[0]) != datetime else event[1][0]),event[1][1][2]) for event in enumerate(scheduledEvents))
    finalStr = u"\n".join(eventStrs)
    if len(finalStr)<9:
        simpleReply(argSet, u"No events have been scheduled.")
    else:
        simpleReply(argSet, finalStr)


def removeEvent(argSet, index, *_):
    """
    Removes a scheduled event.
    :param argSet: The set of values passed in to messageListener
    :type argSet: tuple
    :param index: The index of the event to be removed.
    :type index: int
    """
    userEvents = (e for e in scheduledEvents if getNameFromArgs(*e[1][0:2]) == getNameFromArgs(*argSet[0:2]))
    index = int(index)
    if scheduledEvents[index] in userEvents:
        scheduledEvents.pop(index)
        simpleReply(argSet, u"Event at index {} removed.".format(index))
    else:
        simpleReply(argSet, u"You don't have an event scheduled with that index!")


dice = [u"0⃣", u"1⃣", u"2⃣", u"3⃣", u"4⃣", u"5⃣", u"6⃣", u"7⃣", u"8⃣", u"9⃣️⃣️"]  # 1-9 in emoji form


def numToEmoji(s):
    """
    Replaces numbers with emojis.

    :param s: The string to replace the numbers of with emojis.
    :type s: unicode
    :return: The provided string with its numbers replaced with emojis.
    :rtype: unicode
    """
    for i in range(len(dice)):
        s = s.replace(u"" + str(i), dice[i])  # Force unicode strings for Python 2 and Python 3.
    return s


def diceRoll(argSet, diceStr="", *_):
    """
    Returns a dice roll of the given dice.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param diceStr: The string used to specify the type of dice, in the form [numDice]d[diceSides]
    :type diceStr: unicode
    """
    numDice, numSides = 1, 6  # Defaults to 1d6
    if u"d" in diceStr.lower():
        numDice, numSides = int(diceStr[:diceStr.lower().find(u"d")]), int(diceStr[diceStr.lower().find(u"d") + 1:])
    elif diceStr.isdigit():
        numDice = int(diceStr)
    rolls = [randint(1, numSides) for _ in range(numDice)]  # Roll the dice
    simpleReply(argSet,
        numToEmoji(u"".join(str(s) + u", " for s in rolls) + u"Sum={}, Max={}, Min={}".format(sum(rolls), max(rolls),
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
    name = getFullUsername(argSet, user)
    if name is not None:
        simpleReply(argSet,
            replaceAliasVars(argSet, argSet[2][len(commandDelimiter) + 3:argSet[2].rfind(u" ")]).replace(u"%target",
                name))
    else:
        simpleReply(argSet, u"No user containing {} found.".format(user))


commands = {  # A dict containing the functions to run when a given command is entered.
    u"help": Help,
    u"ping": lambda argSet, *_: simpleReply(argSet, u"Pong!"),
    u"chats": lambda argSet, *_: simpleReply(argSet,
        u"" + str([u"{} ({})".format(purple.PurpleConversationGetTitle(conv), conv) for conv in getChats()])[
        1:-1].replace(
            "u'", "'")),
    u"args": lambda argSet, *_: simpleReply(argSet, u"" + str(argSet)),
    u"echo": lambda argSet, *_: simpleReply(argSet,
        argSet[2][argSet[2].lower().find(u"echo") + 4 + len(commandDelimiter):]),
    u"exit": lambda *_: exit(37),
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
        "Valid aliases: {}".format(u", ".join(aliases[getChatName(argSet[3])].keys())).replace(u"u'", u"'")),
    u"me": lambda argSet, *_: simpleReply(argSet, u"*{} {}.".format(
        purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(*argSet[:2])), argSet[2][3 + len(commandDelimiter):])),
    u"botme": lambda argSet, *_: simpleReply(argSet, u"*{} {}.".format(purple.PurpleAccountGetAlias(argSet[0]),
        argSet[2][6 + len(commandDelimiter):])),
    u"randomemoji": lambda argSet, amt=1, *_: simpleReply(argSet, u"".join(
        [emojis.values()[randint(0, len(emojis) - 1)] for _ in range(int(amt) or 1)])),
    u"mimic": Mimic,
    u"users": lambda argSet, *_: simpleReply(argSet, emojize(str(
        [purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(argSet[0], purple.PurpleConvChatCbGetName(user))) for user in
            purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]), use_aliases=True)),
    u"loc": loc,
    u"gds": lambda argSet, *_: Loc(argSet, time=argSet[2][len(commandDelimiter) + 4:]),
    u"loconly": lambda argSet, *_: Loc(argSet, location=argSet[2][len(commandDelimiter) + 8:]),
    u"atloc": AtLoc,
    u"leftloc": leftLoc,
    u"diceroll": diceRoll,
    u"restart": lambda *_: exit(0),
    u"commands": lambda argSet, *_: simpleReply(argSet, getCommands(argSet)),
    u"to": to,
    u"schedule": scheduleEvent,
    u"events": getEvents,
    u"allevents": getAllEvents,
    u"unschedule": removeEvent
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
    u"unschedule": "Unschedules the event with the given index. (The index should be from {}events)".format(
        commandDelimiter)
}


def runCommand(argSet, command, *args):
    """
    Runs the command given the argSet and the command it's trying to run.

    :param argSet: The set of values passed in to messageListener.
    :type argSet: tuple
    :param command: The command to run.
    :type command: unicode
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
        command = message[len(commandDelimiter):message.find(u" ") if u" " in message else len(message)].lower()
        message = message[:message.lower().find(command)] + command + message[
        message.lower().find(command) + len(command):]
        newMsg = replaceAliasVars(argSet, (message + (u" ".join(tuple(args)) if len(
            tuple(aliases[chat][command][1][len(commandDelimiter):])) > 0 else u"")).replace(command,
            aliases[chat][command][0]))
        commands[aliases[chat][command][1][0]]((argSet[0], argSet[1], newMsg, argSet[3], argSet[4]), *(
            (tuple(args) if len(
                tuple(aliases[chat][command][1][len(commandDelimiter):])) > 0 else ())))  # Run the alias's command
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
    :type nick: unicode
    :param message: The message to send out.
    :type message: unicode
    """
    if receiving is None:  # If the conversation can't be found by libpurple, it'll just error anyway.
        return

    if message[0:len(commandDelimiter)] == commandDelimiter:  # Do not send out commands! No! Bad!
        message = (u"_" if commandDelimiter[0] != u"_" else u" ") + message

    # Actually send the messages out.
    if purple.PurpleConversationGetType(receiving) == 2:  # 2 means a group chat.
        conv = purple.PurpleConvChat(receiving)
        purple.PurpleConvChatSend(conv, (nick + u": " if nick else u"") + emojize(message, True))
    else:
        conv = purple.PurpleConvIm(receiving)
        purple.PurpleConvImSend(conv, (nick + u": " if nick else u"") + emojize(message, True))

    # I could put this behind debug, but I choose not to. It's pretty enough.
    sendTitle = purple.PurpleConversationGetTitle(sending)
    receiveTitle = purple.PurpleConversationGetTitle(receiving)
    try:  # Logging errors should not break things.
        # Removes emojis from messages, not all consoles support emoji, and not all files like emojis written to them.
        log(demojize(u"[{}] Sent \"{}\" from {} ({}) to {} ({}).".format(now().isoformat(),
            (nick + u": " + message if nick else message),
            sendTitle, sending, receiveTitle, conv)))  # Sent "message" from chat 1 (chat ID) to chat 2 (chat ID).
        logFile.flush()  # Update the log since it's been written to.
    except UnicodeError:
        pass


def messageListener(account, sender, message, conversation, flags):
    """
    The function that runs when a message is received.

    :param account: The account the message was received on.
    :type account: int
    :param sender: The name of the chat the message was sent from.
    :type sender: unicode
    :param message: The received message.
    :type message: unicode
    :param conversation: The conversation in which this message was received.
    :type conversation: int
    :param flags: Any flags for this message, such as the type of message.
    :type flags: tuple
    """
    global lastMessageTime
    if purple.PurpleAccountGetUsername(account) == sender:
        return
    elif now() - lastMessageTime < timedelta(seconds=.1):
        print(u"Overflow!", account, sender, message, conversation, flags)  # Debug stuff
        lastMessageTime = now()
        return
    lastMessageTime = now()
    # Strip HTML from Hangouts messages.
    message = purple.PurpleMarkupStripHtml(message) if message.startswith(u"<") else message

    nick = purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(account, sender))  # Name which will appear on the log.

    try:  # Logs messages. Logging errors will not prevent commands from working.
        log(u"{}: {}\n".format(nick, (u"" + str(message))))
        logFile.flush()
    except UnicodeError:
        pass
    # Run commands if the message starts with the command character.
    if message[0:len(commandDelimiter)] == commandDelimiter:
        command = message[len(commandDelimiter):message.find(u" ") if u" " in message else len(message)].lower()
        args = message.split(u" ")[1:]
        argSet = (account, sender, message, conversation, flags)
        if not runCommand(argSet, command.lower(), *args):
            simpleReply(argSet, u"Command/alias \"{}\" not found. {}".format(
                command, getCommands(argSet)))
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


bus = SessionBus()  # Initialize the DBus interface
purple = bus.get(u"im.pidgin.purple.PurpleService", u"/im/pidgin/purple/PurpleObject")  # Connect to libpurple clients.
# Surprisingly, im.pidgin.* and im/pidgin/* work for Finch too. Not sure why.

# Run the message listener for IMs and Chats.
purple.ReceivedImMsg.connect(messageListener)
purple.ReceivedChatMsg.connect(messageListener)


def periodicLoop():
    """
    Used for any tasks that may need to run in the background.

    :return: True
    :rtype: True
    """
    eventRemoved = False
    for event in scheduledEvents:
        if isinstance(event[0], (str, unicode)):  # If it's reading it from the serialized version...
            eventTime = datetime.strptime(event[0], u'%a, %d %b %Y %H:%M:%S UTC')  # Convert it back to a datetime
        else:
            eventTime = event[0]
        if timedelta() < now() - eventTime:  # If the event is due to be scheduled...
            if now() - eventTime < timedelta(minutes=5):  # Make sure the event was supposed to be run
                # less than 5 minutes before now, otherwise, don't run the function, but still discard of it.
                try:
                    messageListener(*event[1])
                except:
                    pass
            scheduledEvents.remove(event)  # Discard the event
            eventRemoved = True
    if eventRemoved:  # If any events were removed, update the file.
        updateFile(u"scheduledEvents.json", scheduledEvents)
    return True


GObject.threads_init()
GLib.threads_init()
GLib.timeout_add_seconds(1, periodicLoop)  # Run periodicLoop once per second.
GObject.MainLoop().run()  # Actually run the program.
