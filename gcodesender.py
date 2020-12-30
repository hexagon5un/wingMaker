#!/usr/bin/env python
"""\
Simple g-code streaming script
"""
 
import serial
import time
import sys

#s = serial.Serial('/dev/ttyACM0',115200)
s = serial.Serial('/dev/ttyUSB0',115200)
f = open(sys.argv[1],'r');
 
# Wake up 
s.write("\r\n\r\n") # Hit enter a few times to wake the Printrbot
time.sleep(2)   # Wait for Printrbot to initialize
s.flushInput()  # Flush startup text in serial input
print ('Sending gcode')
 
# Stream g-code
for line in f:
	l = line.strip() # Strip all EOL characters for streaming
	if  (l.isspace()==False and len(l)>0) :
		print ('Sending: ' + l)
		s.write(l + '\n') # Send g-code block
		grbl_out = s.readline() # Wait for response with carriage return
		print (' : ' + grbl_out.strip())
 
 
# Close file and serial port
f.close()
s.close()

