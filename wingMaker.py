#! /usr/bin/env python3

import csv
import yaml
import math
from gcodeWriter import GcodeWriter

def load_data(filename):
    """ Load up airfoil profile  
    Assumes Selig format for now: from back to front
    Any lines that don't parse as numeric pairs are ignored
    Can't tell top from bottom... """
    f = csv.reader(open(filename), delimiter=' ', skipinitialspace=True)
    profile = []
    for p in f:
        try:
            x,y = [float(p[0]), float(p[1])]
            profile.append([x,y])
        except: # whatever kind of non-parsing junk...
            # print(p)
            pass 
    return(profile)

def median(points):
    return( ( max(points) - min(points) ) / 2 )
def degrees_to_radians(theta):
    return(theta/180*math.pi)
def radians_to_degrees(x):
    return(x*180/math.pi)
def sign(x):
    return(x/abs(x))

def twist_profile(profile, degrees_washout):
    centerX = median([x[0] for x in profile]) 
    centerY = median([x[1] for x in profile]) 
    twisted = []
    for x,y in profile:
        x = x - centerX
        y = y - centerY
        theta = math.atan( y / x )
        radius = math.sqrt( x**2 + y**2 )
        theta2 = theta + degrees_to_radians(degrees_washout)
        twisted.append([centerX + sign(x) * radius * math.cos(theta2), 
            centerY + sign(x) * radius * math.sin(theta2)])
    return(twisted)

def scale_and_sweep_profile(profile, chord, sweep, lift):
    new_profile = []
    for x,y in profile:
        x = x * chord + sweep
        y = y * chord + lift
        new_profile.append([x,y])
    return(new_profile)

def project_to_towers(profileA, profileB):
    coordinates = []
    scaleA = float(wing['towerA_dist'])/float(wing['block_width'])
    scaleB = float(wing['towerB_dist'])/float(wing['block_width'])
    for i in range(len(profileA)):
        x = profileA[i][0] + scaleA*(profileA[i][0] - profileB[i][0])
        y = profileA[i][1] + scaleA*(profileA[i][1] - profileB[i][1])
        u = profileB[i][0] + scaleB*(profileB[i][0] - profileA[i][0])
        v = profileB[i][1] + scaleB*(profileB[i][1] - profileA[i][1])
        coordinates.append([x,y,u,v])
    return(coordinates)

def gcode_preamble(gcodewriter, coordinates):
    """ procedure: 
        zero out, align block, press go"""

    margin = float(wing['margin']) 
    travel_height = wing['travel_height']
    feed_rate = wing["feed_rate"]

    gcodewriter.travel(0, travel_height, 0, travel_height) ## move up and over
    gcodewriter.travel(coordinates[0][0]+margin, travel_height, coordinates[0][2]+margin, travel_height) ## move past trailing edge
    gcodewriter.set_speed(feed_rate)
    gcodewriter.move(coordinates[0][0]+margin, coordinates[0][1],
            coordinates[0][2]+margin, coordinates[0][3]) ## down into the block with margin on trailing edge


def gcode_postscript(gcodewriter, coordinates):
    """ do finish up """
    margin = float(wing['margin']) 
    travel_height = wing['travel_height']
    
    gcodewriter.move(coordinates[-1][0]+margin, coordinates[-1][1], coordinates[-1][2]+margin, coordinates[-1][3]) ## cut out extra "margin"
    gcodewriter.move(coordinates[-1][0]+margin, travel_height, coordinates[-1][2]+margin, travel_height) ## then up
    gcodewriter.travel(0, travel_height, 0, travel_height) ## and back home
    gcodewriter.travel(0, 0, 0, 0)


if __name__ == "__main__":
    import sys
    wing_filename = sys.argv[1]
    wing_gcode_filename = wing_filename.split(".")[0] + ".gcode"
    g = GcodeWriter(wing_gcode_filename)

    ## load up wing / setup spec 
    try:
        wing = yaml.load(open(wing_filename, "r"), Loader=yaml.BaseLoader)
    except: 
        print('Pass a wing spec file as argument.')
        exit()

    ## read in profiles
    profileA = load_data(wing["foilA"])
    profileB = load_data(wing["foilB"])

    ## washout wing tip
    profileA = twist_profile(profileA, float(wing['washoutA']))
    profileB = twist_profile(profileB, float(wing['washoutB']))

    ## scale to chord and offset by wing sweep and margin
    offsetA = float(wing['sweepA']) + float(wing['margin'])
    offsetB = float(wing['sweepB']) + float(wing['margin'])
    profileA = scale_and_sweep_profile( profileA, float(wing['chordA']),
            offsetA, float(wing['liftA']) )
    profileB = scale_and_sweep_profile( profileB, float(wing['chordB']), 
            offsetB, float(wing['liftB']) )
    
    ## fit to workspace
    coordinates = project_to_towers(profileA, profileB)

    ## writeout to G-code
    gcode_preamble(g, coordinates)

    for x,y,u,v in coordinates:
        g.move(x, y, u, v)

    gcode_postscript(g, coordinates)
    g.close()


    if False:
        ## plot profiles 
        import matplotlib
        import matplotlib.pyplot as plt
        import numpy as np
        # Data for plotting
        t = [x[0] for x in profileA]
        s = [x[1] for x in profileA]
        xx = [x[0] for x in profileB]
        yy = [x[1] for x in profileB]
        fig, ax = plt.subplots()
        ax.plot(t, s)
        ax.plot(xx, yy)
        ax.grid()
        plt.show()

