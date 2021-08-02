#! /usr/bin/env python3

import csv
import yaml
import math
from gcodeWriter import GcodeWriter

epsilon=1.0/100000

## Code review Mon Aug  2 10:04:12 AM CEST 2021

## Ailerons have only been trouble.  Consider re-doing, re-thinking, or
## ignoring

## The distance to the towers doesn't really belong in the YAML file?  It's a
## set-up parameter rather than a wing parameter -- enter at time of
## generation?  As command-line option?  Interactive?  Both?

## Might restructure the whole thing to a grid of fine-enough points
##  then reduce back down by some arbitrary curvature rule?



DEBUG = True  ## printf debugging!
# DEBUG = False 
PLOTME = True

def foil_top(profile):
    return([x for x in profile if x[1] >= 0 ])

def foil_bottom(profile):
    return([x for x in profile if x[1] < 0 ])

def load_data(filename):
    """ Load up airfoil profile  
    Uses foil_top and foil_bottom functions to parse
    Any lines that don't parse as numeric pairs are ignored
    """
    f = open(filename)
    profile = []
    for p in f:
        try:
            x,y = p.strip().split()
            x=float(x)
            y=float(y)
            profile.append([x,y])
        except: # whatever kind of non-parsing junk...
            pass 
    f.close()
    ## convert to selig format: trailing edge to trailing edge
    top = foil_top(profile)
    top.sort(key=lambda x: x[0], reverse=True)
    bottom = foil_bottom(profile)
    bottom.sort(key=lambda x: x[0])
    top.extend(bottom)
    return(top)

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

def is_between(a,b,x):
    if a < x and x < b:
        return(True)
    if b < x and x < a:
        return(True)
    return(False)

def closest_to(target, value_list):
    return min(value_list, key = lambda x: abs(x-target))
def index_closest_to(target, value_list):
    return value_list.index(closest_to(target, value_list)) 

def find_neighbors(x, profile):
    for i in range(len(profile)-1):
        if is_between(profile[i][0], profile[i+1][0], x):
            return(profile[i], profile[i+1])
    return None


def linear_interpolate(x1, y1, x2, y2, xm):
    dx = x2 - x1
    dy = y2 - y1
    dm = xm - x1
    return (dm / dx * dy + y1)

## the load_profile function seems to make a single dataset, which this then
## takes apart.  redundant?
def match_profiles(thisProfile, thatProfile):
    ## split, merge, reorder
    top = foil_top(thisProfile)
    topX = [x[0] for x in top]
    bottom = [[0,0]] ## needs 0,0 for linear interpolation purposes
    bottom.extend(foil_bottom(thisProfile))
    bottomX = [x[0] for x in bottom]
    that_top = foil_top(thatProfile)
    that_bottom = foil_bottom(thatProfile)

    ## need to think about wrapping around! 
    ## this part of the code creates points in this profile where the X
    ## matches, but the Y is linearly interpolated.
    ## Running this on both profiles should make sure that every X appears
    ##  in each.  
    ## A better way to do this might be a cubic interpolation to a sufficiently
    ##  fine grid of points, but then _really_ want to keep the same max
    ## resolution on the leading edge, which this does automatically
    for point in that_top: 
        if point[0] not in topX:
            xm = point[0]
            try:
                lower, higher = find_neighbors(xm, top)
                ym = linear_interpolate(lower[0], lower[1], higher[0], higher[1], xm)
                top.append([xm, ym])
            except TypeError: # when find_neighbors is None -- duplicate closest point
                ## adding 1.0 to Drela's airfoils fixes this.  Crap.
                ym = top[index_closest_to(xm, topX)][1]
                top.append([xm, ym])
                if DEBUG:
                    print("top extrapolation", point, "to", [xm, ym])

    for point in that_bottom: 
        if point[0] not in bottomX:
            xm = point[0]
            try:
                lower, higher = find_neighbors(xm, bottom)
                ym = linear_interpolate(lower[0], lower[1], higher[0], higher[1], xm)
                bottom.append([xm, ym])
            except TypeError: # when find_neighbors is None -- duplicate closest point
                ym = bottom[index_closest_to(xm, bottomX)][1]
                bottom.append([xm, ym])
                if DEBUG:
                    print("bottom extrapolation", point, "to", [xm, ym])
                        
    top.sort(key=lambda x: x[0], reverse=True)
    bottom.sort(key=lambda x: x[0])
    bottom.pop(0)
    top.extend(bottom)
    return( top )


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

def calculate_normals(profile):
    normals = []
    for i,p in enumerate(profile):
        try:
            next_point = profile[i+1]
            dx = profile[i+1][0] - p[0]
            dy = profile[i+1][1] - p[1]
            angle = math.atan( dy/dx ) 
            if dx <= 0:  ## arctangent stuff, bounded -pi/2, pi/2
                angle = angle - math.pi
            ## travels CCW around profile, subtracting off 90 degrees
            angle = angle - math.pi/2
            normalX = math.cos(angle)
            normalY = math.sin(angle)
        except IndexError: ## last point: assume roughly horizontal, just shift down
                normalX = 0
                normalY = -1
        normals.append((normalX, normalY))
    return(normals)

def calculate_distances(profile):
    distances = []
    for i,p in enumerate(profile):
        try:
            next_point = profile[i+1]
            dx = profile[i+1][0] - p[0]
            dy = profile[i+1][1] - p[1]
            dist = math.sqrt(dx**2 + dy**2)
        except IndexError: ## last point: punt.
            dist = 10
        distances.append(dist)
    return(distances)
    

def compensate_kerf(thisProfile, thatProfile, kerf):
    '''Add extra kerf outisde, and even more to points where the current profile is going slower than
    the other profile.  For now a linear guesstimate should work'''
    thisNormals = calculate_normals(thisProfile)
    thisDistances = calculate_distances(thisProfile)
    thatDistances = calculate_distances(thatProfile)
    for i,p in enumerate(thisProfile):
        relative_distance = thatDistances[i]/thisDistances[i]  
        ## introduce some other function of relative_distance if necessary
        ## luminance-corrected kerf
        p[0] = p[0] + thisNormals[i][0] * kerf * max(1, relative_distance)
        p[1] = p[1] + thisNormals[i][1] * kerf * max(1, relative_distance)
    return(thisProfile)


def add_ailerons(profile, percentage, hinge_depth):
    """cuts ailerons with cord a fixed percentage of the wing"""
    chord = column_max(profile, 0) - column_min(profile, 0) 
    aileron_chord = percentage * chord / 100
    cut = column_max(profile, 0) - aileron_chord
    halfway = int(len(profile)/2)
    cut_end_index = index_closest_to(cut, [x[0] for x in profile[:halfway]])

    ## depth includes 2*kerf at this point: hinge_depth needs to account for
    ## that, plus the thickness of the hinge remaining
    top = min(profile[:halfway], key = lambda x: abs(x[0]-profile[cut_end_index][0]))[1]
    bottom = min(profile[halfway:], key = lambda x: abs(x[0]-profile[cut_end_index][0]))[1]
    depth = top - bottom - hinge_depth
    travel = depth * 0.3 ## hardcoded for now -- how wide the cut
    cut_start_index =  index_closest_to(cut + travel, [x[0] for x in profile[:halfway]])

    if DEBUG:   
        print("aileron cutout:", cut_start_index, cut_end_index)
    if cut_end_index - cut_start_index > 1:
        ## linear interpolation along the cut to keep # points constant
        for i in range(cut_start_index + 1, cut_end_index):
            x, y = profile.pop(i)
            ym = linear_interpolate(profile[cut_start_index][0], profile[cut_start_index][1], 
                    profile[cut_end_index][0], (bottom+hinge_depth), x)
            profile.insert(i, [x, ym])
    ## add in hinge bottom
    profile.pop(cut_end_index)
    profile.insert(cut_end_index, [profile[cut_end_index][0], (bottom+hinge_depth)] )
    
    return profile


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

    gcodewriter.absolute_coordinates()
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

if PLOTME:
    ## plot profiles 
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np
    def plotme(profileX, profileU, points=False):
        # Data for plotting
        xx = [x[0] for x in profileX]
        yy = [x[1] for x in profileX]
        uu = [x[0] for x in profileU]
        vv = [x[1] for x in profileU]
        fig, ax = plt.subplots()
        ax.set_aspect(1)
        if points:
            ax.plot(xx, yy, "g-o")
            ax.plot(uu, vv, "r-o")
        else:
            ax.plot(xx, yy)
            ax.plot(uu, vv)
        ax.grid()
        plt.show()

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
        print()
        print("Generating", wing_gcode_filename)

        g = GcodeWriter(wing_gcode_filename)

        ## read in profiles
        profileX = load_data(wingX["foil"])
        profileU = load_data(wingU["foil"])
        if DEBUG:
            print("wingX: ", wingX["foil"])
            print("length: ", len(profileX))
            print("wingU: ", wingU["foil"])
            print("length: ", len(profileU))
            # plotme(profileX, profileU)

        ## match profile points to each other
        if not len(profileX) == len(profileU):
            profileX = match_profiles(profileX, profileU)
            # plotme(profileX, profileU)
            profileU = match_profiles(profileU, profileX)
            # plotme(profileX, profileU)

        ## double-check
        if not len(profileX) == len(profileU):
            print("Profile lengths don't match.  Fixme")
            print("Lengths: ", len(profileX), len(profileU))
            for i in range(min(len(profileX), len(profileU))):
                print(profileX[i][0], profileU[i][0])
            1/0

        ## washout wing tip: rotate profile
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
            profileX = compensate_kerf(profileX, profileU, kerf)
            profileU = compensate_kerf(profileU, profileX, kerf)
        except KeyError: 
            print("No kerf specified.  Not compensated.")

        if DEBUG:
            print("post kerf lengths: ", len(profileX), len(profileU) )

        ## add aileron cutouts if defined
        try:
            aileron_percentage = float(wing['aileron'])
            aileron_bottom = 2*kerf + float(wing['aileron_hinge_thickness'])
            profileX = add_ailerons(profileX, aileron_percentage, aileron_bottom)
            profileU = add_ailerons(profileU, aileron_percentage, aileron_bottom)
        except KeyError: ## no aileron difference passed
            print("No aileron cutout.")
        
        if DEBUG:
            print( "post aileron lengths: ",  len(profileX), len(profileU) )

        ## fit to workspace
        coordinates = project_to_towers(profileX, profileU)

        ## writeout to G-code
        gcode_preamble(g, coordinates)
        for x,y,u,v in coordinates:
            g.move(x, y, u, v)
        gcode_postscript(g, coordinates)
        g.close()


    if PLOTME:
        plotme(profileX, profileU)
        # plotme(profileX, profileU, points=True)


