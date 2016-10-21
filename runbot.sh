noErr=2
while [ $noErr -ne 0 ]
do
	echo "(Re)starting bot..."
	python pidginCrossover.py
	noErr=$?
done
