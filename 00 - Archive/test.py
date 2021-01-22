# -*- coding: utf-8 -*-
"""
Created on Wed Jan 20 11:15:17 2021

@author: dmi002
"""

import wntr

INP_file_name = 'Dili_LHS_main' # input('Enter the filename of the network you wish to process: ')
inp_file = f'C:/Users/dmi002/Desktop/Python WIP/thesis_project/{INP_file_name}.inp'
wn = wntr.network.WaterNetworkModel(inp_file)

pipes = wn.pipe_name_list
junctions = wn.junction_name_list
valvues = wn.valve_name_list
pumps = wn.pump_name_list

