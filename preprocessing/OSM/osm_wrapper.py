import os
import shutil

# Local imports
from preprocessing.OSM.osm_preprocessor import Osm_PreProcessor
from preprocessing.OSM.osm_geojson_to_gpkg import OsmGeojson_to_gpkg

class Osm_Wrapper():

    def __init__(self, year:int = 2018):
        self.year = year

    def get_osm_data(self, output_dir:str="./data/input/osm/"):
        osm = Osm_PreProcessor('config.yaml',output_dir)
        queries = osm.overpass_query_builder(self.year, osm.bbox) #TODO check what lulc[0] is in year
        # # TODO loop over all lulc files
        osm.fetch_osm_data(queries=queries, year=self.year)
        osm.convert_to_geojson(queries=queries)
        osm.fix_invalid_geometries(queries,self.year,False)

    def merge_gpkg_files(self):
        input_dir = os.path.join(os.getcwd(), 'data/input/osm')
        output_dir = os.path.join(input_dir, 'gpkg_temp')
        ogtg = OsmGeojson_to_gpkg(input_dir,output_dir,target_epsg=4326)
        output_file = os.path.join(output_dir, f'osm_merged_{self.year}.gpkg')
        fixed_gpkg = os.path.join(output_dir, f'osm_merged_{self.year}_fixed.gpkg')
        ogtg.merge_gpkg_files(output_file, self.year)
        ogtg.fix_geometries_in_gpkg(output_file, fixed_gpkg, overwrite_original=False)
        ogtg.delete_temp_files()
        #NOTE remember to move file to vector_dir for next notebook (merging into single raster)
        shutil.move(fixed_gpkg, os.path.join(os.getcwd(), f'data/input/vector/osm_merged_{self.year}.gpkg'))


# example usage
# if __name__ == "__main__":
#     osm = Osm_Wrapper()
#     osm.get_osm_data()
#     osm.merge_gpkg_files()