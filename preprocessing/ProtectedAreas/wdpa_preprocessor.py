# external imports
import os
import sys

# local imports
from ProtectedAreas.raster_country_code_processor import RasterCountryCodeProcessor
from ProtectedAreas.pa_processor_wrapper import PA_Processor_Wrapper
from ProtectedAreas.rasterizer_processor import Rasterizer_Processor
from ProtectedAreas.update_land_impedance import UpdateLandImpedance
from ProtectedAreas.landscape_affinity_estimator import Landscape_Affinity_Estimator
from ProtectedAreas.lulc_pa_raster_sum import Lulc_pa_raster_sum
from utils import load_yaml


class WDPA_Preprocessor(utils):

    def __init__(self, current_dir:str, parent_dir:str) -> None:
        super().__init__()
        self.current_dir = current_dir
        self.parent_dir = parent_dir
        self.config = load_yaml(os.path.join(parent_dir, 'config.yaml'))
      

    def sum_lulc_pa_rasters(self, lulc_path:str="lulc", lulc_with_null_path:str="lulc_temp", pa_path:str="pas_timeseries", lulc_upd_compr_path:str="lulc_pa") -> None:
        """
        Sum the LULC and PA raster data.

        Args:
            lulc_path (str): The path to the LULC raster data.
            lulc_with_null_path (str): The path to the LULC raster data with zeros.
            lulc_upd_compr_path (str): The path to the combined LULC and PA raster data.
            pa_path (str): The path to the PA raster data.
        
        Returns:
            None
        """
        lprs = Lulc_pa_raster_sum(lulc_path, lulc_with_null_path, pa_path, lulc_upd_compr_path)
        lprs.assign_no_data_values()
        lprs.combine_pa_lulc()
    
    def compute_affinity(self, impedance_dir:str='impedance_pa', affinity_dir:str='affinity') -> None:
        """
        Compute the affinity between the protected areas.

        Args:
            impedance_dir (str): The path to the directory containing the impedance raster data.
            affinity_dir (str): The path to the directory where the affinity data will be saved.

        Returns:
            None
        """
        lae = Landscape_Affinity_Estimator(impedance_dir, affinity_dir)
        lae.compute_affinity(os.listdir(impedance_dir))

    def reclassify_raster_with_impedance(self, input_dir:str='lulc_pa', output_folder:str='impedance_pa', reclass_table:str="reclassification.csv") -> None:
        """
        Reclassify the raster data with impedance values.

        Args:
            input_dir (str): The path to the input directory containing the raster data.
            output_folder (str): The path to the output directory where the reclassified raster data will be saved.
            reclass_table (str): The path to the reclassification table.
        
        Returns:
            None
        """
        UpdateLandImpedance(input_dir, output_folder, reclass_table)

    def rasterize_pas_by_year(self, merged_gpkg:str, lulc_dir:str, pa_timeseries_dir:str) -> None:
        """
        Rasterize the protected areas by year of establishment.

        Args:
            merged_gpkg (str): The path to the merged GeoPackage file.
            lulc_dir (str): The path to the directory containing the LULC raster data.
            pa_timeseries_dir (str): The path to the directory where the rasterized protected areas will be saved.
        
        Returns:
            None
        """
        rp = Rasterizer_Processor(merged_gpkg, lulc_dir, pa_timeseries_dir)
        rp.filter_pa_by_year()
        rp.rasterize_pas_by_year()

    def get_lulc_country_codes(self) -> dict:
        """
        Fetch the country codes for the LULC rasters

        Returns:
            dict: A dictionary of unique ISO3 country codes.
        """
        # initialize the RasterCountryCodeProcessor class
        lulc_ccp = RasterCountryCodeProcessor(self.config, self.current_dir)
        # fetch the unique country codes from input LULC raster data
        lulc_country_codes = set().union(*lulc_ccp.fetch_lulc_country_codes().values())

        return lulc_country_codes
    
    def protected_area_to_merged_geopackage(self, lulc_country_codes:dict, output_file:str ="merged_pa.gpkg", skip_fetch:bool=False) -> str:
        """
        For each unique country code, fetch and process the protected areas and merge them into a single GeoPackage file.
        API used fetches most up to date protected areas.

        Args:
            lulc_country_codes (dict): A dictionary of unique country codes.
            output_file (str): The name of the output GeoPackage file.
        
        Returns:
            str: The path to the merged GeoPackage file.
        """
        # initialize the PA_Processor_Wrapper class
        response_dir = "wdpa_data"
        os.makedirs(response_dir, exist_ok=True)
        # list to store the names of the GeoJSON files
        geojson_filepaths = []

        Pa_processor = PA_Processor_Wrapper(
            lulc_country_codes, 
            self.config['api_url'],
            self.config['token'],
            self.config['marine'],
            response_dir
        )
        if skip_fetch:
            geojson_filepaths = [os.path.join(response_dir, file) for file in os.listdir(response_dir)]
        else:
            Pa_processor.process_all_countries()
            geojson_filepaths = Pa_processor.save_all_country_geoJSON()

        # merge all the GeoJSON files into a single GeoPackage file
        gpkg = Pa_processor.merge_geojsons_to_geopackage(geojson_filepaths, output_file)
        # print(f"GeoPackage file created: {gpkg}")
        return gpkg

# example usage
# if __name__ == "__main__":
#     if os.getcwd().endswith("1_protected_areas") == False:
#         # NOTE working from docker container
#         os.chdir('./1_protected_areas')

#     # define own modules from the root directory (at level above)
#     # define current directory
#     current_dir = os.getcwd()
#     # define parent directory (level above)
#     parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
#     # add the parent directory to sys.path
#     sys.path.append(parent_dir)

#     wp = WDPA_Preprocessor(current_dir, parent_dir)

#     # STEP 1.0: Get the unique country codes from the LULC raster data
#     country_codes = wp.get_lulc_country_codes()
#     # STEP 2.0: Fetch and process the protected areas for the selected countries
#     print("Fetching protected areas for the selected countries")
#     #TODO change skip_fetch to False
#     merged_gpkg = wp.protected_area_to_merged_geopackage(country_codes, "merged_pa.gpkg", skip_fetch=True)

#     # STEP 3.0: Rasterize the merged GeoPackage file
#     print("Rasterizing the merged GeoPackage file")
#     wp.rasterize_pas_by_year(merged_gpkg, os.path.join(current_dir,"lulc"), os.path.join(current_dir, "pas_timeseries"))
    
#     # # STEP 4.0: Raster Calculation
#     print("Raster Calculation")
#     wp.sum_lulc_pa_rasters()
#     #TODO REMOVE BELOW FROM WP and deprecate from utils.py
#     # wp.run_shell_command(os.path.join(current_dir, "raster_sum_loop.sh"))

#     # # STEP 5.0: Reclassify input raster with impedance values
#     print("Reclassifying the raster with impedance values")
#     wp.reclassify_raster_with_impedance()

#     # # STEP 6: Compute affinity
#     print("Computing affinity")
#     wp.compute_affinity()

#     print("Preprocessing of protected areas completed.")