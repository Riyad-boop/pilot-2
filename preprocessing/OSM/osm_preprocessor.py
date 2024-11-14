import overpy
import json
import requests
import sys
import geopandas as gpd
import pandas as pd
import os
import tempfile
from shapely.geometry import Point, LineString, MultiLineString, Polygon, MultiPolygon
from osgeo import gdal, osr
import pyproj

# auxiliary libraries
import time
import warnings
import yaml
import subprocess

#Local imports
from utils import load_yaml

class Osm_PreProcessor():
    """
    A class to enrich raster data with OSM data
    """
    #TODO 20/09/2024  only do 1 year for now. Later, we can extend it to multiple years
    def __init__(self, config_path:str, output_dir:str) -> None:
        self.config = load_yaml(config_path)
        self.output_dir = output_dir

        # make output directory if it does not exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        ## read year (Specify the input raster data)
        self.years = self.config.get('year', None)
        if self.years is None:
            warnings.warn("Year variable is null or not found in the configuration file... \n Defaulting to 2022")
            self.years = [2022]
            self.date = f"{self.years}-12-31T23:59:59Z" # to fetch it as a last second of the year
        elif isinstance(self.years, int):
            # cast to list
            self.years = [self.years]
            self.date = f"{self.years}-12-31T23:59:59Z"
        else:
            # cast to list
            self.years = [int(year) for year in self.years]
            self.date = [f"{year}-12-31T23:59:59Z" for year in self.years]

        print(f"OSM data is to be retrieved for {self.years} years.")
        print ("-" * 30)

        # find directories from config file
        input_dir = self.config.get('input_dir')
        lulc_dir = self.config.get('lulc_dir')

        ## define the input raster dataset that should be enriched with OSM data
        lulc_template = self.config.get('lulc')

        # substitute the year into the lulc string from config file
        # lulcs = [lulc_template.format(year=year) for year in self.years]
        lulcs = {os.path.normpath(os.path.join(lulc_dir,lulc_template.format(year=year))):year for year in self.years}
        
        [print(f"Input rasters to be used for processing is {lulc}, {year}.") for lulc,year in lulcs.items()]
        print ("-" * 30)

        #NOTE: for now just work with one raster file
        #TODO: loop over all lulc files.
        lulc = list(lulcs.keys())[0]
        year = list(lulcs.values())[0]
        x_min_cart, x_max_cart, y_min_cart, y_max_cart, epsg_code = self.get_raster_properties(lulc)
        self.bbox = self.reproject_and_get_bbox(x_min_cart, x_max_cart, y_min_cart, y_max_cart, epsg_code)
        
        # to check the bounding box of input raster
        print(self.bbox)


    def reproject_and_get_bbox(self, x_min_cart:float, x_max_cart:float, y_min_cart:float, y_max_cart:float, epsg_code:int) -> tuple:

        ## Reproject the bounding box of input dataset as Overpass accepts only coordinates in geographical coordinates (WGS 84):
        # defining function to transform
        transform_cart_to_geog = pyproj.Transformer.from_crs(
            pyproj.CRS(f'EPSG:{epsg_code}'),  # applying EPSG code of input raster dataset
            pyproj.CRS('EPSG:4326')   # WGS84 geographic which should be used in OSM APIs
        )

        # running function
        x_min, y_min = transform_cart_to_geog.transform(x_min_cart, y_min_cart)
        x_max, y_max = transform_cart_to_geog.transform(x_max_cart, y_max_cart)

        # print the Cartesian coordinates before transformation
        print("Before Transformation:")
        print("x_min_cart:", x_min_cart)
        print("x_max_cart:", x_max_cart)
        print("y_min_cart:", y_min_cart)
        print("y_max_cart:", y_max_cart)

        # print the transformed geographical coordinates
        print("After Transformation:")
        print("x_min:", x_min)
        print("x_max:", x_max)
        print("y_min:", y_min)
        print("y_max:", y_max)
        bbox=f"{x_min},{y_min},{x_max},{y_max}"
        
        return bbox

    def get_raster_properties(self,lulc:any) -> tuple:
        """
        Get the properties of the raster file
        """
        ## Load the raster file, get its extent, cell size and projection:
        raster = gdal.Open(lulc)
        if raster is not None:
            inp_lyr = raster.GetRasterBand(1)  # get the first band
            x_min_cart, x_max_cart, y_min_cart, y_max_cart = raster.GetGeoTransform()[0], raster.GetGeoTransform()[0] + raster.RasterXSize * raster.GetGeoTransform()[1], raster.GetGeoTransform()[3] + raster.RasterYSize * raster.GetGeoTransform()[5], raster.GetGeoTransform()[3]
            '''
            cellsize = raster.GetGeoTransform()[1]  # Assuming the cell size is constant in both x and y directions
            x_ncells = int((x_max - x_min) / cellsize)
            y_ncells = int((y_max - y_min) / cellsize)
            '''
            print ("Input raster has been successfully found.")

            # extract projection system of input raster file
            info = gdal.Info(raster, format='json')
            if 'coordinateSystem' in info and 'wkt' in info['coordinateSystem']:
                srs = osr.SpatialReference(wkt=info['coordinateSystem']['wkt'])
                if srs.IsProjected():
                    epsg_code = srs.GetAttrValue("AUTHORITY", 1)
                    print(f"Projected coordinate system of the input raster is EPSG:{epsg_code}")
                else:
                    print("Input raster does not have a projected coordinate system.")
            else:
                print("No projection information found in the input raster.")
            # close the raster to keep memory empty
            raster = None
        else:
            print ("Input raster is missing.")

        return x_min_cart, x_max_cart, y_min_cart, y_max_cart, epsg_code



    def load_yaml(self, path:str) -> dict:
        """
        Load a yaml file from the given path to a dictionary

        Args:
            path (str): path to the yaml file

        Returns:
            dict: dictionary containing the yaml file content
        """
        with open(path , 'r') as file:
            return yaml.safe_load(file)
    

    def fetch_osm_data(self,queries:dict, year:int , overpass_url:str = "https://overpass-api.de/api/interpreter", ) -> list:
        intermediate_jsons = []

        # iterate over the queries and execute them
        for query_name, query in queries.items():
            response = requests.get(overpass_url, params={'data': query})
            print(response)
                
            # if response is successful
            if response.status_code == 200:
                print(f"Query to fetch OSM data for {query_name} in the {year} year has been successful.")
                data = response.json()
                
                # Extract elements from data
                elements = data.get('elements', [])
                
                # Print the number of elements
                print(f"Number of elements in {query_name} in the {year} year: {len(elements)}")
                
                # Print the first 3 elements to verify response
                for i, element in enumerate(elements[:3]):
                    print(f"Element {i+1}:")
                    print(json.dumps(element, indent=2))
                
                # Save the JSON data to a file
                output_file = os.path.join(self.output_dir, f"{query_name}_{year}.json")
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                print(f"Data has been saved to {output_file}")
                print ("-" * 30)

                # Add the output file name to the list
                intermediate_jsons.append(output_file)
                
            else:
                print(f"Error: {response.status_code} for {query_name} in the {year} year")
                print(response.text)
                print ("-" * 30)

        return intermediate_jsons

    def overpass_query_builder(self, year:int, bbox:str) -> dict[str, str]:
        """
        A function to build the query for Overpass API
        """
        #TODO: The data limit is 1GB. We should try split the query into smaller parts (bounding boxes) and run them separately.
        #NOTE: the issue with the above is that you might get IP blocked by the server. So, we need to be careful with this.
        query_roads = f"""
        [out:json]
        [maxsize:1073741824]
        [timeout:9000]
        [date:"{year}-12-31T23:59:59Z"]
        [bbox:{bbox}];
        way["highway"~"(motorway|trunk|primary|secondary|tertiary)"];
        /* also includes 'motorway_link',  'trunk_link' etc. because they also restrict habitat connectivity */
        (._;>;);
        out body;
        """
        # '{' characters must be doubled in Python f-string (except for {bbox} because it is a variable)
        # to include statement on paved surfaces use: ["surface"~"(paved|asphalt|concrete|paving_stones|sett|unhewn_cobblestone|cobblestone|bricks|metal|wood)"];
        # it is important to include only paved roads it is important to list all values above, not only 'paved'*/
        # BUT! : 'paved' tag seems to be missing in a lot of features at timestamps from 2010s
        # 'residential' roads are not fetched as these areas are already identified in land-use/land-cover data as urban or residential ones
        # "~" extracts all tags containing this text, for example 'motorway_link'
        
        query_railways = f"""
        [out:json]
        [maxsize:1073741824]
        [timeout:9000]
        [date:"{year}-12-31T23:59:59Z"]
        [bbox:{bbox}];
        way["railway"~"(rail|light_rail|narrow_gauge|tram|preserved)"];
        (._;>;);
        out;
        """
        
        # way["railway"];  # to include features if 'railway' key is found (any value)
        # to include features with values filtered by key. 
        # This statement also includes 'monorail' which are not obstacles for species migration, but these features are extremely rare. Therefore, it was decided not to overcomplicate the query.
        # 31/07/2024 - added filtering on 'preserved' railway during the verification by UKCEH LULC dataset (some railways are marked as 'preserved at older timestamps and 'rail' in newer ones).
    
        query_waterways = f"""
        [out:json]
        [maxsize:1073741824]
        [timeout:9000]
        [date:"{year}-12-31T23:59:59Z"]
        [bbox:{bbox}];
        (
        way["waterway"~"^(river|canal|flowline|tidal_channel)$"];
        way["water"~"^(river|canal)$"];
        );
        /* ^ and $ symbols to exclude 'riverbank' and 'derelict_canal'*/
        /*UPD - second line is added in case if some older features are missing 'way' tag*/
        (._;>;);
        out;
        """

        # Query to bring water features with deprecated tags
        query_waterbodies = f"""
        [out:json]
        [maxsize:1073741824]
        [timeout:9000]
        [date:"{year}-12-31T23:59:59Z"]
        [bbox:{bbox}];
        (
        nwr["natural"="water"];
        nwr["water"~"^(cenote|lagoon|lake|oxbow|rapids|river|stream|stream_pool|canal|harbour|pond|reservoir|wastewater|tidal|natural)$"];
        nwr["landuse"="reservoir"];
        nwr["waterway"="riverbank"];
        /*UPD - second filter was added to catch other water features at all timestamps*/
        /*UPD - third and fourth filters were added to catch other water features at older timestamps*/
        /*it is more reliable to query nodes, ways and relations altogether ('nwr') to fetch the complete polygon spatial features*/
        );
        (._;>;);
        out;
        """
        
        # to include small waterways use way["waterway"~"(^river$|^canal$|flowline|tidal_channel|stream|ditch|drain)"]


        # merge queries into dictonary
        # to include all queries
        return {"roads":query_roads, "railways":query_railways, "waterways":query_waterways, "waterbodies":query_waterbodies}
    

    def convert_to_geojson(self, queries:dict[str,str]):
        for year in self.years:
            for query_name, query in queries.items():
                input_file = os.path.join(self.output_dir, f"{query_name}_{year}.json")
                output_file = os.path.join(self.output_dir, f"{query_name}_{year}.geojson")
                result = subprocess.run(['osmtogeojson', input_file], capture_output=True, text=True)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(result.stdout)

    def fix_invalid_geometries(self, queries:dict[str,str], year:int ,overwrite_original:bool):
        """
        A function to fix invalid geometries in the GeoJSON files

        Args:
            queries (dict): a dictionary of queries
            year (int): the year of the data
            overwrite_original (bool): whether to overwrite the original GeoJSON files

        Returns:
            list: a list of fixed GeoJSON files
        """
        geojson_files=[]

        # iterate over the queries and define outputs
        for query_name, query in queries.items():
            geojson_file = os.path.join(self.output_dir, f"{query_name}_{year}.geojson")

            # check if the non-zero GeoJSON files exist
            if os.path.exists(geojson_file) and os.path.getsize(geojson_file) > 0:
                print(f"Conversion to GeoJSON for {query_name} in the {year} year was successful.")
                
                # read the GeoJSONs
                with open(geojson_file, 'r', encoding='utf-8') as f:
                    geojson_data = json.load(f)
                    features = geojson_data.get('features', [])
                    print(f"Total features: {len(features)}")
                    
                # determine the geometries to filter based on query_name
                # for roads, railways and waterways extract only lines and multilines
                if query_name in ("roads", "railways", "waterways"):
                    geometry_types = ['LineString', 'MultiLineString']
                    # filter based on geometry types and level - it should be 0 (or null)
                    filtered_features = [
                        feature for feature in geojson_data.get('features', [])
                        if feature['geometry']['type'] in geometry_types
                        and (feature['properties'].get('level') in (None, 0)) # filtering by ground level of infrastructure
                    ]
                # for waterbodies extract only polygons and multipolygons
                elif query_name == "waterbodies":
                    geometry_types = ['Polygon', 'MultiPolygon']
                    # filter based on geometry types only
                    filtered_features = [
                        feature for feature in geojson_data.get('features', [])
                        if feature['geometry']['type'] in geometry_types
                    ]
                # for everything else extract everything that can be found
                else:
                    filtered_features = [
                        feature for feature in geojson_data.get('features', [])
                    ]

                # cast all property keys to lowercase
                filtered_features = [
                    {
                        k: {property_key.lower(): property_value for property_key, property_value in v.items()} if k == "properties" else v
                        for k, v in feature.items()
                    }
                    for feature in filtered_features
                ]
                # create a new GeoJSON structure with filtered features
                filtered_geojson_data = {
                    "type": "FeatureCollection",
                    "features": filtered_features
                }

                print(f"Total features after filtering {query_name} in the {year} year: {len(filtered_features)}")
                print ("-" *30)
                
                # create new file 
                if overwrite_original == False:
                    geojson_file = os.path.join(self.output_dir, f"{query_name}_{year}_filtered.geojson")
                
                # overwrite the original GeoJSON file with the filtered one
                with open(geojson_file, 'w', encoding='utf-8') as f:
                    json.dump(filtered_geojson_data, f, ensure_ascii=False, indent=4)

                # write filenames to the list with intermediate geojsons
                geojson_files.append(geojson_file)
            
            else:
                print(f"Conversion to GeoJSON for {query_name} in the {year} year failed.")
                print ("-" *30)

osm = Osm_PreProcessor('config.yaml',"./data/input/osm/")
queries = osm.overpass_query_builder(2018, osm.bbox) #TODO check what lulc[0] is in year
# # TODO loop over all lulc files
# osm.fetch_osm_data(queries=queries, year=2018)
osm.convert_to_geojson(queries=queries)
osm.fix_invalid_geometries(queries,2018,False)