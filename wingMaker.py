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

def project_to_towers(profileX, profileU):
    coordinates = []
    scaleX = float(wing['towerX_dist'])/float(wing['block_width'])
    scaleU = float(wing['towerU_dist'])/float(wing['block_width'])
    for i in range(len(profileX)):
        x = profileX[i][0] + scaleX*(profileX[i][0] - profileU[i][0])
        y = profileX[i][1] + scaleX*(profileX[i][1] - profileU[i][1])
        u = profileU[i][0] + scaleU*(profileU[i][0] - profileX[i][0])
        v = profileU[i][1] + scaleU*(profileU[i][1] - profileX[i][1])
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
    wing_gcode_base = wing_filename.split(".")[0]   

    ## load up wing / setup spec 
    try:
        wing = yaml.load(open(wing_filename, "r"), Loader=yaml.BaseLoader)
    except: 
        print('Pass a wing spec file as argument.')
        exit()

    symmetry = [ [wing_gcode_base + "_right.gcode", wing['tip'], wing['root']],
                 [wing_gcode_base + "_left.gcode",  wing['root'], wing['tip']]]

    for wing_gcode_filename, wingX, wingU in symmetry:

        g = GcodeWriter(wing_gcode_filename)

        ## read in profiles
        profileX = load_data(wingX["foil"])
        profileU = load_data(wingU["foil"])

        ## washout wing tip
        profileX = twist_profile(profileX, float(wingX['washout']))
        profileU = twist_profile(profileU, float(wingU['washout']))

        ## scale to chord and offset by wing sweep and margin
        offsetX = float(wingX['sweep']) + float(wing['margin'])
        offsetU = float(wingU['sweep']) + float(wing['margin'])
        profileX = scale_and_sweep_profile( profileX, float(wingX['chord']), offsetX, float(wingX['lift']) )
        profileU = scale_and_sweep_profile( profileU, float(wingU['chord']), offsetU, float(wingU['lift']) )
        
        ## fit to workspace
        coordinates = project_to_towers(profileX, profileU)

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
        t = [x[0] for x in profileX]
        s = [x[1] for x in profileX]
        xx = [x[0] for x in profileU]
        yy = [x[1] for x in profileU]
        fig, ax = plt.subplots()
        ax.plot(t, s)
        ax.plot(xx, yy)
        ax.grid()
        plt.show()

