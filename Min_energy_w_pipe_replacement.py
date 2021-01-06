# -*- coding: utf-8 -*-
"""
Created on Mon Dec 21 13:54:18 2020
This code returns the pumping and storage configuration which has the lowest energy requirements for a given network.

Note: The network must have 1 pump, 1 reservoir and no pump scheduling controls. 
The network must ONLY include pipe diameters listed below. 
@author: dmi002
"""

import wntr
# import numpy as np
import pandas as pd
import math
import xlsxwriter
from openpyxl import Workbook
from openpyxl import load_workbook
import os

# Replacement pipe info:
pipe_diameters = [0.025, 0.05, 0.08, 0.1, 0.125, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6] # m
pipe_roughness = 0.5

# Costs Table for PE pipes per m
D_25 = 30.0 # Note I had to include this so the code could find it and index to the next size up.
D_50 = 45.0
D_80 = 72.0
D_100 = 90.0
D_125 = 110.0 # This had to be included as well. 
D_150 = 135.0
D_200 = 180.0
D_250 = 225.0
D_300 = 270.0
D_400 = 360.0
D_500 = 450.0
D_600 = 540.0

costs = [30.0, 45.0, 72.0, 90.0, 110.0, 135.0, 180.0, 225.0, 270.0, 360.0, 450.0, 540.0]
cost_table = {'Diameter': pipe_diameters, 'Cost': costs}
cost_df = pd.DataFrame.from_dict(cost_table)

# Global inputs

min_p_req = 20
max_headloss = 10 # m/km
energy_price = 0.15 # €/kWh

# Load model
INP_file_name = 'DAWITOWN_base' # input('Enter the filename of the network you wish to process: ')
inp_file = f'C:/Users/dmi002/Desktop/Python WIP/thesis_project/{INP_file_name}.inp'
wn = wntr.network.WaterNetworkModel(inp_file)

# Creating Directory for results and networks
os.makedirs(f'C:/Users/dmi002/Desktop/Python WIP/thesis_project/{INP_file_name}_results')
os.makedirs(f'C:/Users/dmi002/Desktop/Python WIP/thesis_project/{INP_file_name}_networks')

# Original Pipe diameters
pipe_info = {}
pipe_names = []
original_diameter = []
new_diameter = []
pipe_length = []
for pipe_name in wn.pipe_name_list:
    pipe_names.append(pipe_name)
    original_diameter.append(wn.get_link(pipe_name).diameter)
    pipe_length.append(wn.get_link(pipe_name).length)

tank_con_length = 1
tank_con_diameter = 1
pipe_names.append('tank_connection')
original_diameter.append(None)
pipe_length.append(tank_con_length)                  
pipe_info = {'Pipe_name': pipe_names,'Original_Diameter': original_diameter, 'Length': pipe_length}
pipe_df = pd.DataFrame.from_dict(pipe_info)

# Setting global energy options
wn.options.energy.global_efficiency = 75.0
wn.options.energy.global_price = energy_price/(3.6*10**6) #converting €0.15 per kWh into € per joules 
wn.options.energy.global_pattern = None 

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

# Establishing fixed tank parameters
tank_min_lvl = 2.0
tank_max_lvl = 6.0
tank_diameter = math.sqrt(4/math.pi*tank_volume/(tank_max_lvl - tank_min_lvl))
tank_init_lvl = (tank_max_lvl - tank_min_lvl)/2 + tank_min_lvl
tank_fin_lvl = tank_max_lvl

# Setting Duty_Flow to avg_flow
pump = wn.get_link(wn.pump_name_list[0])
pump_end_node = str(pump.end_node)
Duty_Head = pump.get_head_curve_coefficients()[0] * 3/4
Duty_Flow = avg_flow
curve = pump.pump_curve_name
wn.get_curve(curve).points = [(Duty_Flow, Duty_Head)]
sim = wntr.sim.EpanetSimulator(wn)
results = sim.run_sim()

min_p = results.node['pressure'].min().min()

# Adding pump variable speed pattern
multipliers = [1]
wn.add_pattern('VarSpeed', multipliers)

counter = 0

# Creating Workbook
wb = Workbook()
wb.active.title = "Summary"
wb.active['A1'] = 'Summary of results for tank connected to each node'
for j in junctions:
    ws = wb.create_sheet(j)
    ws.title = j
wb.save(f'{INP_file_name}_results/{INP_file_name}_results.xlsx')

# Creating Summary DataFrame
summary = {"Node": [],
              "Parameter": [],
              "Value": [],
              "Units": []
        }
summary_df = pd.DataFrame.from_dict(summary)

junction = ['a01', 'a02'] # This line replaces junctions for testing the code
for j in junctions:
    # Resetting Pipe diameters to original
    pipe_df.set_index('Pipe_name', inplace=True)
    for pipe_name in wn.pipe_name_list:
        # pipe_name = 'p03'
        pipe = wn.get_link(pipe_name)
        pipe.diameter = pipe_df['Original_Diameter'].loc[pipe_name]
    pipe_df = pipe_df.reset_index()
    
    # Adding Balancing Tank
    wn.add_tank('Balancing_tank', elevation=wn.get_node(j).elevation, init_level=tank_init_lvl, min_level=0, 
                max_level=10000, diameter=tank_diameter, coordinates=(wn.get_node(j).coordinates[0] + 30, wn.get_node(j).coordinates[1] + 30))
    wn.add_pipe('tank_connection', 'Balancing_tank', j, length=tank_con_length, diameter=tank_con_diameter, roughness=0.5)
    
    # Initialising parameters
    tank_init_lvl = (tank_max_lvl - tank_min_lvl)/2 + tank_min_lvl
    Duty_Head = pump.get_head_curve_coefficients()[0] * 3/4
    Duty_Flow = avg_flow
    curve = pump.pump_curve_name
    wn.get_curve(curve).points = [(Duty_Flow, Duty_Head)]
    multipliers = [1]
    
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()
    tank_fin_lvl = results.node['pressure'].loc[24*3600, 'Balancing_tank']
    min_p = results.node['pressure'].loc[:, junctions].min().min()
    min_pumped_flow = results.link['flowrate'].loc[:, wn.pump_name_list[0]].min()
    
    # Critical Pipes
    new_diameter.clear()
    df = results.link['headloss']
    min_p = results.node['pressure'].loc[:, junctions].min().min()
    critical_pipes_times = df[df > max_headloss].dropna(axis=1, how='all').dropna(how='all')
    critical_pipes = critical_pipes_times.columns.to_list()
    
    while len(critical_pipes) >= 1:
        for pipe_name in critical_pipes:
            # pipe_name = 'p03'
            pipe = wn.get_link(pipe_name)
            pipe.diameter = pipe_diameters[pipe_diameters.index(pipe.diameter)+1]
            # print(pipe_name, 'is now diameter:', pipe.diameter, 'm')    
            pipe.roughness = pipe_roughness  
        sim = wntr.sim.EpanetSimulator(wn)
        results = sim.run_sim()
        # Critical Pipes
        df = results.link['headloss']
        min_p = results.node['pressure'].loc[:, junctions].min().min()
        critical_pipes_times = df[df > max_headloss].dropna(axis=1, how='all').dropna(how='all')
        critical_pipes = critical_pipes_times.columns.to_list()
    
    # wn.write_inpfile(f'{INP_file_name} test tank_con_node {j}.inp', version=2.2)
    
    # This loop sets the pump head such that the min P in network equals the desired P
    while abs(min_p - min_p_req) > 0.1:
        while abs(min_p - min_p_req) > 0.1:
            
            # This loops ensures tank balancing
            while abs(tank_init_lvl - tank_fin_lvl) > 0.01:
                wn.get_node('Balancing_tank').init_level = tank_fin_lvl
                sim = wntr.sim.EpanetSimulator(wn)
                results = sim.run_sim()
                tank_fin_lvl = results.node['pressure'].loc[24*3600, 'Balancing_tank']
                tank_init_lvl = wn.get_node('Balancing_tank').init_level
            Duty_Head = Duty_Head + min_p_req - min_p + 0.1
            wn.get_curve(curve).points = [(Duty_Flow, Duty_Head)]
                    
            # the head has to be ablet to provide the avg flow at all times
            # print('Duty Head:', Duty_Head, 'tank_init_lvl:', tank_init_lvl)
            sim = wntr.sim.EpanetSimulator(wn)
            results = sim.run_sim()
            tank_fin_lvl = results.node['pressure'].loc[24*3600, 'Balancing_tank']
            tank_init_lvl = wn.get_node('Balancing_tank').init_level
            
            # This loops ensures tank balancing
            while abs(tank_init_lvl - tank_fin_lvl) > 0.01:
                wn.get_node('Balancing_tank').init_level = tank_fin_lvl
                sim = wntr.sim.EpanetSimulator(wn)
                results = sim.run_sim()
                tank_fin_lvl = results.node['pressure'].loc[24*3600, 'Balancing_tank']
                tank_init_lvl = wn.get_node('Balancing_tank').init_level
            min_p = results.node['pressure'].loc[:, junctions].min().min()
        
        pump_flows = results.link['flowrate'].loc[:, wn.pump_name_list[0]]*1000
        
        # This loop applies the flow balancing method is the standard deviation of the pump flows is greater than 1
        while pump_flows.std() > 1:
            """Start code to pump avg flow"""
            
            # Adding flow control valve to pump avg flow
            wn.add_junction('Dummy_node', elevation=wn.get_node(pump_end_node).elevation, coordinates=(wn.get_node(pump_end_node).coordinates[0]-30, wn.get_node(pump_end_node).coordinates[1]-30))
            wn.add_valve('Dummy_FCV','Dummy_node', pump_end_node, diameter=1, valve_type='FCV', minor_loss=0, setting=avg_flow)
            wn.remove_link(wn.pump_name_list[0])
            wn.add_pump('Pump', wn.reservoir_name_list[0], 'Dummy_node', pump_type='HEAD', pump_parameter=curve, speed=1.0, pattern='VarSpeed')
            
            sim = wntr.sim.EpanetSimulator(wn)
            results = sim.run_sim()
                
            # Setting Duty Head 500mwc above max pressure to ensure Qavg is maintained
            Duty_Head = results.node['pressure'].loc[:, pump_end_node].max()+500
            wn.get_curve(curve).points = [(Duty_Flow, Duty_Head)]
            
            sim = wntr.sim.EpanetSimulator(wn)
            results = sim.run_sim()
            
            # Range of Heads the pump sees
            pumped_head = results.node['pressure'].loc[:, pump_end_node]
            Duty_Head = pumped_head.mean()
            wn.get_curve(curve).points = [(Duty_Flow, Duty_Head)]
                
            #Creating pattern of pump speeds
            multipliers = (0.25+3*pumped_head.array/(4*(Duty_Head)))**0.5
            multipliers = multipliers[:-1]
            VarSpeed = wn.get_pattern('VarSpeed')
            VarSpeed.multipliers = multipliers
                
            # Removing FCV
            wn.remove_link('Pump')
            wn.remove_link('Dummy_FCV')
            wn.remove_node('Dummy_node')
            wn.add_pump('Pump', wn.reservoir_name_list[0], pump_end_node, pump_type='HEAD', pump_parameter=curve, speed=1.0, pattern='VarSpeed')
            
            """End code to pump avg flow"""
            
            sim = wntr.sim.EpanetSimulator(wn)
            results = sim.run_sim()
            pump_flows = results.link['flowrate'].loc[:, wn.pump_name_list[0]]*1000
            min_p = results.node['pressure'].loc[:, junctions].min().min()
                    
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()
    min_p = results.node['pressure'].loc[:, junctions].min().min()
    counter += 1 ; # print(counter) 
    
    # Adjusting tank elevation up
    wn.get_node('Balancing_tank').elevation = wn.get_node('Balancing_tank').elevation + results.node['pressure'].loc[:, 'Balancing_tank'].min() - tank_min_lvl
    wn.get_node('Balancing_tank').init_level = wn.get_node('Balancing_tank').init_level - results.node['pressure'].loc[:, 'Balancing_tank'].min() + tank_min_lvl
    tank_elev = wn.get_node('Balancing_tank').elevation
    tank_init_lvl = wn.get_node('Balancing_tank').init_level
    tank_height = tank_elev - wn.get_node(j).elevation
           
    # Energy Calculations
    pump_flowrate = results.link['flowrate'].loc[:, wn.pump_name_list]
    head = results.node['head']
    pump_energy = wntr.metrics.pump_energy(pump_flowrate, head, wn)
    pump_cost = wntr.metrics.pump_cost(pump_flowrate, head, wn)
       
    # Critical Pipes
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()
    df = results.link['headloss']
    min_p = results.node['pressure'].loc[:, junctions].min().min()
    critical_pipes_times = df[df > max_headloss].dropna(axis=1, how='all').dropna(how='all')
    critical_pipes = critical_pipes_times.columns.to_list()
    
    # Adding new pipe info and calculating replacement costs
    for pipe_name in wn.pipe_name_list:
        new_diameter.append(wn.get_link(pipe_name).diameter)
    
    pipe_df['New_Diameter'] = new_diameter
    pipe_df = pipe_df.merge(cost_df, left_on='New_Diameter', right_on='Diameter', how='left')
    pipe_df['Replacement_Cost'] = pipe_df['Length'] * pipe_df['Cost'].where(pipe_df['Original_Diameter'] != pipe_df['New_Diameter'])
    pipe_df = pipe_df.drop('Diameter', 1)
    pipe_df.set_index('Pipe_name', inplace=True)
    
    
    # Tank Cost calculation
    tank_inv_cost = 300_000 + 150 * tank_volume + 3 * tank_height * tank_volume
    
    # Pump Cost calculation
    pump_inv_cost = 5000 * ((pump.get_design_flow()*1.8*3600)**0.8)
    
    # Total Investment cost
    total_inv_cost = tank_inv_cost + pump_inv_cost + pipe_df['Replacement_Cost'].sum()
        
    # Outputs to console
    print('\nProgress:', counter, '/', len(junctions), 'Nodes Processed')
    print(f'Summary of pumping energy for tank connected to node {j}:')
    print('Pump Parameters: Duty Flow:', round(Duty_Flow*1000, 2),'L/s',  'Duty Head:', round(Duty_Head, 2), 'm', f'Pump Cost: €{round(pump_inv_cost,2):,}')
    print('Actual average pumped flow:', round(pump_flows.mean(), 2), 'L/s')
    print('Cost €', round(pump_cost[0:24].sum()[0]*3600, 2), 'per day')
    print('Energy:', f'{round(pump_energy[0:24].sum()[0]/1000, 2):,}', 'kWh/day')
    print('Minimum Pressure:', round(min_p, 2), 'mwc','at time:', results.node['pressure'].loc[:, str(results.node['pressure'].loc[:, junctions].min().idxmin())].idxmin()/3600 ,
          'At node:', results.node['pressure'].loc[:, junctions].min().idxmin())
    print('Tank Elevation:', round(tank_elev, 2), 'm', 'Tank Height above ground:', round(tank_height, 2), 'm', 'Tank Volume:', f'{round(tank_volume, 2):,}', 'm3', 'Tank Cost: €', f'{round(tank_inv_cost, 2):,}')
    print(f"Cost of replacing pipes over unit headloss threshold: €{pipe_df['Replacement_Cost'].sum():,}")
    print(pipe_df.dropna(subset=['Replacement_Cost']))
    print('Pipes which exceed headloss > 10m/km:', critical_pipes)
    print(f'Total Investment Cost for Pump, Replaced Pipes and Tank: €{round(total_inv_cost,2):,}')
    
    # Individual nodal outputs to Excel
    wb = load_workbook(filename = f'{INP_file_name}_results/{INP_file_name}_results.xlsx')
    writer = pd.ExcelWriter(f'{INP_file_name}_results/{INP_file_name}_results.xlsx', engine='openpyxl')
    writer.book = wb
    writer.sheets = dict((ws.title, ws) for ws in wb.worksheets)
        
    pipe_df_xl = pipe_df.dropna(subset=['Replacement_Cost'])
    pipe_df_xl.to_excel(writer, sheet_name=j, startrow=16)
    ws = wb[j]
        
    ws['A1'] = f'This sheet contains the results for tank connected to node: {j}'
    ws['A3'] = 'Pumping Parameters'
    ws['A4'] = 'Duty Head' ; ws['B4'] = round(Duty_Head, 2) ; ws['C4'] = 'm'
    ws['A5'] = 'Duty Flow' ; ws['B5'] = round(Duty_Flow*1000, 2) ; ws['C5'] = 'L/s'
    ws['A6'] = 'Actual average pumped flow:' ; ws['B6'] = round(pump_flows.mean(), 2) ; ws['C6'] = 'L/s'
    ws['A7'] = 'Cost:' ; ws['B7'] = f'€{pump_cost[0:24].sum()[0]*3600:,.2f}' ; ws['C7'] = 'Euro per day'
    ws['A8'] = 'Energy:' ; ws['B8'] = round(pump_energy[0:24].sum()[0]/1000, 2) ; ws['C8'] = 'kWh/day'
    
    ws['A10'] = 'Balancing Tank Parameters'
    ws['A11'] = 'Elevation' ; ws['B11'] = round(tank_elev, 2) ; ws['C11'] = 'm above sea level'
    ws['A12'] = 'Tank height above ground' ; ws['B12'] = round(tank_height, 2) ; ws['C12'] = 'm above nearest node'
    ws['A13'] = 'Tank volume' ; ws['B13'] = round(tank_volume, 2) ; ws['C13'] = 'm3'
    
    ws['E3'] = 'Network Critical Results'
    ws['E4'] = 'Minimum Pressure' ; ws['F4'] = round(min_p, 2) ; ws['G4'] = 'mwc'
    ws['E5'] = 'Critical Hour' ; ws['F5'] = results.node['pressure'].loc[:, str(results.node['pressure'].loc[:, junctions].min().idxmin())].idxmin()/3600 ; ws['G5'] = 'hrs'
    ws['E6'] = 'Critical Node' ; ws['F6'] = results.node['pressure'].loc[:, junctions].min().idxmin()
    ws['E7'] = 'Critical Pipes' ; ws['F7'] = str(critical_pipes) ; ws['G7'] = 'Unit headloss >10m/km'
    
    ws['E10'] = 'Investment Cost Summary'
    ws['E11'] = 'Pump Cost' ; ws['F11'] = f'€{pump_inv_cost:,.2f}'
    ws['E12'] = 'Tank Cost' ; ws['F12'] = f'€{tank_inv_cost:,.2f}'
    ws['E13'] = 'Total Pipe Replacement Cost' ; ws['F13'] = f"€{pipe_df['Replacement_Cost'].sum():,.2f}" 
    ws['E14'] = 'Total Investment Cost' ; ws['F14'] = f'€{total_inv_cost:,.2f}'
    
    ws['A16'] = 'Table of individual pipes to be replaced'
       
    wb.save(f'{INP_file_name}_results/{INP_file_name}_results.xlsx')
    
    # Summary page output to excel
    parameters = ['for', 'Duty Head', 'Duty Flow', 'Actual average pumped flow:', 'Cost:', 'Energy:', 'Tank Elevation', 
                  'Tank height above ground', 'Tank volume', 'Minimum Pressure', 'Critical Hour', 'Critical Node', 'Critical Pipes',
                  'Pump Cost', 'Tank Cost', 'Total Pipe Replacement Cost', 'Total Investment Cost', '---']
    
    values = ['node: ', round(Duty_Head,2), round(Duty_Flow*1000,2), round(pump_flows.mean(),2), f'€{pump_cost[0:24].sum()[0]*3600:,.2f}', 
              round(pump_energy[0:24].sum()[0]/1000,2), round(tank_elev,2), round(tank_height, 2), round(tank_volume, 2), round(min_p, 2),
              results.node['pressure'].loc[:, str(results.node['pressure'].loc[:, junctions].min().idxmin())].idxmin()/3600,
              results.node['pressure'].loc[:, junctions].min().idxmin(), str(critical_pipes), f'€{pump_inv_cost:,.2f}',
              f'€{tank_inv_cost:,.2f}', f"€{pipe_df['Replacement_Cost'].sum():,.2f}" , f'€{total_inv_cost:,.2f}', '---']
    
    units = [j, 'm', 'L/s', 'L/s', 'Europerday', 'kWh/day', 'm above sea level', 'm above nearest node', 'm3', 'mwc', 'hrs', 'Node',
             'Unit headloss >10m/km', 'Capital Investment', 'Capital Investment', 'Capital Investment', 'Grand Total', '---']
    
    node_summary = {"Node": ['Summary'] + [j]*16 + ['---'],
              "Parameter":  parameters,
              "Value":      values,
              "Units":      units
        }
    node_summary_df = pd.DataFrame.from_dict(node_summary)
    summary_df = summary_df.append(node_summary_df, ignore_index=True)
        
    # Write EPANET.inp file
    wn.write_inpfile(f'{INP_file_name}_networks/{INP_file_name} tank_con_node {j}.inp', version=2.2)
    
    # Resetting Pipe DataFrame
    pipe_df = pipe_df.drop(['New_Diameter', 'Cost', 'Replacement_Cost'], 1)
    pipe_df = pipe_df.reset_index()
    # print(pipe_df)
    
wb = load_workbook(filename = f'{INP_file_name}_results/{INP_file_name}_results.xlsx')
writer = pd.ExcelWriter(f'{INP_file_name}_results/{INP_file_name}_results.xlsx', engine='openpyxl')
writer.book = wb
writer.sheets = dict((ws.title, ws) for ws in wb.worksheets)

summary_df.to_excel(writer, sheet_name='Summary', startrow=3)
wb.save(f'{INP_file_name}_results/{INP_file_name}_results.xlsx')





    
    
    
    

    
    
    
    
    
    
    
    
    

