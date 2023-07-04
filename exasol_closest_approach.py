import pyexasol
import numpy as np
from datetime import datetime
import time, math
import pandas as pd

C = pyexasol.connect(dsn='192.168.178.33/3FE59876FF9E0C837ADFCE8E35EC0B40EBD7CDB2C28037807109101F2458D07A:8563', user='sys', password='exasol')


 

number_of_minutes = 25 # amount of minutes 

every_minute = np.arange(0, number_of_minutes, dtype=np.int32)

start_date_of_analysis =  int(datetime.strptime('2021-11-01 15:01:01.000000','%Y-%m-%d %H:%M:%S.%f' ).timestamp())
print(start_date_of_analysis)
every_minute += start_date_of_analysis

from sklearn.neighbors import NearestNeighbors

i= 0
for timestamp in every_minute:
    i += 1 
    print(str(i) + 'of' + str(number_of_minutes))
    
    time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')  
    positions = C.export_to_pandas(f"SELECT * FROM ORBITS.ORIBITING_CALC_POS where EPOCH = '{time_str}'")
 
    if len(positions) == 0:
        continue;
    positions = positions.reset_index()  # make sure indexes pair with number of rows 
    
    
    positions_xyz = positions.copy().drop(columns = ['EPOCH', 'OBJECTID', 'index'] )
    np_positions = positions_xyz.to_numpy()
    nbrs = NearestNeighbors(n_neighbors=2, algorithm='ball_tree').fit(np_positions)
    distances, indices = nbrs.kneighbors(np_positions)
    distances = distances[:, 1]
    indices = indices[:, 1]
    
    positions_copy = positions.copy()
    object_id1 = positions.copy().drop(columns = [ 'index', 'EPOCH', 'X', 'Y', 'Z'] )
    epoch = positions.copy().drop(columns = [ 'index', 'OBJECTID', 'X', 'Y', 'Z'] )
    
    
    object_id2 = []
     
    for object_id_2_idx in indices:
        #print(positions_copy)
        object_id2.append(positions_copy['OBJECTID'].iloc[object_id_2_idx])
        pass
     
    
    closest_distance_df = pd.DataFrame(data = {'DISTANCE': distances})
    
    closest_distance_df['OBJECTID1'] = object_id1
    closest_distance_df['OBJECTID2'] = object_id2
    closest_distance_df['EPOCH'] = time_str
    
    
    closest_distance_df = closest_distance_df[['OBJECTID1', 'OBJECTID2', 'EPOCH', 'DISTANCE']]
    
    
    C.import_from_pandas(closest_distance_df, ('ORBITS','CLOSEST_APPROACH'))
    
   
    
    
    
    
    