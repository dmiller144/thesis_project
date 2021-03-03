# -*- coding: utf-8 -*-
"""
Created on Thu Feb 11 16:05:09 2021
Tank Emergency Volume calculator
@author: dmi002
"""

import wntr
import pandas as pd
import math
import matplotlib.pyplot as plt
import numpy as np

# Load model
INP_file_name = 'Dili_RHS' # input('Enter the filename of the network you wish to process: ')
inp_file = f'C:/Users/dmi002/Desktop/Python WIP/thesis_project/{INP_file_name}.inp'
wn = wntr.network.WaterNetworkModel(inp_file)

# Calculating required balancing tank volume
demand = wntr.metrics.hydraulic.expected_demand(wn, end_time=23*3600).sum(axis=1)
avg_flow = demand.mean()
daily_demand = demand.sum() * wn.options.time.hydraulic_timestep
cumulative = (avg_flow - demand).cumsum()
tank_volume = (cumulative.max() + abs(cumulative.min())) * wn.options.time.hydraulic_timestep

max_pumped_flow = 1.15 * avg_flow

power_outage = int(input("Add power outage duration in hours: "))

demand_wk = wntr.metrics.hydraulic.expected_demand(wn, end_time=168*3600).sum(axis=1)
tank_df = pd.DataFrame(demand_wk) ; tank_df.columns = ['Demand']
tank_df['Pumped_Flow'] = avg_flow
tank_df.reset_index(level=0, inplace=True)

power_outage_start_times = list()
tank_emerg_vols = list()
    
for i in range(25):
    tank_df['Pumped_Flow'] = avg_flow
    tank_df.loc[i:(i+power_outage-1), 'Pumped_Flow'] = 0
    
    for j in range(i+power_outage,len(tank_df)):
        if tank_df.loc[j-24: j, 'Pumped_Flow'].sum() * wn.options.time.hydraulic_timestep < daily_demand:
            tank_df.loc[j, 'Pumped_Flow'] = max_pumped_flow
        else:
            tank_df.loc[j, 'Pumped_Flow'] = avg_flow
    
    tank_df['In_-_Out'] = (tank_df['Pumped_Flow'] - tank_df['Demand']) * wn.options.time.hydraulic_timestep
    tank_df['Cumulative_Sum'] = tank_df['In_-_Out'].cumsum()
    tank_emerg_vol = (tank_df.loc[:,'Cumulative_Sum'].max() + abs(tank_df.loc[:, 'Cumulative_Sum'].min())) - tank_volume
    tank_df['Power Outage Start: %d'%i] = abs(tank_df.loc[:, 'Cumulative_Sum'].min())
    
    for k in range(1, len(tank_df)):
        tank_df.loc[k, 'Power Outage Start: %d'%i] = tank_df.loc[k-1, 'Power Outage Start: %d'%i] + tank_df.loc[k-1, 'In_-_Out']
    
    power_outage_start_times.append(i)
    tank_emerg_vols.append(tank_emerg_vol)

results = pd.DataFrame({'Power_Out_Start:': power_outage_start_times, 'Tank_Emerg_Vol': tank_emerg_vols})

print(f'For power outage of {power_outage}hrs: ')
print(f'Worst Time: {results.Tank_Emerg_Vol.idxmax()}hrs')
print(f'Requiring Emergency Storage Volume: {results.Tank_Emerg_Vol.max():,.2f}m3')
print(f'Balancing Volume: {tank_volume:,.2f}m3')
results.to_clipboard()

# Plotting 4 responses:
tank_vols = tank_df.iloc[:, tank_df.columns.get_loc('Power Outage Start: 0'):]
tank_vols_simplified = tank_vols.iloc[0:48, [0, 9, 18, 24]]
plt.figure(0)
tank_vols_simplified.plot(legend=True)
# plt.title(f'Sample Tank Responses to {power_outage}h Power Outage')
plt.xlabel('Time step (h)')
plt.ylabel('Tank Volume (m3)')
x_ticks = np.arange(0, 49, 12) 
plt.xticks(x_ticks)
plt.ylim(0, 5000)
plt.legend(loc="upper right")
plt.show()

#Plotting worst case:
worst_case_response = tank_df.iloc[0:48, (results.Tank_Emerg_Vol.idxmax() + 5)]
plt.figure(1)
worst_case_response.plot(legend=True)
# plt.title(f'Worst Case Response to {power_outage}h Power Outage')
plt.xlabel('Time step (h)')
plt.ylabel('Tank Volume (m3)')
plt.ylim(0, 5000)
plt.xticks(x_ticks)
plt.show()






