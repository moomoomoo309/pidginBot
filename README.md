# pidginBot
A bot built on top of pidgin/finch (Maybe other libpurple clients?) using the DBus interface. It can:

-Send messages to and from chats across different (libpurple supported) chat protocols.
-Perform commands.

It can run on any linux-based system that supports libpurple.

Dependencies:

 1. Python 2.7/3.4+ (May run on older versions, not tested)
 1. PyGObject (pip install pygobject)
 1. emoji (pip install emoji)
 1. PyDBus (pip install pydbus)
 1. humanize (pip install humanize)
 1. parsedatetime (pip install parsedatetime)
 1. Pidgin or Finch (sudo apt-get install pidgin or sudo apt-get install finch)

On debian, the command to install all of the dependencies is:
`sudo apt-get install pidgin && sudo pip install pygobject emoji pydbus humanize parsedatetime --upgrade`

How to use:

 1. Install all of the dependencies if they are not installed.
 1. Open pidgin/finch.
 1. If you have not set up a bot account, do so now.
 1. Log into your bot account on pidgin/finch.
 1. Run "runbot.sh"
 1. Profit!

The command delimiter is "!" by default, so commands can be run like "!help". Inputting a command that doesn't exist, such as "!commandThatDoesntExist" will print out a list of all valid commands.

More information on individual commands is available through "!help (commandname)" or in the helpText dictionary in the code.
