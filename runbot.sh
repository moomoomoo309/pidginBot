#!/usr/bin/env bash
export PYTHONIOENCODING=utf8
noErr=0
while [ ${noErr} -eq 0 ]
do
	if [ "$(pidof finch)" == "" ]
	then
	    echo "Starting finch..."
		konsole -e "finch" &
	fi
    sleep 1
	echo "Starting bot..."
	python pidginCrossover.py
	noErr=$?
	killall -q finch
done
