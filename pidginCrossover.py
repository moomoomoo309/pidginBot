#!/usr/bin/env python
# coding: UTF-8

# emoji, humanize and PyGObject are dependencies. "pip install emoji pygobject humanize --upgrade" will do that for you.
from __future__ import print_function

from sys import exit
from datetime import datetime, timedelta
from math import ceil
from random import randint
from humanize import naturaldelta

from gi.repository import GObject
from pydbus import SessionBus
from emoji import demojize, emojize  # This dependency is 👍
from emoji.unicode_codes import UNICODE_EMOJI as emojis
from json import dumps, loads

commandDelimiter = "!"  # What character(s) the commands should start with.
now = datetime.now
lastMessageTime = now()


def readFile(path):
    fileHandle = open(path, mode="r")
    out = None
    strFile = fileHandle.read(-1)
    if out is None and strFile != "":
        try:
            out = loads(strFile)  # json.loads is WAY faster than ast.literal_eval!
        except ValueError:
            pass

    fileHandle.close()  # No need to keep the file handle open unnecessarily.
    return out


readFiles = lambda *paths: [readFile(path) for path in paths]


def getChats():
    rawChats = purple.PurpleGetConversations()
    chatIDs = dict()
    for i in rawChats:
        info = (purple.PurpleConversationGetAccount(i), purple.PurpleConversationGetTitle(i))
        if info not in chatIDs or i > chatIDs[info] and (
            (purple.PurpleConversationGetType(i) == 2 and i <= 10000) or purple.PurpleConversationGetType(i) != 2):
            chatIDs[info] = i
    return chatIDs.values()


def updateFile(path, value):
    openFile = open(path, mode="w")  # To update a file
    openFile.write(dumps(value, openFile, indent=4,
        default=lambda o: o.strftime('%a, %d %b %Y %H:%M:%S UTC') if isinstance(o, datetime) else None))
    openFile.close()


# Read files for persistent values.
messageLinks, puns, aliases, atLoc = readFiles("messageLinks.json", "Puns.json", "Aliases.json", "atLoc.json")

messageLinks = messageLinks or {}
puns = puns or {}
aliases = aliases or {}
atLoc = atLoc or {}
aliasVars = [
    ("%senderName", lambda argSet: getNameFromArgs(*argSet[:2])),
    ("%botname", lambda argSet: purple.PurpleAccountGetAlias(argSet[0])),
    ("%chattitle", lambda argSet: purple.PurpleConversationGetTitle(argSet[3])),
    ("%chatname", lambda argSet: purple.PurpleConversationGetName(argSet[3]))
]
getHrs = lambda currTime: int((currTime or 0) if "h" not in currTime.lower() else currTime[:currTime.lower().find("h")])
getMins = lambda currTime: int(0 if "h" not in currTime.lower() else currTime[currTime.lower().find("h") + 1:])


def replaceAliasVars(argSet, message):
    newMsg = message  # Don't touch the original
    for i in aliasVars:
        newMsg = newMsg.replace(i[0], i[1](argSet))
    return newMsg


def getPun(argSet, punFilter):  # Gets a random pun, or a random pun that satisfies the provided filter.
    chat = getChatName(argSet[3])
    puns[chat] = puns[chat] if chat in puns else []
    if len(puns[chat]) == 0:
        return "No puns found!"
    if not punFilter:
        return puns[chat][randint(0, len(puns) - 1)]
    validPuns = list(filter(lambda pun: str(punFilter) in str(pun), puns[chat]))
    return (validPuns[randint(0, len(validPuns) - 1)]) if len(validPuns) > 0 else (
        "Does not punpute! Random Pun: " + puns[chat][randint(0, len(puns) - 1)])


def Help(argSet, page=(), *_):  # Returns help text for the given command, or a page listing all commands.
    iteratableCommands = commands.keys()  # A tuple containing all of the keys in iteratableCommands.
    commandsPerPage = 10  # How many commands to show per page.
    cmd = page[len(commandDelimiter):]
    if cmd and cmd.lower() in helpText:  # If the help text for a given command was asked for
        simpleReply(argSet, helpText[cmd.lower()])
    elif not page or (page and page.isdigit()):  # If a page number was asked for
        page = int(page) if page and page.isdigit() else 1
        helpStr = ""
        helpStr += "Help page {}/{}".format(int(min(page, ceil(1.0 * len(iteratableCommands) / commandsPerPage))),
            int(ceil(1.0 * len(iteratableCommands) / commandsPerPage)))
        for i in range(max(0, (page - 1) * commandsPerPage), min(page * commandsPerPage, len(iteratableCommands))):
            helpStr += "\n" + iteratableCommands[i] + ": " + (
                helpText[iteratableCommands[i]] if iteratableCommands[i] in helpText else "")
        simpleReply(argSet, helpStr)
    else:
        simpleReply(argSet, "No command \"{}\" found.".format(page))


def Link(argSet, chat, *chats):  # Links chats to chat. Supports partial names.
    fullChatName = getFullConvName(chat)
    fullChatNames = [getFullConvName(chat) for chat in chats]
    if fullChatName in messageLinks:
        messageLinks[fullChatName].append(fullChatNames)
    else:
        messageLinks[fullChatName] = fullChatNames
    if len(messageLinks[fullChatName]) == 1:
        messageLinks[fullChatName] = messageLinks[fullChatName][0]
    updateFile("messageLinks.json", messageLinks)
    simpleReply(argSet, u"{} linked to {}.".format(str(fullChatNames)[1:-1], fullChatName))


def Unlink(argSet, chat, *chats):  # Unlinks chats from chat. Supports partial names.
    fullChatName = getFullConvName(chat)
    removedChats = []
    if fullChatName not in messageLinks:  # If you wanted a chat that doesn't exist, just return.
        simpleReply(argSet, "No chat \"{}\" found.".format(chat))
        return
    for i in chats:  # Remove each chat
        fullName = getFullConvName(i)
        if fullName == messageLinks[fullChatName]:
            messageLinks.pop(fullChatName)  # Remove the last message link from this chat.
            simpleReply(argSet, "{} unlinked from {}.".format(fullName, fullChatName))
            return
        elif isinstance(messageLinks[fullChatName], dict) and fullName in messageLinks[fullChatName]:
            removedChats.append(messageLinks[fullChatName].pop(messageLinks[fullChatName].index(fullName)))
    updateFile("messageLinks.json", messageLinks)  # Update the messageLinks file.
    simpleReply(argSet, "{} unlinked from {}.".format(str(removedChats)[1:-1], fullChatName))


def addPun(argSet, pun):  # Adds a pun to the pun list, then updates the file.
    chat = getChatName(argSet[3])
    puns[chat] = puns[chat] if chat in puns else []
    puns[chat].append(str(pun))
    updateFile("Puns.json", puns)
    simpleReply(argSet, "\"{}\" added to the pun list.".format(pun))


def removePun(argSet, pun):  # Removes a pun from the pun list, then updates the file.
    chat = getChatName(argSet[3])
    puns[chat] = puns[chat] if chat in puns else []
    fullPun = next((fullPun for fullPun in puns if str(pun) in fullPun), None)
    if fullPun is None:
        simpleReply(argSet, "No pun found containing \"{}\".".format(pun))
        return
    puns[chat].remove(fullPun)
    simpleReply(argSet, "\"{}\" removed from the pun list.".format(fullPun))
    updateFile("Puns.json", puns)


def addAlias(argSet, *_):  # Adds an alias for a command, or replies what an alias runs.
    chat = getChatName(argSet[3])
    aliases[chat] = aliases[chat] if chat in aliases else {}
    message = argSet[2][7 + len(commandDelimiter):]
    if message == "":
        return
    command = (message[:message.find(" ")] if " " in message else message).lower()
    argsMsg = message[message.find(" ") + 1 + len(commandDelimiter):]
    args = [str(arg) for arg in argsMsg.split(" ")]
    if " " not in message:  # If the user is asking for the command run by a specific alias.
        if str(command) not in aliases[chat]:  # If the alias asked for does not exist.
            simpleReply(argSet, "No alias \"{}\" found.".format(str(command)))
            return
        simpleReply(argSet, '"' + commandDelimiter + aliases[chat][str(command)][0] + '"')
        return
    if str(command) in commands:
        simpleReply(argSet, "That name is already used by a command!")
        return
    aliases[chat][str(command)] = (argsMsg, args)
    simpleReply(argSet, "\"{}\" bound to \"{}\".".format(commandDelimiter + command, commandDelimiter + argsMsg))
    updateFile("Aliases.json", aliases)


def removeAlias(argSet, alias=(), *_):  # Removes an alias to a command.
    chat = getChatName(argSet[3])
    aliases[chat] = aliases[chat] if chat in aliases else {}
    if not alias:
        simpleReply(argSet, "Enter an alias to remove!")
        return
    if alias[len(commandDelimiter):] in aliases[chat]:
        aliases[chat].pop(alias[len(commandDelimiter):])
    else:
        simpleReply(argSet, "No alias \"{}\" found.".format(alias))
        return
    simpleReply(argSet, "\"{}\" unaliased.".format(alias))
    updateFile("Aliases.json", aliases)


getNameFromArgs = lambda account, name: purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(account, name))
getChatName = lambda chatId: purple.PurpleConversationGetTitle(chatId)


def getFullUsername(argSet, partialName):  # Returns a user's alias given their partial name.
    users = getUserFromName(argSet, partialName)
    return [getNameFromArgs(argSet[0], buddy) for buddy in
        users] if users is not None else None


def getUserFromName(argSet, partialName):  # Returns the "name" of a user given their partial name.
    buddies = [purple.PurpleConvChatCbGetName(user) for user in
        purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]
    names = [getNameFromArgs(argSet[0], buddy) for buddy in buddies]
    # Check the beginning first, otherwise, check if the partialname is somewhere in the name.
    return next((buddies[i] for i in range(len(names)) if names[i][0:len(partialName)].lower() == partialName.lower()),
        None) or next((buddies[i] for i in range(len(names)) if partialName.lower() in names[i].lower()), None)


def runCommand(argSet, command, *args):  # Runs the command given the argSet and the command it's trying to run.
    command = command or argSet[2][:argSet[2].find(" ")]
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
        newMsg = replaceAliasVars(argSet, message).replace(command, aliases[chat][command][0])
        commands[aliases[chat][command][1][0]]((argSet[0], argSet[1], newMsg, argSet[3], argSet[4]), *(
            tuple(args) + tuple(aliases[chat][command][1][len(commandDelimiter):])))  # Run the alias's command
        return True
    return False


def Mimic(argSet, user=None, firstWordOfCmd=None, *_):  # Runs a command as a different user.
    if user is None or firstWordOfCmd is None:
        simpleReply(argSet, "You need to specify the user to mimic and the command to mimic!")
        return
    fullUser = getUserFromName(argSet, user)
    if fullUser is None:
        simpleReply(argSet, "No user by the name \"{}\" found.".format(user))
    # The command, after the user argument.
    cmd = argSet[2][6 + len(commandDelimiter):][argSet[2][6 + len(commandDelimiter):].find(" ") + 1:]
    if not runCommand((argSet[0], fullUser, cmd, argSet[3], argSet[4]), cmd.split(" ")[0][len(commandDelimiter):],
            *cmd.split(" ")[len(commandDelimiter):]):
        simpleReply(argSet, "That's not a command!")


def loc(argSet, *_):  # Tells the chat you've gone somewhere
    time = argSet[2][len(commandDelimiter) + 4:argSet[2].find(" ", len(commandDelimiter) + 4)]
    location = argSet[2][argSet[2].find(" ", len(commandDelimiter) + 4) + 1:] if len(argSet[2]) > len(
        commandDelimiter) + 4 else "GDS"
    Loc(argSet, time, location)


def Loc(argSet, time="1", location="GDS"):
    chat = getChatName(argSet[3])
    atLoc[chat] = atLoc[chat] if chat in atLoc else {}
    # Update the time
    atLoc[chat][purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(*argSet[:2]))] = [now(), location, time]

    time = time if len(time) > 0 else "1"
    numHrs = getHrs(time)
    numHrs = 1 if numHrs is not 0 and not numHrs else numHrs
    numMins = getMins(time)
    numMins = 0 if numMins is not 0 and not numMins else numMins
    print(numHrs, numMins, time, location)
    simpleReply(argSet,
        "{} is going to {} for {}{}{}.".format(getNameFromArgs(*argSet[:2]),
            location,
            naturaldelta(timedelta(hours=getHrs(time))) if numHrs != 0 else "",
            " and " if numHrs != 0 and numMins != 0 else "",
            naturaldelta(timedelta(minutes=getMins(time))) if bool(int(getMins(time))) else ""))
    updateFile("atLoc.json", atLoc)


def leftLoc(argSet, *_):
    chat = getChatName(argSet[3])
    atLoc[chat] = atLoc[chat] if chat in atLoc else {}
    thisLoc = atLoc[chat][purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(*argSet[:2]))]
    thisLoc[0] = now() - timedelta(hours=2)  # Set the last visit time to now minus two hours.
    simpleReply(argSet,
        "{} left {}.".format(getNameFromArgs(*argSet[:2]), thisLoc[1]))
    updateFile("atLoc.json", atLoc)


def AtLoc(argSet, *_):
    def toDate(string):
        if type(string) == datetime:
            return string
        try:
            return datetime.strptime(string, '%a, %d %b %Y %H:%M:%S UTC')
        except:
            return now()

    location = argSet[2][len(commandDelimiter) + 6:] if " " in argSet[2] else "anywhere"
    chat = getChatName(argSet[3])
    atLoc[chat] = atLoc[chat] if chat in atLoc else {}

    # Filter out people who have been somewhere in the last hour
    lastHour = [name for name in atLoc[chat].keys() if
        now() - toDate(atLoc[chat][name][0]) < timedelta(hours=getHrs(atLoc[chat][name][2]),
            minutes=getMins(atLoc[chat][name][2])) and (atLoc[chat][name][1] == location or location == "anywhere")]
    # Write the names to a string.
    strPeopleAtLoc = u"".join([u"{} went to {} {} ago. ".format(
        n, atLoc[n][1], naturaldelta(now() - toDate(atLoc[chat][n][0]))) for n in lastHour])
    if lastHour:
        simpleReply(argSet, strPeopleAtLoc)
    else:  # If no one has been to GDS
        simpleReply(argSet,
            "No one went {} in the last hour.".format(location if location == "anywhere" else "to " + location))


dice = [u"0⃣", u"1⃣", u"2⃣", u"3⃣", u"4⃣", u"5⃣", u"6⃣", u"7⃣", u"8⃣", u"9⃣️⃣️"]  # 1-9 in emoji form


def diceRoll(argSet, diceStr="", *_):  # Returns a dice roll of the given dice.
    def diceify(s):  # Replaces numbers with emojis
        for i in range(len(dice)):
            s = s.replace(u"" + str(i), dice[i])
        return s

    numDice, numSides = 1, 6  # Defaults to 1d6
    if "d" in diceStr.lower():
        numDice, numSides = int(diceStr[:diceStr.lower().find("d")]), int(diceStr[diceStr.lower().find("d") + 1:])
    elif diceStr.isdigit():
        numDice = int(diceStr)
    rolls = [randint(1, numSides) for _ in range(numDice)]  # Roll the dice
    simpleReply(argSet,
        diceify(u"".join(str(s) + ", " for s in rolls) + u"Sum={}, Max={}, Min={}".format(sum(rolls), max(rolls),
            min(rolls))))


commands = {  # A dict containing the functions to run when a given command is entered.
    "help": Help,
    "ping": lambda argSet, *_: simpleReply(argSet, "Pong!"),
    "chats": lambda argSet, *_: simpleReply(argSet,
        str([u"{} ({})".format(purple.PurpleConversationGetTitle(conv), conv) for conv in getChats()])[1:-1].replace(
            "u'", "'")),
    "args": lambda argSet, *_: simpleReply(argSet, str(argSet)),
    "echo": lambda argSet, *_: simpleReply(argSet, argSet[2][argSet[2].find("echo") + 4 + len(commandDelimiter):]),
    "exit": lambda *_: exit(37),
    "msg": lambda argSet, msg="", *_: sendMessage(argSet[-2], getConvFromPartialName(msg), [],
        getNameFromArgs(*argSet[:2]) + ": " + argSet[2][
        argSet[2][4 + len(commandDelimiter):].find(" ") + 5 + len(commandDelimiter):]),
    "link": lambda argSet, *args: Link(argSet, *args),
    "unlink": lambda argSet, *args: Unlink(argSet, *args),
    "links": lambda argSet, *_: simpleReply(argSet, str(messageLinks)),
    "pun": lambda argSet, pun=(), *_: simpleReply(argSet, getPun(argSet, pun)),
    "addpun": lambda argSet, *_: addPun(argSet, argSet[2][7 + len(commandDelimiter):]),
    "removepun": lambda argSet, pun, *_: removePun(argSet, pun),
    "alias": addAlias,
    "unalias": removeAlias,
    "aliases": lambda argSet, *_: simpleReply(argSet,
        "Valid aliases: {}".format(str(aliases[getChatName(argSet[3])].keys())[1:-1]).replace("u'", "'")),
    "me": lambda argSet, *_: simpleReply(argSet, "*{} {}.".format(
        purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(*argSet[:2])), argSet[2][3 + len(commandDelimiter):])),
    "botme": lambda argSet, *_: simpleReply(argSet, "*{} {}.".format(purple.PurpleAccountGetAlias(argSet[0]),
        argSet[2][6 + len(commandDelimiter):])),
    "randomemoji": lambda argSet, amt=1, *_: simpleReply(argSet, u"".join(
        [emojis.values()[randint(0, len(emojis) - 1)] for _ in range(int(amt) or 1)])),
    "mimic": Mimic,
    "users": lambda argSet, *_: simpleReply(argSet, emojize(str(
        [purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(argSet[0], purple.PurpleConvChatCbGetName(user))) for user in
            purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]), use_aliases=True)),
    "loc": loc,
    "gds": lambda argSet, *_: Loc(argSet, time=argSet[2][len(commandDelimiter) + 4:]),
    "loconly": lambda argSet, *_: Loc(argSet, location=argSet[2][len(commandDelimiter) + 7:]),
    "atloc": AtLoc,
    "leftloc": leftLoc,
    "diceroll": diceRoll,
    "restart": lambda *_: exit(0)
}

helpText = {  # The help text for each command.
    "help": "Prints out the syntax and usage of each command.",
    "ping": "Replies \"Pong!\". Useful for checking if the bot is working.",
    "chats": "Lists all chats the bot knows of by name and ID.",
    "args": "Prints out the arguments received from this message.",
    "echo": "Repeats the message said.",
    "exit": "Exits the bot.",
    "msg": "Sends a message to the specified chat. Matches incomplete names.",
    "link": "Links from the first chat to the following chats.",
    "unlink": "Unlinks the second and further chats from the first chat.",
    "links": "Prints out the current message links.",
    "pun": "Replies with a random pun.",
    "addpun": "Adds a pun to the list of random puns.",
    "alias": "Links a name to a command, or prints out the command run by an alias.",
    "unalias": "Unlinks a name from a command.",
    "aliases": "Lists all of the aliases.",
    "removepun": "Removes a pun from the list of puns.",
    "me": "Replies \"*(username) (message)\", e.g. \"*Gian Laput is French.\"",
    "botme": "Replies \"*(bot's name) (message)\", e.g. \"*NickBot DeLello died.\"",
    "randomemoji": "Replies with the specified number of random emojis.",
    "mimic": "Runs the specified command as if it was run by the specified user.",
    "users": "Lists all of the users in the current chat.",
    "loc": "Tells the chat you've gone somewhere.",
    "gds": "Tells the chat you're going to GDS for some period of time.",
    "loconly": "Tells the chat you're going somewhere for an hour.",
    "atloc": "Replies with who's said they're somewhere within the last hour and where they are.",
    "leftloc": "Tells the chat you've left somewhere.",
    "diceroll": "Rolls the specified number of dice, returning the min, max, and sum of the rolls. 1d6 by default.",
    "restart": "Restarts the bot."
}


def getFullConvName(partialName):  # Returns a full conversation title given a partial title.
    conversations = [purple.PurpleConversationGetTitle(conv) for conv in getChats()]
    # Check the beginning first, if none start with the partial name, find it in there somewhere.
    return next((i for i in conversations if i[0:len(partialName)] == partialName), None) or next(
        (i for i in conversations if partialName in i), None)


# Returns the conversation ID of a conversation given its partial name.
getConvFromPartialName = lambda partialName: getConvByName(getFullConvName(partialName))

simpleReply = lambda argSet, message: sendMessage(argSet[-2], argSet[-2], [], message)  # Replies to a chat

lastMessage = ""  # The last message, to prevent infinite looping.

# Gets the ID of a conversation, given its name. Does not work if a message has not been received from that chat yet.
getConvByName = lambda name: next(
    (i for i in getChats() if purple.PurpleConversationGetTitle(i) == name), None)

logFile = open("Pidgin_Crossover_Messages.log", mode="a")
# Writes a string to the log file.
logStr = lambda string: logFile.write(str(u"[{}] {}\n".format(now().isoformat(), demojize(string))))

log = lambda string: [fct(string + "\n") for fct in (print, logStr)]  # Prints and writes to the log file.


def sendMessage(sending, receiving, nick, message):  # Sends a message on the given chat.
    if receiving is None:  # If the conversation can't be found by libpurple, it'll just error anyway.
        return

    if message[0:len(commandDelimiter)] == commandDelimiter:  # Do not send out commands! No! Bad!
        message = ("_" if commandDelimiter[0] != "_" else "__") + message

    # Actually send the messages out.
    if purple.PurpleConversationGetType(receiving) == 2:  # 2 means a group chat.
        conv = purple.PurpleConvChat(receiving)
        purple.PurpleConvChatSend(conv, (nick + ": " if nick else "") + emojize(message, True))
    else:
        conv = purple.PurpleConvIm(receiving)
        purple.PurpleConvImSend(conv, (nick + ": " if nick else "") + emojize(message, True))

    # I could put this behind debug, but I choose not to. It's pretty enough.
    sendTitle = purple.PurpleConversationGetTitle(sending)
    receiveTitle = purple.PurpleConversationGetTitle(receiving)
    try:  # Logging errors should not break things.
        log(demojize(u"[{}] Sent \"{}\" from {} ({}) to {} ({}).".format(now().isoformat(),
            (nick + ": " + message if nick else message),
            sendTitle, sending, receiveTitle, conv)))  # Sent "message" from chat 1 (chat ID) to chat 2 (chat ID).
        # Removes emojis from messages, not all consoles support emoji, and not all files like emojis written to them.

        logFile.flush()  # Update the log since it's been written to.
    except UnicodeError:
        pass


# Returns what it says on the tin.
isListButNotString = lambda obj: isinstance(obj, (list, tuple, set)) and not isinstance(obj, (str, unicode))


def messageListener(account, sender, message, conversation, flags):
    global lastMessageTime
    if purple.PurpleAccountGetUsername(account) == sender:
        return
    elif now() - lastMessageTime < timedelta(seconds=.1):
        print("Overflow!", account, sender, message, conversation, flags)  # Debug stuff
        lastMessageTime = now()
        return
    lastMessageTime = now()
    # Strip HTML from Hangouts messages.
    message = purple.PurpleMarkupStripHtml(message) if message.startswith("<") else message

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
        if not runCommand(argSet, command, *args):
            simpleReply(argSet, "Command/alias \"{}\" not found. Valid commands: {} Valid aliases: {}".format(
                command, str(sorted(commands.keys()))[1:-1],
                str(sorted(aliases[getChatName(argSet[3])].keys()))[1:-1].replace("u'", "'")))
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
purple = bus.get("im.pidgin.purple.PurpleService", "/im/pidgin/purple/PurpleObject")  # Connect to libpurple clients.
# Surprisingly, im.pidgin.* and im/pidgin/* work for Finch too. Not sure why.

# Run the message listener for IMs and Chats.
purple.ReceivedImMsg.connect(messageListener)
purple.ReceivedChatMsg.connect(messageListener)

purple.PurpleConversationsInit()

GObject.MainLoop().run()
