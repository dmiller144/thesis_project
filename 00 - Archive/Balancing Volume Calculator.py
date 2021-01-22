# -*- coding: utf-8 -*-
"""
Created on Mon Dec 21 13:54:18 2020
This code returns the required balancing volume for a network. 
@author: dmi002
"""

import wntr
# Global inputs

min_p_req = 20
energy_price = 0.15 # €/kWh

# Load model
INP_file_name = 'DAWITOWN_base2' # input('Enter the filename of the network you wish to process: ')
inp_file = f'C:/Users/dmi002/Desktop/Python WIP/{INP_file_name}.inp'
wn = wntr.network.WaterNetworkModel(inp_file)

# Setting global energy options
wn.options.energy.global_efficiency = 75.0
wn.options.energy.global_price = energy_price/(3.6*10**6) #converting €0.15 per kWh into € per joules 

reservoirs = wn.reservoir_name_list
junctions = wn.junction_name_list

# Running Sim
sim = wntr.sim.EpanetSimulator(wn)
results = sim.run_sim()

# Calculating required balancing tank volume
avg_flow = results.node['demand'].loc[0:23*3600, reservoirs].sum().sum()/-24
demand = results.node['demand'].loc[0:23*3600, reservoirs].sum(axis=1)*-1
cumulative = (avg_flow - demand).cumsum()
tank_volume = (cumulative.max() + abs(cumulative.min()))*3600
print('Balancing Tank Volume:', round(tank_volume, 2), 'm3')



