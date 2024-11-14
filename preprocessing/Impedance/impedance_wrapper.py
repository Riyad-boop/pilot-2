import os
import warnings
from osgeo import gdal

#local imports
from Impedance.impedance_config_processor import Impedance_config_processor
from Impedance.impedance_processor import Impedance_processor
from utils import load_yaml, save_yaml, find_stressor_params, get_max_from_tif

class ImpedanceWrapper():
    """
    This class is a wrapper for the Impedance processor.
    It abstracts the pipeline process of populating the impedance configuration file, processing the stressors, and calculating the impedance. 
    """
    def __init__(self,
        types: str = None,
        decline_type: str = 'exp_decline', # 'exp_decline' or 'prop_decline'
        lambda_decay: float = 500,
        k_value: float = 500,
        config_path:str="config.yaml", 
        config_impedance_path:str="config_impedance.yaml"
    ):
        
        # Load the configuration files
        self.config = load_yaml(config_path)
        self.config_impedance_path = config_impedance_path
        self.config_impedance = load_yaml(self.config_impedance_path)
        
        # Define the dictionary template for the configuration YAML file (for each stressor). We are using variables defined above.
        self.params_placeholder = {
            'types': types, # specify whether category of stressors has particular types different in parameters (for example, primary and secondary roads)
            'decline_type': decline_type,  # user will choose from 'exp_decline' and 'prop_decline'
            'exp_decline': {
                'lambda_decay': lambda_decay  # placeholder for exponential decay value
            },
            'prop_decline': {
                'k_value': k_value  # placeholder for proportional decline value
            }
        }
        
        # process all years
        self.years = self.config.get('year', None)
        if self.years is None:
            warnings.warn("Year variable is null or not found in the configuration file.")
            self.years = []
        elif isinstance(self.years, int):
            self.years = [self.years]
        else:
            # cast to list
            self.years = [int(year) for year in self.years]


        # to be passed into other classes
        self.parent_dir = os.path.normpath(os.getcwd())
        self.output_dir = self.config.get('output_dir') # get the output directory
        self.impedance_dir = self.config.get('impedance_dir') # get the directory for impedance rasters
        

    def validate_impedance_config(self, impedance_stressors:dict):
        validation_config = load_yaml(self.config_impedance_path)
        error_flag = False
        for yaml_stressor in impedance_stressors.keys():
            # use params_placeholder to validate if each stressor has all the required parameters and datatypes
            stressor_params = find_stressor_params(validation_config, yaml_stressor,)

            for key, value in stressor_params.items():        
                if key not in self.params_placeholder:
                    warnings.warn(f"Parameter {key} not found in the placeholder. Please update the configuration file.")
                    error_flag = True
                elif not isinstance(value, type(self.params_placeholder[key])):
                    datatype = type(self.params_placeholder[key])
                    warnings.warn(f"Parameter {key} has a different datatype. Expected {datatype} but got {type(value)}.")
                    error_flag = True

            # check if all parameters are present
            if len(stressor_params) != len(self.params_placeholder):
                # check if all keys are present in the configuration file
                for key in self.params_placeholder.keys():
                    if key not in stressor_params:
                        warnings.warn(f"Parameter {key} is missing from the configuration file. Please update the configuration file.")
                        error_flag = True

            if error_flag:
                raise ValueError("Validation of the configuration file failed. Please update the configuration file.")

    def get_impedance_max_value(self):
        impedance_tif_template = self.config.get('impedance_tif')
        impedance_tif = impedance_tif_template.format(year=self.years[0]) # substitute year from the configuration file
        impedance_tif = os.path.normpath(os.path.join(self.parent_dir,self.impedance_dir,impedance_tif))
        
        if impedance_tif is not None:
            impedance_ds = gdal.Open(impedance_tif) # open raster impedance dataset
            impedance_max = get_max_from_tif(impedance_ds) # call function from above
            print (f"Impedance raster GeoTIFF dataset used is {impedance_tif}") # debug
            print (f"Maximum value of impedance dataset: {impedance_max}") # debug
        else:
            raise FileNotFoundError(f"Impedance raster GeoTIFF dataset '{impedance_tif}' is not found! Please check the configuration file.") # stop execution
        
        return impedance_ds, impedance_max
    
    def process_impedance_config(self):
        """
        Process the impedance configuration (initial setup + lulc & osm stressors)

        Returns:
            impedance_stressors (dict): dictionary for stressors, mapping stressor raster path to YAML alias
        """
        # initialize the dictionary for stressors, which contains mapping stressor raster path to YAML alias
        impedance_stressors = {} 

        icp = Impedance_config_processor(year=self.years[0], params_placeholder=self.params_placeholder, config=self.config, config_impedance=self.config_impedance)
        icp.setup_config_impedance()
        impedance_stressors, self.config_impedance = icp.process_stressors(self.parent_dir, self.output_dir)
        # save the updated configuration file
        save_yaml(self.config_impedance, self.config_impedance_path)

        return impedance_stressors
    

    def calculate_impedance(self, impedance_stressors:dict, impedance_ds, impedance_max):
        # initialise variables with outputs of the effects from all rasters
        max_result = None
        cumul_result = None
        driver = gdal.GetDriverByName('GTiff') # has already been defined above
        mem_driver = gdal.GetDriverByName('MEM')
        impedance_processor = None # initialize the impedance processor to use after the loop

        for yaml_stressor, stressor_raster in impedance_stressors.items():
            # read the raster
            print(f"Processing: {stressor_raster}") # debug
            print(f"Corresponding key in YAML configuration: {yaml_stressor}") # debug
            # open the input raster dataset
            impedance_processor = Impedance_processor(
                max_result=max_result,
                cumul_result=cumul_result,
                parent_dir=self.parent_dir,
                output_dir=self.output_dir,
                config_impedance=self.config_impedance,
                yaml_stressor=yaml_stressor,
                stressor_raster=stressor_raster,
                driver=driver,
                mem_driver=mem_driver,
                impedance_ds=impedance_ds,
                impedance_max=impedance_max)
            if impedance_processor.ds is None:
                print(f"Failed to open {stressor_raster}, skipping...")
                continue
            else:
                impedance_processor.handle_no_data()
                proximity_data = impedance_processor.compute_proximity()
                max_result = impedance_processor.calculate_edge_effect(proximity_data)
                # print(f"Maximum result: {max_result}") # debug
        
        # Once all stressors have been processed, update the impedance dataset with decay
        impedance_processor.update_impedance_with_decay()


# example usage
# if __name__ == "__main__":
#     # Check if stressor.yaml exists. It is required for the script to run
#     if not os.path.exists('stressors.yaml'):
#         raise FileNotFoundError("The stressors.yaml file is not found. Please add the file to the current directory.")
#     else:
#         print("Stressors file found.")
#         iw = ImpedanceWrapper( 
#             types = None,
#             decline_type = 'exp_decline', # 'exp_decline' or 'prop_decline'
#             lambda_decay = 500,
#             k_value = 500)
        
#         # 1. Process the impedance configuration (initial setup + lulc & osm stressors)
#         # e.g. impedance_stressors = {'primary': '/data/data/output/roads_primary_2018.tif'}
#         impedance_stressors = iw.process_impedance_config()
#         #2. Prompt user to update the configuration file #TODO add function to do this automatically
#         print("Please update the configuration file for impedance dataset:")

#         # 2.1. Or validate after manual update 
#         iw.validate_impedance_config(impedance_stressors)

#         # 3.  Get the maximum value of the impedance raster dataset
#         impedance_ds, impedance_max = iw.get_impedance_max_value()

#         #3.0 Calculate impedance
#         iw.calculate_impedance(impedance_stressors,impedance_ds,impedance_max)

#         # 4.0 delete impedance stressors.yaml
#         os.remove("stressors.yaml")
#         print("osm stressors temp file has been deleted")
