#! /usr/bin/env python3

import sys
import math
from gcodeWriter import GcodeWriter


if (not len(sys.argv) == 3):
    print("Arguments: angle, cut depth below zero \nExample: 7 10 cuts a seven degree dihedral 10 mm lower than the vertical zero offset")
    exit()
else: 
    angle, cut_depth = sys.argv[1:3]
    angle = float(angle)
    cut_depth = float(cut_depth)


default_height = 70  ## change me if you want.  who has such big blocks?
radians = angle * math.pi / 180   
xoffset = (default_height + cut_depth) * math.tan(radians) 

g = GcodeWriter( "dihedral_{}_{}.gcode".format(int(angle), int(cut_depth)) )
# g.travel(0, 0, 0, 0)
g.travel(0, default_height, 0, default_height)
g.travel(xoffset, default_height, xoffset, default_height)
g.move(0, -cut_depth, 0, -cut_depth)
# g.travel(0, 0, 0, 0)
g.close()





