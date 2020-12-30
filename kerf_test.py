#! /usr/bin/env python3

import sys
from gcodeWriter import GcodeWriter

depth = 0    ## will cut to this depth: if you zero on the plate, use a positive number here
height = 30 + depth ## tall enough to clear your foam scrap
notch = 20   ## makes notches/gaps that are this wide
speeds = sys.argv[1:]

g = GcodeWriter("kerf_test.gcode")
g.travel(0, height, 0, height)

for i, speed in enumerate(speeds):
    g.set_speed(speed)
    g.travel((i*2+1)*notch, height, (i*2+1)*notch, height)
    g.move((i*2+1)*notch, depth, (i*2+1)*notch, depth)
    g.move((i*2+2)*notch, depth, (i*2+2)*notch, depth)
    g.move((i*2+2)*notch, height, (i*2+2)*notch, height)

g.travel(0, height, 0, height)
g.travel(0, 0, 0, 0)



