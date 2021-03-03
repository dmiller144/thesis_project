# -*- coding: utf-8 -*-
"""
Created on Fri Jan 22 14:41:40 2021

This script uses NSGA-II to optimise the pipe diameters of a small network with a lowest annual cost objective.

It has a single constraint: Network Minimum Pressure > Minimum Required Pressure
@author: dmi002
"""

from platypus import Problem, NSGAII, Integer, nondominated
import wntr
import pandas as pd
from cust_wntr_funcs import total_annual_expenditure_func, min_p_func
import time

start_time = time.time()

# Load model
inp_file = 'Dili_upper_left tank_con_node J38.inp'
wn = wntr.network.WaterNetworkModel(inp_file)

print("GA optimisation in process…")
#Available Diameters
available_diameters = [63.0, 75.0, 90.0, 110.0, 125.0, 140.0, 160.0, 200.0, 225.0,
                       250.0, 315.0, 355.0, 400.0, 450.0, 500.0, 600.0, 700.0, 800.0]

# Minimum pressure requirement
min_p_req = 20

#Collecting info about network
pipes = wn.pipe_name_list

    
def Min_Cost_GA(x):
    
    indexers = {"indexer_%d"%idx: val for idx, val in enumerate(x)}
    
    for idx, pipe in enumerate(pipes):
        wn.get_link(pipe).diameter = available_diameters[indexers["indexer_%d"%idx]]/1000
    
    min_p = min_p_func(wn)
    total_annual_expenditure = total_annual_expenditure_func(wn)
        
    return    [total_annual_expenditure], [min_p - min_p_req]

problem = Problem(len(pipes), 1 , 1) # (Decisions variables, objectives, constraints)
problem.types[:] = Integer(0, len(available_diameters)-1)
problem.constraints[:] = ">=0"
problem.function = Min_Cost_GA
problem.directions[0] = Problem.MINIMIZE
algorithm = NSGAII(problem, population_size=100)
algorithm.run(10000)  

end_time = time.time()

# Results
non_dominated_soln = nondominated(algorithm.result)

diameters_result = [available_diameters[indexer] for indexer in
[problem.types[0].decode(binary_result) for binary_result in non_dominated_soln[0].variables]]

network_cost_result = non_dominated_soln[0].objectives[0]

min_p_result = non_dominated_soln[0].constraints[0] + min_p_req

print('The Nondominated Solution has the following decision variables:')
for pipe, diameter in enumerate(diameters_result):
    print(f'Pipe {pipe} diameter = {diameter}mm')
print(f'\nThe total annual expenditure for this network configuration is ${network_cost_result:,.2f}')
print(f'The Minimum Pressure in the network is: {min_p_result:.2f}mwc')
print(f'\nExecution time = {(end_time - start_time)/60:.2f} minutes')

# Creating the Optimised network
for idx, pipe in enumerate(pipes):
    wn.get_link(pipe).diameter = diameters_result[idx]/1000

wn.write_inpfile('Optimised_network.inp', version=2.2)

#%%
# This code exports the final population to the clipboard for further inspection in MS excel 
results_dict = {f'Pipe_{pipe}_diameters': [available_diameters[indexer] for indexer in 
                [problem.types[0].decode(binary_result) for binary_result in 
                [solution.variables[idx] for solution in algorithm.result]]] for idx, pipe in enumerate(pipes)}

results_dict['objectives'] = [solution.objectives[0] for solution in algorithm.result]
results_dict['constraints'] = [solution.constraints[0] for solution in algorithm.result]

results_df = pd.DataFrame.from_dict(results_dict)
results_df.to_clipboard()





