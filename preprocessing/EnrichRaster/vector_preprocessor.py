# auxiliary libraries
import subprocess
from subprocess import Popen, PIPE
import warnings
import os

# for appending scripts and functions
import sys

# local modules
from vector_proc import VectorTransform
from utils import extract_layer_names

class vector_preprocessor():
    """
    Preprocesses OSM vector data for rasterization, which includes reprojecting, fixing geometries 
    and buffering features in specified layers (roads and railways).
    """
    def __init__(self, config: dict, parent_dir:str, vector_dir:str, year:int, lulc_crs:int, lulc_is_cartesian:bool) -> None:
        """
        Initializes the vector data preprocessor. Extracts vector layer names and checks if the CRS of the vector data matches the LULC data.

        Args:
            config (dict): configuration file
            parent_dir (str): parent directory
            vector_dir (str): vector directory
            year (int): year of the data
            lulc_crs (int): LULC CRS
            lulc_is_cartesian (bool): whether the LULC data is in cartesian coordinates
        """
        self.config = config
        self.year = year
        self.crs = lulc_crs
        self.is_cartesian = lulc_is_cartesian
        self.vector_refine = self.load_auxillary_data(parent_dir, vector_dir, year)
        print(f"Path to the input vector dataset: {self.vector_refine}")
        self.vector_layer_names = self.check_vector_data(self.vector_refine, self.crs)
        # specify the output directory
        self.vector_railways_buffered = os.path.join(parent_dir,vector_dir, f"railways_{self.year}_buffered.gpkg")
        self.vector_roads_buffered = os.path.join(parent_dir,vector_dir, f"roads_{self.year}_buffered.gpkg")
    
    def load_auxillary_data(self,parent_dir:str, vector_dir:str, year:int) -> str:
        """
        Loads the auxiliary data (OSM or user-specified vector data) from the configuration file.

        Returns:
            str: filename of the auxiliary data
        """
        # specify input vector data
        osm_data_template = self.config.get('osm_data', None)
        vector_filename = None # define a new variable which will be equal either osm_data or user_vector (depending on the configuration file)
        if osm_data_template is not None:
            osm_data = osm_data_template.format(year=year)
            user_vector = None
            vector_filename = osm_data 
            print ("Input raster dataset will be enriched with OSM data.")
        else:
            warnings.warn("OSM data not found in the configuration file.") 
            user_vector_template = self.config.get('user_vector',None)
            if user_vector_template is not None:
                user_vector = user_vector_template.format(year=year)
                vector_filename = user_vector
                print ("Input raster dataset will be enriched with user-specified data.")
            else:
                raise ValueError("No valid input vector data found. Neither OSM data nor user specified data found in the configuration file.")
            
        # print the name of chosen vector file
        print(f"Using vector file to refine raster data: {vector_filename}")
        return os.path.normpath(os.path.join(parent_dir,vector_dir,vector_filename))
    

    def check_vector_data(self, vector_refine:str, crs:int):
        vector_layer_names = extract_layer_names(vector_refine) 
        print(f"Layers found in the input vector file: {vector_layer_names}")
        formatted_layers = ', '.join(vector_layer_names)  # join layer names with a comma and space for readability
        print(f"Please continue if the layers in the vector file listed below are correct \n: {formatted_layers}.")

        # define full path with vector input directory
        # split path on last occurence of '/' and take the first part
        filepath = os.sep.join(vector_refine.split(os.sep)[:-1])
        vector_refine_path = os.path.join(filepath)

        # check if crs matches input raster (lulc). If not, reproject the vector data
        Vt = VectorTransform(vector_refine_path)
        files_to_validate = Vt.reproject_vector(crs, overwrite=True)
        if len(files_to_validate) > 0:
            Vt.fix_geometries_in_gpkg(Vt.geom_valid(files_to_validate), overwrite=True)
        return vector_layer_names
    
    def buffer_features(self, layer:str, output_filepath:str, epsg:int=27700):
        """
        Buffer the features in the input vector layer. 
        If the instance is not in cartesian coordinates, a temporary transformation is used to apply the buffer in meters and then transform back to the original CRS.
        """
        if os.path.exists(output_filepath):
            os.remove(output_filepath)

        subquery = f"""
            CASE 
                WHEN "width" IS NULL OR CAST("width" AS REAL) IS NULL THEN 
                    CASE 
                        WHEN highway IN ('motorway', 'motorway_link', 'trunk', 'trunk_link') THEN 30/2
                        WHEN highway IN ('primary', 'primary_link', 'secondary', 'secondary_link') THEN 20/2 
                        ELSE 10/2 
                    END 
                ELSE CAST("width" AS REAL)/2 
            END
        """
        # if it is not in cartesian coordinates, transform the geometry to a temporary cartesian CRS for buffering and then back to the original CRS
        if self.is_cartesian == False:
            query = f"""
                ST_Transform(
                    ST_Buffer(
                        ST_Transform(geom, {epsg}),
                        {subquery}
                    ),
                    {self.crs}
                ) AS geometry,
                *
            """
        else:
            query = f""" ST_Buffer(geom, {subquery}) AS geometry, * """


        print(f"Buffering {layer} layer...")
        #NOTE only for roads and railways for now
        ogr2ogr_command = [
            'ogr2ogr',
            '-f', 'GPKG',
            output_filepath, # output file path
            self.vector_refine, # input file path (should be before the SQL statement)
            '-dialect', 'SQLite',
            '-sql', f"""
                SELECT
                {query}
                FROM {layer}; /* to specify layer of input file */
            """,
            '-nln', layer, # define layer in the output file
            '-nlt', 'POLYGON' # ensure the output is a polygon
        ]

        # execute ogr2ogr command
        try:
            result = subprocess.run(ogr2ogr_command, check=True, capture_output=True, text=True)
            print(f"Successfully buffered {layer} layer and saved to {output_filepath}.")
            if result.stderr:
                print(f"Warnings or errors:\n{result.stderr}")
        except subprocess.CalledProcessError as e:
            print(f"Error buffering roads: {e.stderr}")
        except Exception as e:
            print(f"Unexpected error: {str(e)}")