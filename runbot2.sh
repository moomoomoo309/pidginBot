#!/usr/bin/env bash
noErr=0
while [ ${noErr} -eq 0 ]
do
	echo "(Re)starting bot..."
	python3 messageConfirmer.py
	noErr=$?
done
