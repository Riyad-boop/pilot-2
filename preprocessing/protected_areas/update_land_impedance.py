from osgeo import gdal
gdal.UseExceptions()
import numpy as np
import csv
import os
import subprocess
import pandas as pd

class UpdateLandImpedance():

    def __init__(self, input_folder, output_folder, reclass_table) -> None:
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.reclass_table = reclass_table

        self.tiff_files = [f for f in os.listdir(input_folder) if f.endswith('.tif')]
        os.makedirs(output_folder, exist_ok=True)

        for tiff_file in self.tiff_files:
            input_raster_path = os.path.join(input_folder, tiff_file)
            print (tiff_file)
            # modify the output raster filename to ensure it's different from the input raster filename
            output_filename = "impedance_" + tiff_file
            output_raster_path = os.path.join(output_folder, output_filename)

            # call function and capture data_type for compression - Float32 or Int32
            data_type = self.reclassify_raster(input_raster_path, output_raster_path, reclass_table)
            print ("Data type used to reclassify LULC as impedance is",data_type)

            # compression using 9999 as nodata
            compressed_raster_path = os.path.splitext(output_raster_path)[0] + '_compr.tif'
            print("path to compressed raster is:", compressed_raster_path)
            subprocess.run(['gdal_translate', output_raster_path, compressed_raster_path,'-a_nodata', '9999', '-ot', data_type, '-co', 'COMPRESS=LZW'])

            # as soon as gdal_translate doesn't support rewriting, we should delete non-compressed GeoTIFFs...
            os.remove(output_raster_path)
            # ...and rename compressed file in the same way as the original GeoTIFF
            os.rename(compressed_raster_path, output_raster_path)

            print("Reclassification complete for:", input_raster_path + "\n------------------------------------")
        

    def lulc_impedance_mapper(self, reclass_table:str) -> dict:

        has_decimal = False
        # read into pandas dataframe and conver to numeric
        df = pd.read_csv(reclass_table, encoding='utf-8-sig')
        df = df.apply(pd.to_numeric, errors='coerce')
        # check if there are decimal values in the dataframe
        if df['impedance'].dtype == 'float64':
            has_decimal = True
            # convert lulc to float too
            df['lulc'] = df['lulc'].astype(float)

        # create a dictionary from the dataframe reclass_dict[lulc] = impedance
        reclass_dict = df.set_index('lulc')['impedance'].to_dict()
        
        if has_decimal:
            print("LULC impedance is characterized by decimal values.")
            # update reclassification dictionary to align nodata values with one positive value (Graphab requires positive value as no_data value)
            # assuming nodata value is 9999 (or 9999.00 if estimating decimal values)
            reclass_dict.update({-2147483647: 9999.00, -32768: 9999.00, 0: 9999.00}) # minimum value for int16, int32 and 0 are assigned with 9999.00 (nodata)
        else:
            print("LULC impedance is characterized by integer values only.")
            # update dictionary again
            reclass_dict.update({-2147483647: 9999, -32768: 9999, 0: 9999}) # minimum value for int16, int32 and 0 are assigned with 9999.00 (nodata)
        
        return reclass_dict , has_decimal , "Int64" if has_decimal == False else "Float64"


    def reclassify_raster(self, input_raster:str, output_raster:str, reclass_table:str) -> str:
        """
        Reclassifies a raster based on a reclassification table.

        Args:
            input_raster (str): The path to the input raster.
            output_raster (str): The path to the output raster.
            reclass_table (str): The path to the reclassification table.

        Returns:
            str: The data type of the output raster.
        """
        # read the reclassification table
        reclass_dict = {}
        # map lulc with impedance values from the reclassification table
        reclass_dict,has_decimal,data_type = self.lulc_impedance_mapper(reclass_table)
           
        print ("Mapping dictionary used to classify impedance is:", reclass_dict)

        # open input raster
        dataset = gdal.Open(input_raster)
        if dataset is None:
            print("Could not open input raster.")
            return

        # get raster info
        cols = dataset.RasterXSize
        rows = dataset.RasterYSize

        # initialize output raster
        driver = gdal.GetDriverByName("GTiff")
        if has_decimal:
            output_dataset = driver.Create(output_raster, cols, rows, 1, gdal.GDT_Float32)
        else:
            output_dataset = driver.Create(output_raster, cols, rows, 1, gdal.GDT_Int32)
        #TODO - to add condition on Int32 if integer values are revealed
        output_dataset.SetProjection(dataset.GetProjection())
        output_dataset.SetGeoTransform(dataset.GetGeoTransform())

        # reclassify each pixel value
        input_band = dataset.GetRasterBand(1)
        output_band = output_dataset.GetRasterBand(1)
        # read the entire raster as a NumPy array
        input_data = input_band.ReadAsArray()

        if input_data is None:
            print("Could not read input raster.")
            return
        elif reclass_dict is None:
            print("Reclassification dictionary is empty.")
            return
        # apply reclassification using dictionary mapping
        output_data = np.vectorize(reclass_dict.get)(input_data)
        output_band.WriteArray(output_data)

        '''FOR CHECKS
        print (f"input_data_shape is': {input_data.shape}")
        print (f"output_data_shape is': {output_data.shape}")
        '''
        
        # close datasets
        dataset = None
        output_dataset = None

        return (data_type)
    # TODO - define a multiplier (effect of protected areas), cast it to yaml function and apply to estimate impedance and affinity
