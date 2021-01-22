%: %.yaml
	./wingMaker.py $^

%_left.gcode: %.yaml
	./wingMaker.py $^

%_right.gcode: %.yaml
	./wingMaker.py $^


clean:
	rm *.gcode

.PHONY: clean

