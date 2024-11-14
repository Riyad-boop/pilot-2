import os
import warnings

# Local imports
from utils import load_yaml
from lulc_enrichment_processor import lulc_enrichment_processor


class lulc_enrichment_wrapper():
    def __init__(self, config_path:str, output_dir:str) -> None:
        self.config = load_yaml(config_path)
        self.years = self.config.get('year', None)
        if self.years is None:
            warnings.warn("Year variable is null or not found in the configuration file... \n Defaulting to 2018")
            self.years = [2018]
        elif isinstance(self.years, int):
            self.years = [self.years]

        lulc_template = self.config.get('lulc', None)
        # substitute year from the configuration file
        year = self.years[0]
        lulc = lulc_template.format(year=year)

        print(f"Input raster to be used for processing is {lulc}.")

        parent_dir = os.getcwd()
        lulc_dir = self.config.get('lulc_dir')
        output_dir = self.config.get('output_dir')

        # create the output directory if it does not exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
        
        # specifying the path to input files through the path variables
        lulc = os.path.normpath(os.path.join(parent_dir,lulc_dir,lulc))
        self.adp = lulc_enrichment_processor(self.config, parent_dir,lulc,year, save_osm_stressors=True)

if __name__ == "__main__":
    lew = lulc_enrichment_wrapper('config.yaml', 'output')
    lew.adp.prepare_lulc_osm_data()
    lew.adp.merge_lulc_osm_data(save_osm_stressors=True)