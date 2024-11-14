import os
import yaml
from abc import ABC, abstractmethod

class Impedance_config(ABC):
    
    def __init__(self, config:dict, config_impedance:dict, params_placeholder:dict, impedance_stressors:dict, year:int, 
        parent_dir:str, output_dir:str) -> None:
        super().__init__()
        self.config = config
        self.config_impedance = config_impedance
        self.params_placeholder = params_placeholder
        self.impedance_stressors = impedance_stressors
        self.year = year
        self.parent_dir = parent_dir
        self.output_dir = output_dir
        
       
       
    @abstractmethod
    def update_impedance_config(self, *args, **kwargs) -> tuple[dict,dict]:
        """Updates the impedance configuration file with stressors and default decay parameters.
        
        Returns:
            impedance_dictionaries (tuple): Tuple containing two dictionaries:
                - Impedance_stressors (dict) The dictionary of stressors, mapping stressor raster path to YAML alias.
                - Impedance_configuration (dict): The updated configuration file mapping stressors to default decay parameters.
        """
        ...