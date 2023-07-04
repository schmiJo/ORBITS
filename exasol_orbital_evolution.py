import pyexasol
import numpy as np
from datetime import datetime
import time, math
import pandas as pd

C = pyexasol.connect(dsn='192.168.178.33/3FE59876FF9E0C837ADFCE8E35EC0B40EBD7CDB2C28037807109101F2458D07A:8563', user='sys', password='exasol')

initial_orbit_positions = C.export_to_pandas("SELECT * FROM ORBITS.ORBITING_OBJECT_INITIAL")
initial_orbit_positions = initial_orbit_positions.reset_index()  # make sure indexes pair with number of rows

number_of_minutes = 30 # amount of minutes 

every_minute = np.arange(0, number_of_minutes, dtype=np.int32)

start_date_of_analysis =  int(datetime.strptime('2021-11-01 15:01:01.000000','%Y-%m-%d %H:%M:%S.%f' ).timestamp())
print(start_date_of_analysis)
every_minute += start_date_of_analysis


def evolve_orbit_3d(inclination, raan, eccentricity, argument_perigee, mean_anomaly, mean_motion, time):
    # inclination: inclination of the orbit in radians
    # raan: right ascension of the ascending node in radians
    # eccentricity: eccentricity of the orbit
    # argument_perigee: argument of perigee in radians
    # mean_anomaly: mean anomaly in radians
    # mean_motion: mean motion of the orbit in revolutions per day
    # time: array of time values (Unix timestamps) at which to evaluate the orbit

    # Constants
    gravitational_parameter = 398600.4418  # Earth's gravitational parameter in km^3/s^2
    radius_earth = 6378.137  # Earth's mean radius in kilometers

    # Preparing arrays to store the evolving orbit
    central_coordinates = np.zeros((len(time), 3))

    # Convert mean motion from revolutions per day to radians per second
    mean_motion = 2 * np.pi * mean_motion / (24 * 3600)

    for i, t in enumerate(time):
        # Calculating elapsed time from the initial time (Unix timestamp)
        elapsed_time = t - time[0]

        # Calculating mean anomaly at current time
        current_mean_anomaly = mean_anomaly + mean_motion * elapsed_time

        # Solving Kepler's equation for eccentric anomaly
        eccentric_anomaly = current_mean_anomaly
        while True:
            next_eccentric_anomaly = eccentric_anomaly - (eccentric_anomaly - eccentricity * np.sin(eccentric_anomaly) - current_mean_anomaly) / (1 - eccentricity * np.cos(eccentric_anomaly))
            if abs(next_eccentric_anomaly - eccentric_anomaly) < 1e-8:
                eccentric_anomaly = next_eccentric_anomaly
                break
            eccentric_anomaly = next_eccentric_anomaly

        # Calculating true anomaly
        true_anomaly = 2 * np.arctan2(np.sqrt(1 + eccentricity) * np.sin(eccentric_anomaly / 2), np.sqrt(1 - eccentricity) * np.cos(eccentric_anomaly / 2))

        # Calculating radius
        radius = (gravitational_parameter / mean_motion**2) ** (1 / 3) / (1 + eccentricity * np.cos(true_anomaly))

        # Calculating position vector in the orbital plane
        x_orbital_plane = radius * np.cos(true_anomaly)
        y_orbital_plane = radius * np.sin(true_anomaly)

        # Transforming position vector to the inertial frame
        x = x_orbital_plane * (np.cos(raan) * np.cos(argument_perigee) - np.sin(raan) * np.sin(argument_perigee) * np.cos(inclination)) - y_orbital_plane * (np.sin(raan) * np.cos(argument_perigee) + np.cos(raan) * np.sin(argument_perigee) * np.cos(inclination))
        y = x_orbital_plane * (np.cos(raan) * np.sin(argument_perigee) + np.sin(raan) * np.cos(argument_perigee) * np.cos(inclination)) + y_orbital_plane * (np.cos(raan) * np.cos(argument_perigee) * np.cos(inclination) - np.sin(raan) * np.sin(argument_perigee))
        z = x_orbital_plane * (np.sin(raan) * np.sin(inclination)) + y_orbital_plane * (np.cos(raan) * np.sin(inclination))

        # Storing the coordinates with the center of earth as the origin
        central_coordinates[i] = [x, y, z]

    return central_coordinates

final_df = None
count_merges = 0
for index, row in initial_orbit_positions.iterrows():
    print(index)
    every_minute[0] =  int(datetime.strptime(row['INITEPOCH'],'%Y-%m-%d %H:%M:%S.%f' ).timestamp())
    eccentricity = float('0.'+ str(row['ECCENTRICITY'])) 
    radial_coordinates = evolve_orbit_3d(
                            math.radians(float(row['INCLINATION'])), 
                            math.radians(float(row['RIGHTASCOFASCNODE'])),  
                            eccentricity,  
                            math.radians(float(row['ARGOFPERIGEE'])),  
                            math.radians(float(row['MEANANOMALY'])),  
                            math.radians(float(row['MEANMOTION'])),  
                            every_minute)
    
    df = pd.DataFrame(radial_coordinates, columns = ['X','Y','Z'])
    
    str_timestamps = []
    str_object_ids = []
    for i, timestamp in enumerate(every_minute):
        str_timestamps.append(datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')) 
        str_object_ids.append(row['OBJECTID'])
    df['EPOCH'] = str_timestamps
    df['OBJECTID'] = str_object_ids
    
    
    if final_df is None:
        final_df = df[['OBJECTID', 'EPOCH', 'X', 'Y', 'Z']]
    else:
        count_merges =  count_merges + 1
        final_df = pd.concat([final_df, df], ignore_index=True)
        
        
    if count_merges == 500:
        count_merges = 0
        final_df = final_df[['OBJECTID', 'EPOCH', 'X', 'Y', 'Z']]
         
        C.import_from_pandas(final_df, ('ORBITS','ORIBITING_CALC_POS'))
        final_df = None
         
    
