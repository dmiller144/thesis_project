# -*- coding: utf-8 -*-
"""
Created on Mon Jan 11 14:23:45 2021

Dili WDN analysis

@author: dmi002
"""

import wntr
import pandas as pd
import numpy as np
import math

# Pipe Cost Table for T/L
pipecost_dict = {"Pipe_Diameter\n(mm)": [63.0, 75.0, 90.0, 110.0, 125.0, 140.0, 160.0, 200.0, 225.0, 250.0, 315.0, 355.0, 400.0, 450.0, 500.0, 600.0, 700.0, 800.0],
           "Pipe_Material": ['PVC', 'PVC', 'PVC', 'PVC', 'PVC', 'PVC', 'PVC', 'PVC', 'PVC', 'PVC', 'PVC', 'PVC', 'Ductile Iron', 'Ductile Iron', 'Ductile Iron', 'Ductile Iron', 'Ductile Iron', 'Ductile Iron'],
           "Supply_and_Installed_Cost\n($ USD/m)": [14.0, 17.0, 21.0, 28.0, 34.0, 41.0, 52.0, 79.0, 100.0, 120.0, 190.0, 240.0, 253.0, 295.0, 348.0, 462.0, 590.0, 732.0]
           }
pipecost_df = pd.DataFrame.from_dict(pipecost_dict)

# Annual O&M as % of investment
OM_pipes = 0.5
OM_pumps = 2.0
OM_tanks = 0.8

# Euro to USD exchange rate
euro_usd_exchange_rate = 1.22

#Cost of Electricity 
energy_price = 0.42 # USD/kWh

# Import a water network model
inp_file = 'Dili_LHS_main_noPRVs tank_con_node R_TIBAR_2.inp' # Choose INP file
wn = wntr.network.WaterNetworkModel(inp_file) # Read the INP file into the memory (index wn)


# Setting global energy options
wn.options.energy.global_efficiency = 75.0
wn.options.energy.global_price = energy_price/(3.6*10**6) #converting € 0.15 per kWh into €  per joules 
wn.options.energy.global_pattern = None 

sim = wntr.sim.EpanetSimulator(wn)
results = sim.run_sim()
    
junctions = wn.junction_name_list
pipes = wn.pipe_name_list
tanks = wn.tank_name_list
reservoirs = wn.reservoir_name_list
valves = wn.valve_name_list
pumps = wn.pump_name_list 


# PIPES
pipe_diameters = [wn.get_link(pipe).diameter * 1000 for pipe in pipes]
pipe_lengths = [wn.get_link(pipe).length for pipe in pipes]
pipe_start_nodes = [wn.get_link(pipe).start_node_name for pipe in pipes]
pipe_end_nodes = [wn.get_link(pipe).end_node_name for pipe in pipes]

pipe_dict = {"Pipe_Name": pipes,
           "Pipe_Diameter\n(mm)": pipe_diameters,
           "Pipe_Length\n(m)": pipe_lengths,
           "Pipe_Start_Node": pipe_start_nodes,
           "Pipe_End_Node": pipe_end_nodes
           }

pipe_df = pd.DataFrame.from_dict(pipe_dict)
pipecost_df = pipecost_df.sort_values(by='Pipe_Diameter\n(mm)')
pipe_df = pipe_df.sort_values(by="Pipe_Diameter\n(mm)")
pipe_df = pd.merge_asof(pipe_df, pipecost_df, left_on="Pipe_Diameter\n(mm)", right_on="Pipe_Diameter\n(mm)", direction="nearest")
pipe_df['Total Cost\n($ USD)'] = pipe_df['Supply_and_Installed_Cost\n($ USD/m)'] * pipe_df['Pipe_Length\n(m)']
total_pipe_inv_cost = pipe_df["Total Cost\n($ USD)"].sum()
print('CAPEX Breakdown:')
print(f'Total Pipe Investment Cost: USD ${total_pipe_inv_cost:,.2f}')
# pipe_df.to_excel('pipe2.xlsx')

#PUMPS
pump_duty_heads = [wn.get_link(pump).get_head_curve_coefficients()[0] * 3/4 for pump in pumps]
pump_duty_flows = [wn.get_link(pump).get_design_flow() * 3600 for pump in pumps]
pump_inv_costs = [euro_usd_exchange_rate * 5000*((wn.get_link(pump).get_design_flow() * 1.8 * 3600)**0.8)  for pump in pumps]

pump_dict = {"Pump_Name": pumps,
           "Pump_Duty_Head\n(m)": pump_duty_heads,             
           "Pump_Duty_Flow\n(m3/h)": pump_duty_flows,
           "Pump_Investment_Cost\n($/pump)": pump_inv_costs
           }
pump_df = pd.DataFrame.from_dict(pump_dict)
total_pump_inv_cost = pump_df["Pump_Investment_Cost\n($/pump)"].sum()
print(f'Total Pump Investment Cost: USD ${total_pump_inv_cost:,.2f}')

#VALVES
valve_types = [wn.get_link(valve).valve_type for valve in valves] 
valve_diameters = [wn.get_link(valve).diameter * 1000 for valve in valves]
valve_statuses = [str(wn.get_link(valve).initial_status) for valve in valves]
valve_inv_costs = [euro_usd_exchange_rate * (1000.0 + 30* (wn.get_link(valve).diameter * 1000)) for valve in valves]


valve_dict = {"Valve_Name": valves,
             "Valve_Type": valve_types,             
           "Valve_Diameter\n(mm)": valve_diameters,
           "Valve_Status": valve_statuses,
           "Valve_Investment_Cost\n($/valve)": valve_inv_costs
           }
valve_df = pd.DataFrame.from_dict(valve_dict)
total_valve_inv_cost = valve_df["Valve_Investment_Cost\n($/valve)"].sum()
print(f'Total Valve Investment Cost: USD ${total_valve_inv_cost:,.2f}')

#TANKS
tank_elevations = [wn.get_node(tank).elevation for tank in tanks]
tank_heights_above_ground = [18.09] # Manunal input required here
# tank = wn.tank_name_list[0]
# maxx = results.node['pressure'].loc[:, tank].min()
tank_volumes = [(math.pi/4 * wn.get_node(tank).diameter ** 2 *(results.node['pressure'].loc[:, tank].max() - results.node['pressure'].loc[:, tank].min())) for tank in tanks]
tank_inv_cost = (euro_usd_exchange_rate * (300_000 + 150 * np.array(tank_volumes) + 3*np.array(tank_heights_above_ground)*np.array(tank_volumes))).tolist()

tank_dict = {"Tank_Name": tanks,
           "Tank_Elevation": tank_elevations,             
           "Tank_Height_above_ground": tank_heights_above_ground,
           "Tank_Volume": tank_volumes,
           "Tank_Investment_Cost\n($/tank)": tank_inv_cost
           }
tank_df = pd.DataFrame.from_dict(tank_dict)
total_tank_inv_cost = tank_df["Tank_Investment_Cost\n($/tank)"].sum()
print(f'Total Tank Investment Cost: USD ${total_tank_inv_cost:,.2f}')

#TOTAL INVESTMENT COST
grand_total_inv_cost = total_pipe_inv_cost + total_pump_inv_cost + total_valve_inv_cost + total_tank_inv_cost
                  
print(f'Total Investment Cost USD ${grand_total_inv_cost:,.2f}\n')

#OPERATIONAL COST
# Energy Calculations
pump_flowrate = results.link['flowrate'].loc[:, wn.pump_name_list]
head = results.node['head']
pump_energy = wntr.metrics.pump_energy(pump_flowrate, head, wn)
pump_cost = wntr.metrics.pump_cost(pump_flowrate, head, wn)

pump_energy_total = pump_energy[0:24].sum()/1000*365
pump_cost_total = pump_cost[0:24].sum()*3600*365

annual_pump_energy = pump_energy[0:24].sum().sum()/1000*365
annual_pump_cost = pump_cost[0:24].sum().sum()*3600*365

print('OPEX Breakdown:')
print(f'Annual Energy Consumption: {annual_pump_energy:,.2f}')
print(f'Annual Energy Cost: USD $ {annual_pump_cost:,.2f}')

# OM Costs as percentage of CAPEX 
Total_OM = (total_pipe_inv_cost*OM_pipes + total_pump_inv_cost*OM_pumps + total_tank_inv_cost*OM_tanks)/100
print(f'Annual O&M Costs: USD $ {Total_OM:,.2f}')

# Loan conditions
Repay = 20.0 # years
Interest = 6.0 # annual interest rate on %

print('\nLoan Breakdown:')
print("Repayment period is", Repay, "years, at the annual interest rate of", Interest, "%")

Annuity = (Interest/100*(1+Interest/100)**Repay)/((1+Interest/100)**Repay-1)*grand_total_inv_cost

print (f"The total annual loan repayment is: USD ${Annuity:,.2f}") 




demand_df = results.node['demand'].iloc[0:24, :].sum()
demand_df.to_clipboard()

min_p = results.node['pressure'].loc[:, junctions].min().min()
min_pressures = results.node['pressure'].loc[:, junctions].min()
max_pressures = results.node['pressure'].loc[:, junctions].max()
max_pressures.to_clipboard()
print('Minimum Pressure:', round(min_p, 2), 'mwc','at time:', results.node['pressure'].loc[:, str(results.node['pressure'].loc[:, junctions].min().idxmin())].idxmin()/3600 ,
          'At node:', results.node['pressure'].loc[:, junctions].min().idxmin())


























