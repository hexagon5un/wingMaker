#! /usr/bin/env python3

import csv
import yaml
import math

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

def scale_and_sweep_profile(profile, chord, sweep):
    new_profile = []
    for x,y in profile:
        x = x * chord + sweep
        y = y * chord
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

def gcode_preamble(outfile):
    """ do setup """
    outfile.write("F{}\n".format(wing["feed_rate"]))

def gcode_postscript(outfile):
    """ do finish up """

if __name__ == "__main__":
    import sys
    wing_filename = sys.argv[1]
    wing_gcode_filename = wing_filename.split(".")[0] + ".gcode"

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

    ## scale to chord and offset by wing sweep
    profileA = scale_and_sweep_profile( profileA, float(wing['chordA']), float(wing['sweepA']) )
    profileB = scale_and_sweep_profile( profileB, float(wing['chordB']), float(wing['sweepB']) )
    
    ## fit to workspace
    coordinates = project_to_towers(profileA, profileB)

    ## writeout to G-code
    outfile = open(wing_gcode_filename, "w")
    gcode_preamble(outfile)
    
    for x,y,u,v in coordinates:
        outfile.write("G1 X{} Y{} U{} V{}\n".format(x,y,u,v))

    gcode_postscript(outfile)
    outfile.close()


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

