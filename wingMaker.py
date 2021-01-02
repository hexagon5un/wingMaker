#! /usr/bin/env python3

import csv
import yaml
import math
from gcodeWriter import GcodeWriter

epsilon=1.0/100000

def load_data(filename):
    """ Load up airfoil profile  
    Assumes Selig format for now: from back to front
    Any lines that don't parse as numeric pairs are ignored
    Can't tell top from bottom... """
    f = open(filename)
    profile = []
    for p in f:
        try:
            x,y = p.strip().split()
            x=float(x)
            y=float(y)
            profile.append([x,y])
        except: # whatever kind of non-parsing junk...
            # print(p)
            pass 
    f.close()
    return(profile)

def median(points):
    return( ( max(points) - min(points) ) / 2 )
def degrees_to_radians(theta):
    return(theta/180*math.pi)
def radians_to_degrees(x):
    return(x*180/math.pi)
def sign(x):
    if x == 0:
        return(1)
    else:
        return(x/abs(x))
def column_min(data, column):
    return(min(data, key=lambda x: x[column])[column])
def column_max(data, column):
    return(max(data, key=lambda x: x[column])[column])

def twist_profile(profile, degrees_washout):
    centerX = median([x[0] for x in profile]) 
    centerY = median([x[1] for x in profile]) 
    twisted = []
    for x,y in profile:
        x = x - centerX
        if x == 0:
            x = epsilon ## avoid /0 in arctan
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

def compensate_kerf(profile, kerf):
    new_profile = []
    for i,p in enumerate(profile):
        try:
            next_point = profile[i+1]
            dx = profile[i+1][0] - p[0]
            dy = profile[i+1][1] - p[1]
            if dx == 0: ## hopefully only happens on the top side: hack!
                p[1] = p[1] + kerf 
                p[0] = p[0] + kerf 
            else:
                ## travels CCW around profile, subtracting off 45 degrees
                angle = math.atan( dy/dx ) 
                if dx <= 0:
                    angle = angle - math.pi
                angle = angle - math.pi/2
                p[0] = p[0] + math.cos(angle)*kerf
                p[1] = p[1] + math.sin(angle)*kerf
        except IndexError: ## last point
                p[1] = p[1] - kerf
        
        new_profile.append(p)
    
    return(new_profile)
                


def add_ailerons(profile, width, hinge_depth):
    """close enough is good enough?"""
    # extent = max(column_max(profile, 0)) - min(
    cut = column_max(profile, 0) - width
    halfway = int(len(profile)/2)
    top = min(profile[:halfway], key = lambda x: abs(x[0]-cut))[1]
    bottom = min(profile[halfway:], key = lambda x: abs(x[0]-cut))[1]
    # horizontal travel = depth at 45 degrees is too far.
    travel = 0.3 * (top - bottom)

    new_coords = []
    started_cut = False
    done_with_cut = False
    for p in profile:
        if not started_cut:
            if p[0] <= cut + travel:
                new_coords.append([cut, bottom + hinge_depth])
                started_cut = True
            else:
                new_coords.append(p)
        else: ## in cut
            if not done_with_cut:
                if p[0] < cut:  ## last X in cut
                    new_coords.append([cut, top])
                    done_with_cut = True
                else:
                    new_coords.append([cut, bottom + hinge_depth])
                    ## to maintain profile element length -- hack, hack
            else: # done with cut, just copy through
                new_coords.append(p)
    return(new_coords)

    

def project_to_towers(profileX, profileU):
    """ this assumes that both profiles have the same number of coordinates """
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
        
        print("max foam height: {}".format(max(column_max(profileX, 1), column_max(profileU,1))))
        print("min foam height: {}".format(min(column_min(profileX, 1), column_min(profileU,1))))
        
        ## compensate kerf
        try:
            kerf = float(wing['kerf'])
        except KeyError: ## default to 1 mm?
            kerf = 1

        profileX = compensate_kerf(profileX, kerf)
        profileU = compensate_kerf(profileU, kerf)

        ## add aileron cutouts if defined
        try:
            aileron_depth = 2*kerf + float(wing['aileron_hinge_thickness'])
        except KeyError: ## default to 1 mm?
            aileron_depth = 2*kerf + 1

        try: 
            aileronX = float(wingX['aileron'])
            aileronU = float(wingU['aileron'])
            profileX = add_ailerons(profileX, aileronX, aileron_depth)
            profileU = add_ailerons(profileU, aileronU, aileron_depth)
        except KeyError: ## no aileron difference passed, ignore
            pass


        ## fit to workspace
        coordinates = project_to_towers(profileX, profileU)

        ## writeout to G-code
        gcode_preamble(g, coordinates)
        for x,y,u,v in coordinates:
            g.move(x, y, u, v)
        gcode_postscript(g, coordinates)
        g.close()


    if True:
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
        ax.set_aspect(1)
        ax.plot(t, s)
        ax.plot(xx, yy)
        ax.grid()
        plt.show()

