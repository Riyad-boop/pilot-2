import geopandas as gpd
import rasterio
import os
import subprocess
import numpy as np

class Rasterizer_Processor:

    def __init__(self, gpkg_filepath:str, lulc_dir:str,pa_timeseries_dir:str) -> None:
        self.gdf = gpd.read_file(gpkg_filepath)
        self.input_folder = lulc_dir
        self.output_dir = pa_timeseries_dir
        # create output directory if it does not exist
        os.makedirs(pa_timeseries_dir, exist_ok=True)

        tiff_files = [f for f in os.listdir(lulc_dir) if f.endswith('.tif')]

        # choose the first TIFF file (it shouldn't matter which LULC file to extract extent because they must have the same extent)
        if tiff_files:
            file_path = os.path.join(lulc_dir, tiff_files[0])  
            extent, self.res = self.extract_ext_res(file_path)
            self.min_x, self.max_x, self.min_y, self.max_y = extent.left, extent.right, extent.bottom, extent.top
            print("Extent of LULC files")
            print("Minimum X Coordinate:", self.min_x, 
                "\n Maximum X Coordinate:", self.max_x, 
                "\n Minimum Y Coordinate:", self.min_y, 
                "\n Maximum Y Coordinate:", self.max_y)
            print("Spatial resolution (pixel size):", self.res)
        else:
            raise ValueError("No LULC files found in the input folder.")

        # extract the year from the filename
        self.year_stamps = [int(f.split('_')[1].split('.')[0]) for f in tiff_files]
        print("Considered timestamps of LULC data are:","".join(str(self.year_stamps)))

            
    # define function
    def extract_ext_res(self, file_path:str) -> tuple[any,float]:
        """
        Extracts the extent and resolution of a raster file.

        Args:
            file_path (str): The path to the raster file.

        Returns:
            tuple: The extent and resolution of the raster file.
        """
        with rasterio.open(file_path) as src:
            extent = src.bounds
            res = src.transform[0]  # assuming the res is the same for longitude and latitude
        return extent, res
    

    def filter_pa_by_year(self) -> None:
        # create an empty dictionary to store subsets
        subsets_dict = {}
        # loop through each year_stamp and create subsets
        for year_stamp in self.year_stamps:
            # filter Geodataframe based on the year_stamp
            subset = self.gdf[self.gdf['year'] <= np.datetime64(str(year_stamp))]

            # store subset in the dictionary with year_stamp as key
            subsets_dict[year_stamp] = subset

            # print key-value pairs of subsets 
            print(f"Protected areas are filtered according to year stamps of LULC and PAs' establishment year: {year_stamp}")

            # ADDITIONAL BLOCK IF EXPORT TO GEOPACKAGE IS NEEDED (currently needed as rasterizing vector data is not possible with geodataframes)
            ## save filtered subset to a new GeoPackage
            subset.to_file(os.path.join(self.output_dir,f"pas_{year_stamp}.gpkg"), driver='GPKG')
            print(f"Filtered protected areas are written to:",os.path.join(self.output_dir,f"pas_{year_stamp}.gpkg"))

        print ("---------------------------")

    def rasterize_pas_by_year(self, keep_intermediate_gpkg:bool=False) -> None:
        # list all subsets of protected areas by the year of establishment
        pas_yearstamps = [f for f in os.listdir(self.output_dir) if f.endswith('.gpkg')]
        pas_yearstamp_rasters = [f.replace('.gpkg', '.tif') for f in pas_yearstamps]

        # loop through each input file
        for pas_yearstamp, pas_yearstamp_raster in zip(pas_yearstamps, pas_yearstamp_rasters):
            pas_yearstamp_path = os.path.join(self.output_dir, pas_yearstamp)
            pas_yearstamp_raster_path = os.path.join(self.output_dir, pas_yearstamp_raster)
            # TODO - to make paths more clear and straightforward
            print(f"Rasterizing protected areas for {pas_yearstamp}")
            # rasterize
            pas_rasterize = [
                "gdal_rasterize",
                ##"-l", "pas__merged", if you need to specify the layer
                "-burn", "100", ## assign code starting from "100" to all LULC types
                "-init", "0",
                "-tr", str(self.res), str(self.res), #spatial res from LULC data
                "-a_nodata", "-2147483647", # !DO NOT ASSIGN 0 values with non-data values as it will mask them out in raster calculator
                "-te", str(self.min_x), str(self.min_y), str(self.max_x), str(self.max_y), # minimum x, minimum y, maximum x, maximum y coordinates of LULC raster
                "-ot", "Int32",
                "-of", "GTiff",
                "-co", "COMPRESS=LZW",
                pas_yearstamp_path,
                pas_yearstamp_raster_path
                ]

            # execute rasterize command
            try:
                subprocess.run(pas_rasterize, check=True)
                print("Rasterizing of protected areas has been successfully completed for", pas_yearstamp)
            except subprocess.CalledProcessError as e:
                print(f"Error rasterizing protected areas: {e}")
            finally:
                if not keep_intermediate_gpkg:
                    os.remove(pas_yearstamp_path)
                    print(f"Intermediate GeoPackage {pas_yearstamp} has been removed.")