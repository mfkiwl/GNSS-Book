# -*- coding: utf-8 -*-
"""
Created on Tue Nov 14 15:01:15 2023

@author: ASTI
"""

import georinex as gr
import pandas as pd
import numpy as np
import numpy.linalg as la
import matplotlib.pyplot as plt
from methods.sat_pos import *
from methods.localization import *
from datetime import datetime,timedelta
import time

def calc_rcvr_pos(rcvr_time,nav,group,x0,count):
    init_x = x0
        
    print(f"Epoch: {rcvr_time}")
    
    while True:
        H = np.empty((0,3))
        p_arr = np.empty((0,1))
        group = group.dropna(subset=['C1C','C2W','L1C','L2W'])
        
        for sv in group.SV.unique():
            group_sub = group[group.SV == sv]
            p1 = group_sub.C1C.values
            p2 = group_sub.C2W.values
            pseudorange = (((f1**2) / ((f1**2) - (f2**2))) * p1) - (((f2**2) / ((f1**2) - (f2**2))) * p2)
            p = pseudorange[np.newaxis,:] + (calcSatBias(rcvr_time,nav,sv)*c) - init_x[-1]
            
            ###pseudoranges
            # pseudorange1 = group_sub.C1C
            # p1 = pseudorange1.values[:,np.newaxis] + (calcSatBias(rcvr_time,nav,sv) - init_x[-1]/c)*c
            
            # pseudorange2 = group_sub.C2W
            # p2 = pseudorange2.values[:,np.newaxis] + (calcSatBias(rcvr_time,nav,sv) - init_x[-1]/c)*c
            
            # ###carrier phase measurements
            # carrier1 = group_sub.L1C
            # cp1 = carrier1.values[:,np.newaxis] * c/(f1*1e6) + (calcSatBias(rcvr_time,nav,sv) - init_x[-1]/c)*c
            
            # carrier2 = group_sub.L2W
            # cp2 = carrier2.values[:,np.newaxis] * c/(f2*1e6) + (calcSatBias(rcvr_time,nav,sv) - init_x[-1]/c)*c
            
            # f_arr = np.vstack([p1,p2,cp1,cp2])
            
            # p, iono_delay, N1, N2 = dualF_eq(f_arr,f1,f2)
            # p = p[:,np.newaxis]
            
            sat_pos = calcSatPos(rcvr_time, p.flatten()[0], nav, sv)
            sat_pos = rot_satpos(sat_pos,p)
            
            if count == 0:
                H = np.vstack((H,sat_pos.T))    
                p_arr = np.append(p_arr,p,axis=0)
            
            else:
                azimuth, elevation = calc_az_el(ecef2enu(np.array(init_x[:-1])[np.newaxis,:],sat_pos.T))
                
                if elevation < 5.:
                    continue
                else:
                    H = np.vstack((H,sat_pos.T))    
                    p_arr = np.append(p_arr,p,axis=0)
        
        if len(H) < 4:
            raise Exception("Less than 4 satellites in view")
        else:
            pass
        
        x = init_x
        delta_xb = la.inv(G_mat(x,H).T @ G_mat(x,H)) @ G_mat(x,H).T @ (p_arr - est_p(x,H) + init_x[-1] - x[-1])
        x = x + delta_xb.flatten()
        
        counter = 0
        while ((np.abs(delta_xb) > 1e-8).all()) & (counter <= 100):
            delta_xb = la.inv(G_mat(x,H).T @ G_mat(x,H)) @ G_mat(x,H).T @ (p_arr - est_p(x,H) + init_x[-1] - x[-1])
            x = x + delta_xb.flatten()
            counter += 1
        
        if (np.abs(x - init_x) > 1e-8).all():
            init_x = x
            
        else:
            init_x = x
            break
    
    return init_x

def est_pIF(prange_arr,f1,f2):
    
    g_mat = np.array([[1,1],
                      [1,(f1**2)/(f2**2)]])
    
    pIF = la.inv(g_mat.T @ g_mat) @ g_mat.T @ prange_arr
    
    return pIF

def dualF_eq(f_arr,f1,f2):
    
    g_mat = np.array([[1,1,0,0],
                      [1,(f1**2)/(f2**2),0,0],
                      [1,-1,1,0],
                      [1,-(f1**2)/(f2**2),0,1]])
    
    pIF = la.inv(g_mat.T @ g_mat) @ g_mat.T @ f_arr
    
    return pIF

    
def calc_cp_pos(rcvr_time,nav,group,x0,N1_dict,N2_dict,N1_list,N2_list,count):
    init_x = x0
    
    print(f"Epoch: {rcvr_time}")
    
    while True:
        H = np.empty((0,3))
        p_arr = np.empty((0,1))
        group = group.dropna(subset=['C1C','C2W','L1C','L2W'])
        
        for sv in group.SV.unique():
            group_sub = group[group.SV == sv]
            
            pseudorange = group_sub.C1C
            p = pseudorange.values[:,np.newaxis]
            
            ### Carrier Phases Measurements
            carrier1 = group_sub.L1C
            cp1 = carrier1.values[:,np.newaxis]
            
            carrier2 = group_sub.L2W
            cp2 = carrier2.values[:,np.newaxis]
            
            NL12 = cp1 - cp2 - (p_narrow / n_12)
            
            N1 = np.around((((l2/l1)-1)**-1) * ( ((l2/l1)*NL12) - cp1 + ((l2/l1)*cp2)) ).astype(int)
            N2 = np.around(N1 - NL12).astype(int)
            
            N1_dict[sv] = N1[0]
            N2_dict[sv] = N2[0]
            
            if count <= 600:
                pass
            else:
                sv_index = list(N1_dict.keys()).index(sv)
                # N1 = np.around(np.mean(N1_list,axis=0)).astype(int)[sv_index]
                # N2 = np.around(np.mean(N2_list,axis=0)).astype(int)[sv_index]
                N1 = np.mean(N1_list[-200:],axis=0)[sv_index]
                N2 = np.mean(N2_list[-200:],axis=0)[sv_index]
            
            cp11 = (cp1 - N1)*l1 + (calcSatBias(rcvr_time,nav,sv)*c) - init_x[-1]
            cp22 = (cp2 - N2)*l2 + (calcSatBias(rcvr_time,nav,sv)*c) - init_x[-1]
            
            iono_l1 = ((f2**2)/(f1**2 - f2**2)) * ((cp11-(N1*l1)) - (cp22-(N2*l2))) ### ALready
            
            cp = cp11 - iono_l1
            # cp = cp22 - ((f1**2/f2**2)*iono_l1)
            
            # cp = ((((f1**2) / ((f1**2) - (f2**2))) * cp11) - (((f2**2) / ((f1**2) - (f2**2))) * cp22)) - (N1 * l1)
            
            p = p + (calcSatBias(rcvr_time,nav,sv)*c) - init_x[-1] + iono_l1
            sat_pos = calcSatPos(rcvr_time, p[0], nav, sv)
            sat_pos = rot_satpos(sat_pos,p)
            
            if count == 0:
                H = np.vstack((H,sat_pos.T))    
                p_arr = np.append(p_arr,cp,axis=0)
            
            else:
                azimuth, elevation = calc_az_el(ecef2enu(np.array(init_x[:-1])[np.newaxis,:],sat_pos.T))
                
                if elevation < 5.:
                    continue
                else:
                    H = np.vstack((H,sat_pos.T))    
                    p_arr = np.append(p_arr,cp,axis=0)
        
        if len(H) < 4:
            raise Exception("Less than 4 satellites in view")
        else:
            pass
        
        x = init_x
        delta_xb = la.inv(G_mat(x,H).T @ G_mat(x,H)) @ G_mat(x,H).T @ (p_arr - est_p(x,H) + init_x[-1] - x[-1])
        x = x + delta_xb.flatten()
        
        counter = 0
        while ((np.abs(delta_xb) > 1e-3).all()) & (counter <= 100):
            delta_xb = la.inv(G_mat(x,H).T @ G_mat(x,H)) @ G_mat(x,H).T @ (p_arr - est_p(x,H) + init_x[-1] - x[-1])
            x = x + delta_xb.flatten()
            counter += 1
        
        if (np.abs(x - init_x) > 1e-8).all():
            init_x = x
            
        else:
            init_x = x
            break
    
    return init_x


"""
for rcrv_time, group in sample:
    print(f"Epoch: {rcvr_time}")
    
    sv = group[group['SV'] == 'G02']
    cp = sv.L1C
    pr = sv.C1C
    
    NL1 = cp - (pr * (f1*1e6/c))
    print(f"NL1: {NL1.values}")
    time.sleep(1)

#Wide Lane measurements
for rcrv_time, group in sample:
    print(f"Epoch: {rcvr_time}")

    l_12 = c/((f1-f2) * 1e6)
    sv = group[group['SV'] == 'G02']
    cp1 = sv.L1C
    cp2 = sv.L2W
    pr = sv.C1C

    NL12 = cp1 - cp2 - (pr / l_12)
    print(f"NL12: {NL12.values}")
    time.sleep(1)
    
#Narrow Lane measurements
for rcrv_time, group in sample:
    print(f"Epoch: {rcvr_time}")

    l_12 = c/((f1+f2) * 1e6)
    sv = group[group['SV'] == 'G02']
    cp1 = sv.L1C
    cp2 = sv.L2W
    pr = sv.C1C

    NL12 = cp1 + cp2 - (pr / l_12)
    print(f"NL12: {NL12.values}")
    time.sleep(1)

#Wide Lane measurements 2
N1_list, N2_list, NL12_list = [], [], []
for rcrv_time, group in sample:
    print(f"Epoch: {rcvr_time}")
    
    l_12 = c/((f1-f2) * 1e6)
    group_sub = group[group['SV'] == 'G02']
    cp1 = group_sub.L1C.values
    cp2 = group_sub.L2W.values
    pr = group_sub.C1C.values
    
    NL12 = cp1 - cp2 - (pr / l_12)
    N1 = ((l2/l1)**-1) * ( (l2/l1)*NL12 - cp1 + (l2/l1)*cp2)
    N2 = N1 - NL12
    
    cp11 = (cp1 - N1)*l1
    cp21 = (cp2 - N2)*l2
    print(f"N1: {N1}")
    print(f"N2: {N2}")
    print(f"NL12: {NL12}")
    print(f"cp1: {cp11}\n")
    
    N1_list.append(N1[0])
    N2_list.append(N2[0])
    NL12_list.append(NL12[0])
    time.sleep(1)

"""


gps_date_start = datetime(1980,1,6)
f1 = 1575.42 #MHz
f2 = 1227.6 #MHz
f5 = 1176. #MHz

l1 = c / (f1 * 1e6) ###L1 wavelength
l2 = c / (f2 * 1e6) ###L2 wavelength
l5 = c / (f5 * 1e6) ###L5 wavelength
l_12 = c/((f1-f2) * 1e6) ###Wide Lane Combination wavelength
n_12 = c/((f1+f2) * 1e6)


###Molave
# Laptop
# obs = gr.load(r'C:/Users/ASTI/Desktop/GNSS/UP data/Molave/IGS000USA_R_20193020215_00M_01S_MO.rnx',use="G").to_dataframe().reset_index(drop=False)
# nav = gr.load(r'C:/Users/ASTI/Desktop/GNSS/UP data/Molave/IGS000USA_R_20193020215_00M_01S_MN.rnx',use="G")

# PC
# obs = gr.load(r'D:/Cholo/UP/5th Year - 1st Sem - BS Geodetic Engineering/GE 155.1/GNSS/Day 1/Molave/Molave/IGS000USA_R_20193020215_00M_01S_MO.rnx',use="G").to_dataframe().reset_index(drop=False)
# nav = gr.load(r'D:/Cholo/UP/5th Year - 1st Sem - BS Geodetic Engineering/GE 155.1/GNSS/Day 1/Molave/Molave/IGS000USA_R_20193020215_00M_01S_MN.rnx',use="G")

###Freshie Walk
# obs = gr.load(r'C:/Users/ASTI/Desktop/GNSS/UP data/Freshie/IGS000USA_R_20193010216_24H_15S_MO.rnx',use="G").to_dataframe().reset_index(drop=False)
# nav = gr.load(r'C:/Users/ASTI/Desktop/GNSS/UP data/Freshie/IGS000USA_R_20193010216_24H_15S_MN.rnx',use="G")

# PC
# obs = gr.load(r'D:/Cholo/UP/5th Year - 1st Sem - BS Geodetic Engineering/GE 155.1/GNSS/Day 4/Freshie_Walk_Day4/IGS000USA_R_20193240054_00M_01S_MO.rnx',use="G").to_dataframe().reset_index(drop=False)
# nav = gr.load(r'D:/Cholo/UP/5th Year - 1st Sem - BS Geodetic Engineering/GE 155.1/GNSS/Day 4/Freshie_Walk_Day4/IGS000USA_R_20193240054_00M_01S_MN.rnx',use="G")

###CMC Hill
# Laptop
# obs = gr.load(r'C:/Users/ASTI/Desktop/GNSS/UP data/CMC_Hill/IGS000USA_R_20193250055_00M_01S_MO.rnx',use="G").to_dataframe().reset_index(drop=False)
# nav = gr.load(r'C:/Users/ASTI/Desktop/GNSS/UP data/CMC_Hill/IGS000USA_R_20193250055_00M_01S_MN.rnx',use="G")

# PC
obs = gr.load(r'D:/Cholo/UP/5th Year - 1st Sem - BS Geodetic Engineering/GE 155.1/GNSS/Day 4/CMC_Hill_Day4/IGS000USA_R_20193250055_00M_01S_MO.rnx',use="G").to_dataframe().reset_index(drop=False)
nav = gr.load(r'D:/Cholo/UP/5th Year - 1st Sem - BS Geodetic Engineering/GE 155.1/GNSS/Day 4/CMC_Hill_Day4/IGS000USA_R_20193250055_00M_01S_MN.rnx',use="G")

###PTAG IGS
# obs = gr.load(r'C:/Users/ASTI/Desktop/GNSS/PTAG00PHL_R_20230180100_01H_30S_MO.crx',use="G").to_dataframe().reset_index(drop=False)
# nav = gr.load(r'C:/Users/ASTI/Desktop/GNSS/PTAG00PHL_R_20230180000_01H_GN.rnx',use="G")

try:
    iono_corr = nav.ionospheric_corr_GPS
except:
    pass
nav = nav.to_dataframe().reset_index(drop=False)

obs_columns = obs.columns.tolist()
obs_columns[:2] = ['SV','epoch']
obs.columns = obs_columns

days_epoch = (((obs.epoch - timedelta(hours=8)).values.astype(np.int64) // 10 ** 9) - datetime.timestamp(gps_date_start)) / (3600*24)
GPS_week = days_epoch//7
time_week = (days_epoch/7  % 1) * (3600*24*7)
obs['GPS_week'] = GPS_week
obs['time_week'] = time_week



nav.columns = ['epoch','SV','af0','af1','af2','iode','crs','dn','m0','cuc','e','cus','sqrta','toe','cic','omg0',
               'cis','i0','crc','omega','odot','idot','CodesL2','GPSWeek','L2Pflag','SVacc','health','TGD','IODC','toc']
nav = nav[['epoch','SV','toc','toe','af0','af1','af2','e','sqrta','dn','m0',
                'omega','omg0','i0','odot','idot','cus','cuc','cis','cic','crs','crc','TGD','IODC']]

### Molave Ref
# ref = ell2cart(np.array([14.6575984,121.0673426,116.7935])).T

### Freshie Walk Ref
# ref = ell2cart(np.array([14.653947053,121.068636975,110.])).T

### CMC Hill Ref
ref = ell2cart(np.array([14.65530195,121.0638391,104.4737])).T

### PTAG Ref
# ref = np.array([-3184320.9618,5291067.5908,1590413.9800])[np.newaxis,:]

#initial position estimate
init_x = np.array([0,0,0,0])

start = time.time()
count = 0

sample = obs.groupby(time_week)

pos_list, time_list, e_list, n_list, u_list, b_list = [], [], [], [], [], []

sv_list = obs.SV.unique().tolist()
n0_list = [0 for sv in sv_list]

N1_dict, N2_dict = dict(map(lambda x,y: (x,y), sv_list,n0_list)), dict(map(lambda x,y: (x,y), sv_list,n0_list))
N1_list, N2_list = np.zeros(shape=(1,len(sv_list))), np.zeros(shape=(1,len(sv_list)))

for rcvr_time, group in sample:
    rcvr_time += init_x[-1]/c
    # init_x = calc_rcvr_pos(rcvr_time,nav,group,init_x, count)
    
    init_x = calc_cp_pos(rcvr_time, nav, group, init_x, N1_dict, N2_dict,N1_list, N2_list, count)
    N1_list = np.append(N1_list,np.array(list(N1_dict.values())).T,axis=0)
    N2_list = np.append(N2_list,np.array(list(N2_dict.values())).T,axis=0)
    
    lat, lon, height = cart2ell(init_x[:-1]).flatten()
    print(f"Latitude: {lat}, Longitude: {lon}, Ellipsoidal Height: {height}")
    print(f"Receiver Clock Bias: {init_x[-1]/c} s\n")
    
    e, n, u = ecef2enu(ref,init_x[:3][np.newaxis,:]).flatten()
    b = init_x[-1]/c
    
    pos_list.append([lat,lon,height])
    time_list.append(rcvr_time)
    e_list.append(e)
    n_list.append(n)
    u_list.append(u)
    b_list.append(b)
    
    count += 1

end = time.time()
print(f"Runtime: {end-start} seconds")

time_list2 = np.array(time_list)
e_list2 = np.array(e_list)
n_list2 = np.array(n_list)
u_list2 = np.array(u_list)
b_list2 = np.array(b_list)

e_list2 = e_list2 - e_list2.mean()
n_list2 = n_list2 - n_list2.mean()
u_list2 = u_list2 - u_list2.mean()
b_list2 = b_list2 - b_list2.mean()

###plot satellite position during GNSS measurement
fig,ax = plt.subplots(figsize=(12,7),dpi=120)
sc = ax.scatter(x=e_list2,y=n_list2,
                c=time_list2,
                cmap='rainbow_r')

fig.colorbar(sc)
ax.set_xlim(np.min(e_list2),np.max(e_list2))
ax.set_ylim(np.min(n_list2),np.max(n_list2))
ax.set_title('GNSS Measurement')
plt.show()

###plot each component versus time 
fig,ax = plt.subplots(nrows=4,figsize=(12,18),dpi=120)
ax[0].scatter(x=time_list2,y=e_list2,c = 'black',label = 'Easting')
ax[0].set_title(f'Easting vs time, Mean: {e_list2.mean()} Standard Deviation: {e_list2.std()}')
ax[0].legend()


ax[1].scatter(x=time_list2,y=n_list2,c = 'red',label = 'Northing')
ax[1].set_title(f'Northing vs time, Mean: {n_list2.mean()} Standard Deviation: {n_list2.std()}')
ax[1].legend()


ax[2].scatter(x=time_list2,y=u_list2,c = 'blue',label = 'Up')
ax[2].set_title(f'Up vs time, Mean: {u_list2.mean()} Standard Deviation: {u_list2.std()}')
ax[2].legend()


ax[3].scatter(x=time_list2,y=b_list2,c = 'green',label = 'User Clock Bias')
ax[3].set_title(f'Receiver Clock Bias vs time, Mean: {b_list2.mean()} Standard Deviation: {b_list2.std()}')
ax[3].legend()
plt.show()