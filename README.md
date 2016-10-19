# pidginBot
A bot built on top of pidgin/finch (Maybe other libpurple clients?) using the DBus interface. It can:

-Send messages to and from chats across different (libpurple supported) chat protocols.

-Perform commands.

It can run on any linux-based system that supports libpurple.

Dependencies:

-Python 2.7/3.4 (May run on 3.5 or older versions, not tested)

-PyGObject (pip install pygobject)

-emoji (pip install emoji)

-PyDBus (pip install pydbus)

-humanize (pip install humanize)

-Pidgin or Finch (sudo apt-get install pidgin or sudo apt-get install finch)


How to use:
After installing all of the dependencies:

-Open pidgin/finch

-If you have not set up a bot account, do so now.

-Run "python pidginCrossover.py"

-Profit!


The command delimiter is "!" by default, so commands can be run like "!help". Inputting a command that doesn't exist, such as "!commandThatDoesntExist" will print out a list of all valid commands.

More information on individual commands is available through "!help (commandname)".
