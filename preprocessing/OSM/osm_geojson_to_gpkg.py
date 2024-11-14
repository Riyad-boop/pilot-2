import shutil
import os
import subprocess
from osgeo import ogr

class OsmGeojson_to_gpkg():
    def __init__(self, input_dir:str,output_dir:str,target_epsg:str) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.target_epsg = target_epsg
        # replace .geojson with .gpkg for each file
        self.gpkg_files = [file.replace('.geojson', '.gpkg') for file in self.convert_geojson_to_gpkg()]

    def convert_geojson_to_gpkg(self, file_ending:str='filtered.geojson') -> list:
        # create output directory if it does not exist
        os.makedirs(self.output_dir, exist_ok=True)
        # loop through all geojson files in directory
        geojson_files = []
        for filename in os.listdir(self.input_dir):
            if filename.endswith(file_ending):
                geojson_file = os.path.join(self.input_dir, filename)
                geopackage_file = os.path.join(self.output_dir, filename.replace('.geojson', '.gpkg'))
            
                try:
                    # run function as a shell script through subprocess library
                    result = subprocess.run(['ogr2ogr', '-f', 'GPKG', '-t_srs', f'EPSG:{self.target_epsg}', geopackage_file, geojson_file], 
                                            check=True, 
                                            capture_output=True, 
                                            text=True)
                    
                    print(f"Converted and modified to GeoPackage: {filename}")

                    #check error code
                    if len(result.stderr) > 0:
                        print(f"Warnings or errors:\n{result.stderr}")

                    # append filenames with a list
                    geojson_files.append(filename)

                except subprocess.CalledProcessError as e:
                    print(f"Error processing {filename}: {e}")
                except Exception as e:
                    print(f"Unexpected error with {filename}: {e}")

        # return the list of GeoJSON files
        return geojson_files
    
    def merge_gpkg_files(self, output_file:str, year:int):
        # initialize the GeoPackage using the first GeoPackage file
        first_gpkg_file = self.gpkg_files[0]
        layer_name = first_gpkg_file.split(f"_{year}")[0]
        first_gpkg_file = os.path.join(self.output_dir, first_gpkg_file)

        subprocess.run(['ogr2ogr', '-f', 'GPKG', output_file, first_gpkg_file, # output and input files
                '-s_srs', f'EPSG:{self.target_epsg}',  # set source CRS
                '-t_srs', f'EPSG:{self.target_epsg}', # set target CRS
                '-nln', layer_name # specify name of the layer
                ], check=True, capture_output=True, text=True) # to show log
        print(f"Initialized merged GeoPackage with CRS EPSG:{self.target_epsg} from {layer_name}.")

        for gpkg_file in self.gpkg_files[1:]:  # skip the first file because it's already added
            layer_name = gpkg_file.split(f"_{year}")[0]
            gpkg_file = os.path.join(self.output_dir, gpkg_file)
            # run appending separate geopackages to empty merged geopackage (update if layers were previously written)
            try:
                result = subprocess.run(['ogr2ogr', '-f', 'GPKG', output_file, '-s_srs', f'EPSG:{self.target_epsg}', # for input file
                                                '-t_srs', f'EPSG:{self.target_epsg}', # for output file
                                                '-nln', layer_name, '-update', '-append', gpkg_file],
                                                check=True, 
                                                capture_output=True, 
                                                text=True)
                
                print(f"Added layer {layer_name} from {gpkg_file} to {output_file}")
                if len(result.stderr) > 0:
                    print(f"Warnings or errors:\n{result.stderr}")

            except subprocess.CalledProcessError as e:
                print(f"Error adding {layer_name}: {e.stderr}")
            except Exception as e:
                print(f"Unexpected error with {layer_name}: {e}")

    def fix_geometries_in_gpkg(self, input_gpkg:str, fixed_gpkg:str=None, overwrite_original:bool=False):
        # if fixed_gpkg is not specified, overwrite the input_gpkg
        if fixed_gpkg is None:
            fixed_gpkg = input_gpkg
        else:
            shutil.copyfile(input_gpkg, fixed_gpkg) # to copy file to a new one

        # open the output GeoPackage for editing
        data_source = ogr.Open(fixed_gpkg, update=1)

        for i in range(data_source.GetLayerCount()):
            layer = data_source.GetLayerByIndex(i)
            layer_name = layer.GetName()
            feature_to_fix_count = 0
            fixed_feature_count = 0
            invalid_feature_count = 0

            # iterate over all features in the layer
            for feature in layer:
                geometry = feature.GetGeometryRef()
                if not geometry.IsValid():
                    feature_to_fix_count += 1 # increment the number of features to be fixed
                    # attempt to fix the geometry
                    fixed_geometry = geometry.MakeValid()

                    if fixed_geometry.IsValid():
                        # replace the geometry with the fixed one
                        feature.SetGeometry(fixed_geometry)
                        layer.SetFeature(feature)  # save the updated feature back to the layer
                        print(f"Fixed invalid geometry in layer '{layer_name}', feature ID: {feature.GetFID()}")
                        fixed_feature_count += 1 # increment the number of fixed features
                    else:
                        print(f"Could not fix geometry in layer '{layer_name}', feature ID: {feature.GetFID()}")
                        invalid_feature_count += 1 # increment the number of features that cannot be fixed

        # estin
        
        if feature_to_fix_count == 0:
            print (f"All geometries of features in the layer '{layer_name}' of the output vector are valid.")
            print("-" * 40)
        else:
            print(f"Layer '{layer_name}: {fixed_feature_count} geometries fixed.") 
            print(f"Layer '{layer_name}': {invalid_feature_count} geometries could not be fixed.")
            print("-" * 40)

        # close the data source
        del data_source

        # remove the original GeoPackage if it should be overwritten
        if overwrite_original:
            shutil.copyfile(fixed_gpkg, input_gpkg)
            print(f"Fixed geometries and saved to {input_gpkg}.")
            os.remove(fixed_gpkg)
        else:
            print(f"Fixed geometries and saved to {fixed_gpkg}.")

    
    def delete_temp_files(self):
        # delete all GeoJSON files
        for file in os.listdir(self.input_dir):
            if file.endswith('.geojson'):
                os.remove(os.path.join(self.input_dir, file))
        print("Deleted all intermediate GeoJSON files.")
        print("-" * 40)

        for file in os.listdir(self.output_dir):
            if file.startswith('osm_merged'):
                continue
            else:
                os.remove(os.path.join(self.output_dir, file))

