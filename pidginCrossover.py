#!/usr/bin/env python
# coding: UTF-8

# emoji and PyGObject are dependencies. "pip install emoji PyGObject --upgrade" will do that for you.
from __future__ import print_function

import sys
from datetime import datetime, timedelta
from math import ceil
from ast import literal_eval
from random import randint

from gi.repository import GObject
from pydbus import SessionBus
from emoji import demojize, emojize  # This dependency is 👍
from emoji.unicode_codes import UNICODE_EMOJI as emojis

commandDelimiter = "!"  # What character(s) the commands should start with.
lastMessageTime = datetime.now()


def readFile(path):
    fileHandle = open(path, mode="r")
    try:  # Try to read the messageLinks from a text file, if it does not succeed, set it to an empty dict.
        out = literal_eval(fileHandle.read(-1))  # Read the whole file and evaluate it literally.
    except SyntaxError:
        out = None  # Otherwise, assume no links exist.
    fileHandle.close()  # No need to keep the file handle open unnecessarily.
    return out


def readFiles(*paths):
    out = []
    for path in paths:
        out.append(readFile(path))
    return out


def updateFile(path, value):
    file = open(path, mode="w")  # To update a file
    file.write(str(unicode(value, errors="replace")))
    file.close()


# Read files for persistent values.
messageLinks, puns, aliases = readFiles("messageLinks.txt", "Puns.txt", "Aliases.txt")

messageLinks = messageLinks or {}
puns = puns or []
aliases = aliases or {}


def getPun(punFilter):  # Gets a random pun, or a random pun that satisfies the provided filter.
    if punFilter is None:
        return puns[randint(0, len(puns) - 1)]
    validPuns = list(filter(lambda pun: str(punFilter) in str(pun), puns))
    return (validPuns[randint(0, len(validPuns) - 1)]) if len(validPuns) > 0 else (
        "Does not punpute! Random Pun: " + puns[randint(0, len(puns) - 1)])


def Help(argSet, *args):  # Returns help text for the given command, or a page listing all commands.
    iteratableCommands = commands.keys()  # A tuple containing all of the keys in iteratableCommands.
    commandsPerPage = 10  # How many commands to show per page.
    if len(args) > 0 and args[0].lower() in helpText:  # If the help text for a given command was asked for
        simpleReply(argSet, helpText[args[0].lower()])
    elif len(args) == 0 or args[0].isdigit():  # If a page number was asked for
        page = int(args[0]) if len(args) > 0 else 1
        helpStr = ""
        helpStr += "Help page {}/{}".format(int(min(page, ceil(1.0 * len(iteratableCommands) / commandsPerPage))),
            int(ceil(1.0 * len(iteratableCommands) / commandsPerPage)))
        for i in range(max(0, (page - 1) * commandsPerPage), min(page * commandsPerPage, len(iteratableCommands))):
            helpStr += "\n" + iteratableCommands[i] + ": " + (
                helpText[iteratableCommands[i]] if iteratableCommands[i] in helpText else "")
        simpleReply(argSet, helpStr)


def Link(argSet, chat, *chats):  # Links chats to chat. Supports partial names.
    fullChatName = getFullConvName(chat)
    fullChatNames = [getFullConvName(chat) for chat in chats]
    if fullChatName in messageLinks:
        messageLinks[fullChatName].append(fullChatNames)
    else:
        messageLinks[fullChatName] = fullChatNames
    if len(messageLinks[fullChatName]) == 1:
        messageLinks[fullChatName] = messageLinks[fullChatName][0]
    updateFile("messageLinks.txt", str(messageLinks))
    simpleReply(argSet, "{} linked to {}.".format(str(fullChatNames)[1:-1], fullChatName))


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
    updateFile("messageLinks.txt", str(messageLinks))  # Update the messageLinks file.
    simpleReply(argSet, "{} unlinked from {}.".format(str(removedChats)[1:-1], fullChatName))


def addPun(argSet, pun):  # Adds a pun to the pun list, then updates the file.
    puns.append(str(pun))
    updateFile("Puns.txt", str(puns))
    simpleReply(argSet, "\"{}\" added to the pun list.".format(pun))


def removePun(argSet, pun):  # Removes a pun from the pun list, then updates the file.
    fullPun = next((fullPun for fullPun in puns if str(pun) in fullPun), None)
    puns.remove(fullPun)
    simpleReply(argSet, "\"{}\" removed from the pun list.".format(fullPun))
    updateFile("Puns.txt", str(puns))


def addAlias(argSet, *args):  # Adds an alias for a command, or replies what an alias runs.
    message = argSet[2][8:]
    if message == "":
        return
    command = message[:message.find(" ") or -0]
    argsMsg = message[message.find(" ") + len(commandDelimiter):]
    args = [str(arg) for arg in argsMsg.split(" ")]
    if argsMsg.count(" ") == 0:
        if str(argsMsg) not in aliases:
            simpleReply(argSet, "No command \"{}\" found.".format(str(argsMsg)))
            return
        simpleReply(argSet, "!" + aliases[str(argsMsg)][0])
        return
    if str(command) in aliases:
        simpleReply(argSet, "You cannot add an alias to an existing command!")
        return
    aliases[str(command)] = (argsMsg, args)
    simpleReply(argSet, "!{} bound to !{}.".format(command, argsMsg))
    updateFile("Aliases.txt", str(aliases))


def removeAlias(argSet, *args):  # Removes an alias to a command.
    if args[0][len(commandDelimiter):] in aliases:
        aliases.pop(args[0][len(commandDelimiter):])
    else:
        simpleReply(argSet, "No alias \"{}\" found.".format(args[0]))
        return
    simpleReply(argSet, "\"{}\" unaliased.".format(args[0]))
    updateFile("Aliases.txt", str(aliases))


def getFullUsername(argSet, partialName):  # Returns a user's alias given their partial name.
    users = getUserFromName(argSet, partialName)
    return [purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(argSet[0], buddy)) for buddy in
        users] if users is not None else None


def getUserFromName(argSet, partialName):  # Returns the "name" of a user given their partial name.
    buddies = [purple.PurpleConvChatCbGetName(user) for user in
        purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]
    names = [purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(argSet[0], buddy)) for buddy in buddies]
    # Check the beginning first, otherwise, check if the partialname is somewhere in the name.
    return next((buddies[i] for i in range(len(names)) if names[i][0:len(partialName)].lower() == partialName.lower()),
        None) or next((buddies[i] for i in range(len(names)) if partialName.lower() in names[i].lower()), None)


def runCommand(argSet, command, *args): # Runs the command given the argSet and the command it's trying to run.
    command = command or argSet[2][:argSet[2].find(" ")]
    if command in commands:
        commands[command](argSet, *args)
        return True
    elif command in aliases:
        message = argSet[2]
        command = message[len(commandDelimiter):message.find(" ") or len(message)].lower()
        message = message[:message.lower().find(command)] + command + message[
        message.lower().find(command) + len(command):]
        newMsg = message.replace(command, aliases[command][0]).replace("%sendername",
            purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(*argSet[:2]))).replace("%botname",
            purple.PurpleAccountGetAlias(argSet[0])).replace("%chattitle",
            purple.PurpleConversationGetTitle(argSet[3])).replace("%chatname",
            purple.PurpleConversationGetName(argSet[3]))  # Adds a few variables you can put into aliases
        commands[aliases[command][1][0]]((argSet[0], argSet[1], newMsg, argSet[3], argSet[4]),
            *(tuple(args) + tuple(aliases[command][1][len(commandDelimiter):])))  # Run the alias's command
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


commands = {  # A dict containing the functions to run when a given command is entered.
    "help": Help,
    "ping": lambda argSet, *args: simpleReply(argSet, "Pong!"),
    "chats": lambda argSet, *args: simpleReply(argSet,
        str([str(purple.PurpleConversationGetTitle(conv)) + " (" + str(conv) + ")" for conv in
            purple.PurpleGetConversations()])[1:-1]),
    "args": lambda argSet, *args: simpleReply(argSet, str(argSet)),
    "echo": lambda argSet, *args: simpleReply(argSet, argSet[2][argSet[2].find("echo") + 4 + len(commandDelimiter):]),
    "exit": lambda *args: sys.exit(0),
    "msg": lambda argSet, *args: sendMessage(argSet[-2], getConvFromPartialName(args[0]), None,
        purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(*argSet[:2])) + ": " + argSet[2][
        argSet[2][4 + len(commandDelimiter):].find(" ") + 5 + len(commandDelimiter):]),
    "link": lambda argSet, *args: Link(argSet, *args),
    "unlink": lambda argSet, *args: Unlink(argSet, *args),
    "links": lambda argSet, *args: simpleReply(argSet, str(messageLinks)),
    "pun": lambda argSet, *args: simpleReply(argSet, getPun(args[0] if len(args) > 0 else None)),
    "addpun": lambda argSet, *args: addPun(argSet, argSet[2][7 + len(commandDelimiter):]),
    "removepun": lambda argSet, *args: removePun(argSet, args[0]),
    "alias": addAlias,
    "unalias": removeAlias,
    "aliases": lambda argSet, *args: simpleReply(argSet, "Valid aliases: {}".format(str(aliases.keys())[1:-1])),
    "me": lambda argSet, *args: simpleReply(argSet,
        "*{} {}.".format(purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(*argSet[:2])),
            argSet[2][3 + len(commandDelimiter):])),
    "botme": lambda argSet, *args: simpleReply(argSet,
        "*{} {}.".format(purple.PurpleAccountGetAlias(argSet[0]), argSet[2][6 + len(commandDelimiter):])),
    "randomemoji": lambda argSet, amt=1, *args: simpleReply(argSet,
        u"".join([emojis.values()[randint(0, len(emojis) - 1)] for i in range(int(amt) or 1)])),
    "mimic": Mimic,
    "users": lambda argSet, *args: simpleReply(argSet, str(
        [purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(argSet[0], purple.PurpleConvChatCbGetName(user))) for user in
            purple.PurpleConvChatGetUsers(purple.PurpleConvChat(argSet[3]))][:-1]))
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
    "me": "Replies \"*(username) (message)\", e.g. \"*Slim Gsus died.\"",
    "botme": "Replies \"*(bot's name) (message)\", e.g. \"*NickBot died.\"",
    "randomemoji": "Replies with the specified number of random emojis.",
    "mimic": "Runs the specified command as if it was run by the specified user.",
    "users": "Lists all of the users in the current chat."
}


def getFullConvName(partialName):  # Returns a full conversation title given a partial title.
    conversations = [purple.PurpleConversationGetTitle(conv) for conv in purple.PurpleGetConversations()]
    # Check the beginning first, if none start with the partial name, find it in there somewhere.
    return next((i for i in conversations if i[0:len(partialName)] == partialName), None) or next(
        (i for i in conversations if partialName in i), None)


# Returns the conversation ID of a conversation given its partial name.
getConvFromPartialName = lambda partialName: getConvByName(getFullConvName(partialName))

simpleReply = lambda argSet, message: sendMessage(argSet[-2], argSet[-2], None, message)  # Replies to a chat

lastMessage = None  # The last message, to prevent infinite looping.

# Gets the ID of a conversation, given its name. Does not work if a message has not been received from that chat yet.
getConvByName = lambda name: next(
    (i for i in purple.PurpleGetConversations() if purple.PurpleConversationGetTitle(i) == name), None)

logFile = open("Pidgin_Crossover_Messages.log", mode="a")
logStr = lambda string: logFile.write(
    str(u"[{}] ".format(datetime.now().isoformat())) + demojize(string).decode("utf-8",
        errors="remove"))

log = lambda string: [fct(string + "\n") for fct in (print, logStr)]  # Prints and writes to the log file.


def sendMessage(sending, receiving, nick, message):  # Sends a message on the given chat.
    if receiving is None:  # If the conversation can't be found by libpurple, it'll just error anyway.
        return

    if message[0:len(commandDelimiter)] == commandDelimiter:  # Do not send out commands! No! Bad!
        message = (" " if commandDelimiter[0] != " " else "_") + message

    # Actually send the messages out.
    if purple.PurpleConversationGetType(receiving) == 2:  # 2 means a group chat.
        conv = purple.PurpleConvChat(receiving)
        purple.PurpleConvChatSend(conv, (nick + ": " if nick is not None else "") + emojize(message, True))
    else:
        conv = purple.PurpleConvIm(receiving)
        purple.PurpleConvImSend(conv, (nick + ": " if nick is not None else "") + emojize(message, True))

    # I could put this behind debug, but I choose not to. It's pretty enough.
    sendTitle = purple.PurpleConversationGetTitle(sending)
    receiveTitle = purple.PurpleConversationGetTitle(receiving)
    log(demojize(
        u"Sent \"{}\" from {} ({}) to {} ({}).".format((nick + ": " + message if nick is not None else message),
            sendTitle, sending, receiveTitle, conv)))  # Sent "message" from chat 1 (chat ID) to chat 2 (chat ID).
    # Removes emojis from messages, not all consoles support emoji, and not all files can have emojis written to them.

    logFile.flush()  # Update the log since it's been written to.


# Returns what it says on the tin.
isListButNotString = lambda obj: isinstance(obj, (list, tuple, set)) and not isinstance(obj, basestring)


def messageListener(account, sender, message, conversation, flags):
    purple.PurpleConversationClearMessageHistory(conversation)  # Don't keep history
    global lastMessageTime
    if purple.PurpleAccountGetUsername(account) == sender:
        return
    elif datetime.now() - lastMessageTime < timedelta(seconds=.1):
        print("Overflow!", account, sender, message, conversation, flags)  # Debug stuff
        lastMessageTime = datetime.now()
        return
    lastMessageTime = datetime.now()
    # Strip HTML from Hangouts messages.
    message = purple.PurpleMarkupStripHtml(message) if message.startswith("<html>") else message

    nick = purple.PurpleBuddyGetAlias(purple.PurpleFindBuddy(account, sender))
    # Logs messages. Logging errors will not prevent commands from working.
    try:
        logStr(unicode("{}: {}").format(nick, unicode(message)))
        logFile.flush()
    except:
        pass
    # Run commands if the message starts with the command character.
    if message[0:len(commandDelimiter)] == commandDelimiter:
        command = message[len(commandDelimiter):message.find(" ") if " " in message else len(message)].lower()
        args = message.split(" ")[1:]
        argSet = (account, sender, message, conversation, flags)
        if not runCommand(argSet, command, *args):
            simpleReply(argSet, "Command/alias \"{}\" not found. Valid commands: {} Valid aliases: {}".format(command,
                str(sorted(commands.keys()))[1:-1], str(sorted(aliases.keys()))[1:-1]))
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
purple = bus.get("im.pidgin.purple.PurpleService", "/im/pidgin/purple/PurpleObject")  # Interface with libpurple client.
# Surprisingly, im.pidgin.* and im/pidgin/* work for Finch too. Not sure why.

# Run the message listener for IMs and Chats.
purple.ReceivedImMsg.connect(messageListener)
purple.ReceivedChatMsg.connect(messageListener)

GObject.MainLoop().run()
# 4/Vm4EVMEipb_5BK9s_PL9NIf6aofuvPTrAUgY_ADej_0 oauth