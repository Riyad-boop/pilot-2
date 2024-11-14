import os
import yaml
import warnings
import geopandas as gpd
import numpy as np
import copy
from typing import Optional, Iterator

from preprocessing.Impedance.lulc_impedance_processor import Lulc_impedance_processor
from preprocessing.Impedance.osm_impedance_processor import Osm_impedance_processor

class Impedance_config_processor(): 
    """
    This class is responsible for processing the configuration file for the impedance dataset for the lulc and osm stressors
    The lulc stressors are defined in the reclassification CSV file and the osm stressors are defined in the stressors.yaml file (from the 3rd notebook)
    """

    def __init__(self, year:int, params_placeholder:dict, config:dict, config_impedance:dict):
        """
        Initialize the Impedance class with the configuration file paths and other parameters.

        Args:
            year (int): The year for which the edge effect is calculated.
            params_placeholder (dict): The dictionary template for the configuration YAML file (for each stressor).
            config_path (str): The path to the main configuration file. Default is 'config.yaml'.
            config_impedance_path (str): The path to the impedance configuration file. Default is 'config_impedance.yaml'.
        
        Returns:
            None
        """
        # self.params_placeholder = params_placeholder 
        # self.impedance_stressors_dict = impedance_stressors_dict
        self.config = config
        self.params_placeholder = params_placeholder
        self.year = year
        self.config_impedance = config_impedance
        
        self.impedance_stressors = {} # initialize the dictionary for stressors, which contains mapping stressor raster path to YAML alias

        # TODO remove since it is called in wrapper
        # self.config_impedance = self.setup_config_impedance()
        # self.impedance_stressors = self.process_stressors()


    def setup_config_impedance(self) -> None:
        """
        Handle the initial setup of the configuration file for impedance
        """
        # ensure 'initial_lulc' exists and handle 'enabled' field logic (various cases)
        if self.config_impedance.get('initial_lulc', None) is None:
            # create 'initial_lulc' with 'enabled' set to 'false' if it doesn't exist or is None
            self.config_impedance['initial_lulc'] = {'enabled': 'false'}
        else:
            # if 'enabled' doesn't exist in 'initial_lulc', add it and set to 'false'
            if self.config_impedance['initial_lulc'].get('enabled', None) is None:
                self.config_impedance['initial_lulc']['enabled'] = 'false'

        #NOTE: FOR DEBUGGING
        print("Initial structure of the configuration file for impedance dataset:")
        print(yaml.dump(self.config_impedance, default_flow_style=False))
        print("-" * 40)

        return self.config_impedance
    
    def process_stressors(self, parent_dir:str, output_dir:str) -> dict:
        """
        Process the stressors for lulc and osm data
        """
        lip = Lulc_impedance_processor(self.config_impedance,self.config, self.params_placeholder, self.impedance_stressors, self.year, parent_dir, output_dir)
        self.impedance_stressors, self.config_impedance = lip.update_impedance_config()
        oip = Osm_impedance_processor(self.config_impedance, self.config, self.params_placeholder, self.impedance_stressors, self.year, parent_dir, output_dir)
        self.impedance_stressors, self.config_impedance = oip.update_impedance_config()

        return self.impedance_stressors, self.config_impedance