noErr=0
while [ $noErr -eq 0 ]
do
	echo "(Re)starting bot..."
	python pidginCrossover.py
	noErr=$?
done
