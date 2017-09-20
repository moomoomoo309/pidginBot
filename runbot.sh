#!/usr/bin/env bash
konsole -e "finch" & &> /dev/null
sleep .5
noErr=0
while [ ${noErr} -eq 0 ]
do
	echo "(Re)starting bot..."
	python pidginCrossover.py
	noErr=$?
	killall -q finch
done
