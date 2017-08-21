#!/usr/bin/env python

import rasterio
from xml.dom import minidom
import glob
import os
import argparse

parser = argparse.ArgumentParser(description='Convert Planet TIFs to TOA')
parser.add_argument('folders', type=str, nargs='+', help='the folders containing TIFs')
args = parser.parse_args()

for folder in args.folders:
  tif_file = glob.glob(os.path.join(folder, "*BGRN_Analytic.tif"))[0]
  xml_file = glob.glob(os.path.join(folder, "*BGRN_Analytic_metadata.xml"))[0]

  with rasterio.open(tif_file) as src:
    bands = src.read().astype(float)
    
  xmldoc = minidom.parse(xml_file)
  nodes = xmldoc.getElementsByTagName("ps:bandSpecificMetadata")

  # XML parser refers to bands by numbers 1-4
  for node in nodes:
    bn = node.getElementsByTagName("ps:bandNumber")[0].firstChild.data
    try:
      i = int(bn) - 1
      value = node.getElementsByTagName("ps:reflectanceCoefficient")[0].firstChild.data
      bands[i] *= float(value) * 10000
    except ValueError:
      print("{} doesn't look like a channel".format(bn))

  # Set spatial characteristics of the output object to mirror the input
  kwargs = src.meta
  kwargs.update(compress='lzw')

  processed_filename = tif_file.replace("Analytic.tif", "Analytic_toa.tif")

  with rasterio.open(processed_filename, 'w', **kwargs) as dst:
    dst.write(bands.astype(rasterio.uint16))
  print("{} done".format(folder))
