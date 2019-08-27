#!/usr/bin/env bash
export PYTHONIOENCODING=utf8
noErr=0
while [ ${noErr} -eq 0 ]
do
	while [ "$(pidof pidgin)" == "" ]; do
	    echo "Starting pidgin..."
	    pidgin  &
        sleep 1
    done
    sleep 1
    echo "Started pidgin."
	echo "Starting bot..."
	python3 pidginCrossover.py
	noErr=$?
	killall -q pidgin
    sleep 1
done
