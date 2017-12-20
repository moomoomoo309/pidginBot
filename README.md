# pidginBot
A bot built on top of pidgin/finch (Maybe other libpurple clients?) using the DBus interface. It can:
- Send messages to and from chats across different (libpurple supported) chat protocols.
- Perform commands.

It can run on any linux-based system that supports libpurple. The bot assumes you're using konsole. If you aren't, switch the terminalName variable to match the terminal you use.

Dependencies:

 1. Python 2.7/3.4+ (May run on older versions, not tested)
 1. PyGObject (pip install pygobject)
 1. PyDBus (pip install pydbus)
 1. humanize (pip install humanize)
 1. parsedatetime (pip install parsedatetime)
 1. youtube-dl (pip install youtube-dl)
 1. Finch (sudo apt install finch)

On debian, the command to install all of the dependencies is:
`sudo apt install finch && sudo pip install pygobject pydbus humanize parsedatetime youtube-dl --upgrade`

How to use:

 1. Install all of the dependencies if they are not installed.
 1. Open finch.
 1. If you have not set up a bot account, do so now.
 1. Log into your bot account on finch.
 1. Run "runbot.sh"
 1. Profit!

The command delimiter is "!" by default, so commands can be run like "!help". Inputting a command that doesn't exist, such as "!commandThatDoesntExist" will print out a list of all valid commands.

More information on individual commands is available through "!help (commandname)" or in the helpText dictionary in the code.
