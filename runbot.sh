#!/usr/bin/env bash
export PYTHONIOENCODING=utf8
noErr=0
while [ ${noErr} -eq 0 ]
do
	if [ "$(pidof pidgin)" == "" ]
	then
	    echo "Starting pidgin..."
	    pidgin -c $PWD/.purple &
        echo "Started pidgin."
    fi
	sleep 1
	echo "Starting bot..."
	python3 pidginCrossover.py
	noErr=$?
	killall -q pidgin
done
