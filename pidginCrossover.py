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
    # type: (unicode) -> dict
    """Reads, then parses the file at the given path as json."""
    with open(path, mode="r") as fileHandle:  # With is nice and clean.
        out = None
        strFile = fileHandle.read(-1)
        if out is None and strFile != "":
            try:
                out = loads(strFile)  # json.loads is WAY faster than ast.literal_eval!
            except ValueError:
                pass
    return out


readFiles = lambda *paths: [readFile(path) for path in paths]  #


def getChats():
    # type: () -> list
    """Returns all valid chat ids, filtering out any duplicate or invalid chats."""
    rawChats = purple.PurpleGetConversations()
    chatIDs = dict()
    for i in rawChats:
        info = (purple.PurpleConversationGetAccount(i), purple.PurpleConversationGetTitle(i))
        if info not in chatIDs or i > chatIDs[info] and (
                    (purple.PurpleConversationGetType(i) == 2 and i <= 10000) or
                        purple.PurpleConversationGetType(i) != 2):
            chatIDs[info] = i
    return chatIDs.values()


def updateFile(path, value):
    # type: (unicode, unicode) -> None
    """Replaces the contents of the file at the given path with the given value."""
    with open(path, mode="w") as openFile:  # To update a file
        openFile.write(dumps(value, openFile, indent=4,
            default=lambda o: o.strftime('%a, %d %b %Y %H:%M:%S UTC') if isinstance(o, datetime) else None))
        # The default function allows it to dump datetime objects.


naturalTime = lambda time: naturaltime(time + timedelta(seconds=1))  # Fixes rounding errors.
naturalDelta = lambda time: naturaldelta(time - timedelta(seconds=1))  # Fixes rounding errors.

getNameFromArgs = lambda account, name: purple.PurpleBuddyGetAlias(
    purple.PurpleFindBuddy(account, name))  # Gets a user's actual name given the account and name.
getChatName = lambda chatId: purple.PurpleConversationGetTitle(chatId)  # Gets the name of a chat given the chat's ID.


def getTime(currTime):
    # type: (unicode) -> datetime
    """Given a natural time string, such as "in 30 minutes", returns that time as a datetime object."""
    return parser.parseDT(currTime)[0]


getCommands = lambda argSet: u"Valid Commands: {}, Valid Aliases: {}".format(str(sorted(commands.keys()))[1:-1],
    str(sorted(aliases[getChatName(argSet[3])].keys()))[1:-1].replace("u'",
        u"'"))  # Returns a list of all of the commands.


def getFullConvName(partialName):
    # type: (unicode) -> unicode
    """Returns a full conversation title given a partial title."""
    conversations = [purple.PurpleConversationGetTitle(conv) for conv in getChats()]
    # Check the beginning first, if none start with the partial name, find it in there somewhere.
    return next((i for i in conversations if i[0:len(partialName)] == partialName), None) or next(
        (i for i in conversations if partialName in i), None)


# Returns the conversation ID of a conversation given its partial name.
getConvFromPartialName = lambda partialName: getConvByName(getFullConvName(partialName))

simpleReply = lambda argSet, message: sendMessage(argSet[-2], argSet[-2], u"", message)  # Replies to a chat

# Gets the ID of a conversation, given its name. Does not work if a message has not been received from that chat yet.
getConvByName = lambda name: next(
    (i for i in getChats() if purple.PurpleConversationGetTitle(i) == name), None)

logFile = open("Pidgin_Crossover_Messages.log", mode="a")
# Writes a string to the log file.
logStr = lambda string: logFile.write(str(u"[{}] {}\n".format(now().isoformat(), demojize(string))))
log = lambda string: [fct(string + "\n") for fct in (print, logStr)]  # Prints and writes to the log file.

# Returns what it says on the tin.
isListButNotString = lambda obj: isinstance(obj, (list, tuple, set)) and not isinstance(obj, (str, unicode))
# ---------------------------------------

# Read files for persistent values.
messageLinks, puns, aliases, atLoc, scheduledEvents = readFiles("messageLinks.json", "Puns.json", "Aliases.json",
    "atLoc.json", "scheduledEvents.json")

commandDelimiter = "!"  # What character(s) the commands should start with.
lastMessage = ""  # The last message, to prevent infinite looping.
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
    # type: (tuple, unicode) -> unicode
    """Given the original message, replaces any alias vars (see above) with their proper values."""
    newMsg = message  # Don't touch the original
    for i in aliasVars:
        newMsg = newMsg.replace(i[0], i[1](argSet))
    return newMsg


def getPun(argSet, punFilter):
    # type: (tuple, unicode) -> unicode
    """Gets a random pun, or a random pun that satisfies the provided filter."""
    chat = getChatName(argSet[3])
    puns[chat] = puns[chat] if chat in puns else []
    if len(puns[chat]) == 0:
        return u"No puns found!"
    if not punFilter:
        return puns[chat][randint(0, len(puns[chat]) - 1)]
    validPuns = list(filter(lambda pun: str(punFilter) in str(pun), puns[chat]))
    return (validPuns[randint(0, len(validPuns) - 1)]) if len(validPuns) > 0 else (
        u"Does not punpute! Random Pun: " + puns[chat][randint(0, len(puns) - 1)])


def Help(argSet, page="", *_):
    # type: (tuple, unicode)->None
    """Returns help text for the given command, or a page listing all commands."""
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
    # type: (tuple, unicode, tuple)->None
    """Links chats to chat. Supports partial names."""
    fullChatName = getFullConvName(chat)
    fullChatNames = [getFullConvName(chat) for chat in chats]
    if fullChatName in messageLinks:
        messageLinks[fullChatName].append(*fullChatNames)
    else:
        messageLinks[fullChatName] = fullChatNames
    if len(messageLinks[fullChatName]) == 1:
        messageLinks[fullChatName] = messageLinks[fullChatName][0]
    updateFile(u"messageLinks.json", messageLinks)
    simpleReply(argSet, u"{} linked to {}.".format(str(fullChatNames)[1:-1], fullChatName))


def Unlink(argSet, chat, *chats):
    # type: (tuple, unicode, tuple)->None
    """Unlinks chats from chat. Supports partial names."""
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
    simpleReply(argSet, u"{} unlinked from {}.".format(str(removedChats)[1:-1], fullChatName))


def addPun(argSet, pun):
    # type: (tuple, unicode)->None
    """Adds a pun to the pun list, then updates the file."""
    chat = getChatName(argSet[3])
    puns[chat] = puns[chat] if chat in puns else []
    puns[chat].append(str(pun))
    updateFile(u"Puns.json", puns)
    simpleReply(argSet, u"\"{}\" added to the pun list.".format(pun))


def removePun(argSet, pun):
    # type: (tuple, unicode)->None
    """Removes a pun from the pun list, then updates the file."""
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
    # type: (tuple)->None
    """Adds an alias for a command, or replies what an alias runs."""
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
        " " in argsMsg and argsMsg.find(" ") or len(argsMsg))]
    if cmd not in commands:
        simpleReply(argSet, u"{}{} is not a command!".format(commandDelimiter, cmd))
        return
    aliases[chat][str(command)] = (argsMsg, args)
    simpleReply(argSet, u"\"{}\" bound to \"{}\".".format(commandDelimiter + command, commandDelimiter + argsMsg))
    updateFile(u"Aliases.json", aliases)


def removeAlias(argSet, alias=(), *_):
    # type: (tuple, tuple)->None
    """Removes an alias to a command."""
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
    # type: (tuple, unicode) -> unicode
    """Returns a user's alias given their partial name."""
    buddies = [purple.PurpleConvChatCbGetName(user) for user in
        purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]
    names = [getNameFromArgs(argSet[0], buddy) for buddy in buddies]
    # Check the beginning first, otherwise, check if the partialname is somewhere in the name.
    name = (next((names[i] for i in range(len(names)) if names[i][0:len(partialName)].lower() == partialName.lower()),
        None) or next((names[i] for i in range(len(names)) if partialName.lower() in names[i].lower()), None))
    return u"" + name if name is not None else None


def getUserFromName(argSet, partialName):
    # type: (tuple, unicode) -> unicode
    """Returns the "name" of a user given their partial name."""
    buddies = [purple.PurpleConvChatCbGetName(user) for user in
        purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]
    names = [getNameFromArgs(argSet[0], buddy) for buddy in buddies]
    # Check the beginning first, otherwise, check if the partialname is somewhere in the name.
    name = (next((buddies[i] for i in range(len(names)) if names[i][0:len(partialName)].lower() == partialName.lower()),
        None) or next((buddies[i] for i in range(len(names)) if partialName.lower() in names[i].lower()), None))
    return u"" + name if name is not None else None


def runCommand(argSet, command, *args):
    # type: (tuple, unicode, tuple) -> bool
    """Runs the command given the argSet and the command it's trying to run."""
    command = (command or argSet[2][:argSet[2].find(" ")]).lower()
    chat = getChatName(argSet[3])
    aliases[chat] = aliases[chat] if chat in aliases else {}
    if command in commands:
        commands[command](argSet, *args)
        return True
    elif command in aliases[chat]:
        message = argSet[2]
        command = message[len(commandDelimiter):message.find(" ") if " " in message else len(message)].lower()
        message = message[:message.lower().find(command)] + command + message[
        message.lower().find(command) + len(command):]
        newMsg = replaceAliasVars(argSet, (message + (
            u" ".join(tuple(args)) if len(
                tuple(aliases[chat][command][1][len(commandDelimiter):])) > 0 else u"")).replace(
            command,
            aliases[chat][command][0]))
        commands[aliases[chat][command][1][0]]((argSet[0], argSet[1], newMsg, argSet[3], argSet[4]), *(
            (tuple(args) if len(
                tuple(aliases[chat][command][1][len(commandDelimiter):])) > 0 else ())))  # Run the alias's command
        return True
    return False


def Mimic(argSet, user=None, firstWordOfCmd=None, *_):
    # type: (tuple, unicode, unicode, tuple) -> None
    """Runs a command as a different user."""
    if user is None or firstWordOfCmd is None:
        simpleReply(argSet, u"You need to specify the user to mimic and the command to mimic!")
        return
    fullUser = getUserFromName(argSet, user)
    if fullUser is None:
        simpleReply(argSet, u"No user by the name \"{}\" found.".format(user))
    # The command, after the user argument.
    cmd = argSet[2][6 + len(commandDelimiter):][argSet[2][6 + len(commandDelimiter):].find(" ") + 1:].lower()
    if not runCommand((argSet[0], fullUser, cmd, argSet[3], argSet[4]), cmd.split(" ")[0][len(commandDelimiter):],
            *cmd.split(" ")[len(commandDelimiter):]):
        simpleReply(argSet, u"That's not a command!")


def loc(argSet, *_):
    # type: (tuple, tuple) -> None
    """Tells the chat you've gone somewhere."""
    time = argSet[2][len(commandDelimiter) + 4:argSet[2].find(" ", len(commandDelimiter) + 4)]
    location = argSet[2][argSet[2].find(" ", len(commandDelimiter) + 4) + 1:] if len(argSet[2]) > len(
        commandDelimiter) + 4 else u"GDS"
    Loc(argSet, time, location)


def Loc(argSet, time=u"30 minutes", location=u"GDS"):
    # type: (tuple, unicode, unicode) -> None
    """Tells the chat you've gone somewhere. Has default values for ease of implementation."""
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
            (" " + appendMsg if len(appendMsg) > 0 else ""),
            naturalDelta(now() - dateTime) if dateTime is not None else ""
        )
    )
    updateFile(u"atLoc.json", atLoc)


def leftLoc(argSet, *_):
    # type: (tuple, tuple) -> None
    """Tells the chat you've left wherever you are."""
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
    # type: (tuple, tuple) -> None
    """Replies with who is at the given location, or where everyone is if the location is not specified."""

    def toDate(string):
        if type(string) == datetime:
            return string
        try:
            return datetime.strptime(string, u'%a, %d %b %Y %H:%M:%S UTC')
        except:
            return now()

    def toDelta(string):
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
    # type: (tuple, tuple) -> None
    """Schedules the given command to run at the given time."""
    msg = argSet[2][len(commandDelimiter) + 9:]
    if commandDelimiter in msg:
        timeStr = msg[:msg.find(commandDelimiter) - 1]
        cmdStr = msg[msg.find(commandDelimiter):]
    else:
        simpleReply(argSet, u"You need a command to run, with the command delimiter (" + commandDelimiter + u").")
        return
    newArgset = list(argSet)
    newArgset[2] = cmdStr
    scheduledEvents.append((getTime(timeStr), newArgset))
    updateFile(u"scheduledEvents.json", scheduledEvents)
    simpleReply(argSet, u"\"{}\" scheduled to run at {}.".format(cmdStr, naturalTime(getTime(timeStr))))


dice = [u"0⃣", u"1⃣", u"2⃣", u"3⃣", u"4⃣", u"5⃣", u"6⃣", u"7⃣", u"8⃣", u"9⃣️⃣️"]  # 1-9 in emoji form


def numToEmoji(s):
    # type: (unicode) -> unicode
    """Replaces numbers with emojis."""
    for i in range(len(dice)):
        s = s.replace(u"" + str(i), dice[i])  # Force unicode strings for Python 2 and Python 3.
    return s


def diceRoll(argSet, diceStr="", *_):
    # type: (tuple, unicode, tuple) -> None
    """Returns a dice roll of the given dice."""
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
    # type: (tuple, tuple) -> None
    """Provides %target as an alias variable, then replies with the parsed string."""
    if len(args) == 0:
        simpleReply(argSet, u"You need to provide some arguments!")
        return
    user = args[-1]
    name = getFullUsername(argSet, user)
    if name is not None:
        simpleReply(argSet,
            replaceAliasVars(argSet, argSet[2][len(commandDelimiter) + 3:argSet[2].rfind(" ")]).replace(u"%target",
                name))
    else:
        simpleReply(argSet, u"No user containing {} found.".format(user))


commands = {  # A dict containing the functions to run when a given command is entered.
    u"help": Help,
    u"ping": lambda argSet, *_: simpleReply(argSet, u"Pong!"),
    u"chats": lambda argSet, *_: simpleReply(argSet,
        str([u"{} ({})".format(purple.PurpleConversationGetTitle(conv), conv) for conv in getChats()])[1:-1].replace(
            "u'", "'")),
    u"args": lambda argSet, *_: simpleReply(argSet, str(argSet)),
    u"echo": lambda argSet, *_: simpleReply(argSet,
        argSet[2][argSet[2].lower().find(u"echo") + 4 + len(commandDelimiter):]),
    u"exit": lambda *_: exit(37),
    u"msg": lambda argSet, msg="", *_: sendMessage(argSet[-2], getConvFromPartialName(msg), u"",
        getNameFromArgs(*argSet[:2]) + ": " + argSet[2][
        argSet[2][4 + len(commandDelimiter):].find(" ") + 5 + len(commandDelimiter):]),
    u"link": lambda argSet, *args: Link(argSet, *args),
    u"unlink": lambda argSet, *args: Unlink(argSet, *args),
    u"links": lambda argSet, *_: simpleReply(argSet, str(messageLinks)),
    u"pun": lambda argSet, pun=(), *_: simpleReply(argSet, getPun(argSet, pun)),
    u"addpun": lambda argSet, *_: addPun(argSet, argSet[2][7 + len(commandDelimiter):]),
    u"removepun": lambda argSet, pun, *_: removePun(argSet, pun),
    u"alias": addAlias,
    u"unalias": removeAlias,
    u"aliases": lambda argSet, *_: simpleReply(argSet,
        "Valid aliases: {}".format(str(aliases[getChatName(argSet[3])].keys())[1:-1]).replace("u'", "'")),
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
    u"schedule": scheduleEvent
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
    u"schedule": u"Runs a command after the specified amount of time."
}


def sendMessage(sending, receiving, nick, message):
    # type: (int, int, unicode, unicode) -> None
    """Sends a message on the given chat."""
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
    # type: (int, int, unicode, int, tuple) -> None
    """The function that runs when a message is received."""
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

    nick = purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(account, sender))
    # Logs messages. Logging errors will not prevent commands from working.
    try:
        logStr(u"{}: {}\n".format(nick, (u"" + str(message))))
        logFile.flush()
    except UnicodeError:
        pass
    # Run commands if the message starts with the command character.
    if message[0:len(commandDelimiter)] == commandDelimiter:
        command = message[len(commandDelimiter):message.find(" ") if " " in message else len(message)].lower()
        args = message.split(" ")[1:]
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
    lastMessage = nick + ": " + message  # Remember the last message to prevent infinite looping.


bus = SessionBus()  # Initialize the DBus interface
purple = bus.get(u"im.pidgin.purple.PurpleService", u"/im/pidgin/purple/PurpleObject")  # Connect to libpurple clients.
# Surprisingly, im.pidgin.* and im/pidgin/* work for Finch too. Not sure why.

# Run the message listener for IMs and Chats.
purple.ReceivedImMsg.connect(messageListener)
purple.ReceivedChatMsg.connect(messageListener)

purple.PurpleConversationsInit()


def periodicLoop():
    # type: ()->True
    """Used for any tasks that may need to run in the background."""
    eventRemoved = False
    for event in scheduledEvents:
        eventTime = None
        if isinstance(event[0], (str, unicode)):
            eventTime = datetime.strptime(event[0], u'%a, %d %b %Y %H:%M:%S UTC')
        else:
            eventTime = event[0]
        if timedelta() < now() - eventTime:
            if now() - eventTime < timedelta(minutes=5):
                try:
                    messageListener(*event[1])
                except:
                    pass
            scheduledEvents.remove(event)
            eventRemoved = True
    if eventRemoved:
        updateFile(u"scheduledEvents.json", scheduledEvents)
    return True


GObject.threads_init()
GLib.threads_init()
GLib.timeout_add_seconds(1, periodicLoop)
GObject.MainLoop().run()
