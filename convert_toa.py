#!/usr/bin/env python

import rasterio
from xml.dom import minidom
import glob
import os
import argparse
import math
import datetime

parser = argparse.ArgumentParser(description='Convert Planet TIFs to TOA')
parser.add_argument('folders', type=str, nargs='+', help='the folders containing TIFs')
parser.add_argument('-c', '--clobber', action="store_true", help='Whether to overwrite existing toa tiffs')
args = parser.parse_args()

EAI = [1997.8, 1863.5, 1560.4, 1395.0, 1124.4] # Exo-Atmospheric Irradiance as per https://www.planet.com/products/satellite-imagery/files/160625-RapidEye%20Image-Product-Specifications.pdf

for i, folder in enumerate(args.folders):
  print("processing {}/{} - {}".format(i, len(args.folders), folder))
  toa_file = glob.glob(os.path.join(folder, "*Analytic_toa.tif"))
  if toa_file and not args.clobber:
    print(folder + " already processed")
    continue
  tif_file = None
  mode = None
  try:
    tif_file = glob.glob(os.path.join(folder, "*BGRN_Analytic.tif"))[0]
    mode = "BGRN"
  except IndexError:
    pass
  try:
    tif_file = glob.glob(os.path.join(folder, "*3A_Analytic.tif"))[0]
    mode = "3A"
  except IndexError:
    pass
  if not tif_file:
    print("Couldn't find an _Analytic tif in {}".format(folder))
    continue
  try:
    xml_file = glob.glob(os.path.join(folder, "*_Analytic_metadata.xml"))[0]
  except IndexError:
    print("Couldn't find an _Analytic_metadata xml in {}".format(folder))
    continue

  try:
    with rasterio.open(tif_file) as src:
      bands = src.read().astype(float)

    xmldoc = minidom.parse(xml_file)

    if mode == "3A":
      solar_elevation_angle_deg = float(xmldoc.getElementsByTagName("opt:illuminationElevationAngle")[0].firstChild.data)
      acquisitionDate = xmldoc.getElementsByTagName("re:acquisitionDateTime")[0].firstChild.data
      dt = datetime.datetime.strptime(acquisitionDate, "%Y-%m-%dT%H:%M:%S.%fZ")
      day = dt.timetuple().tm_yday
      sun_distance = 1 - 0.01672 * math.cos(math.radians(0.9856 * (day - 4)))
      solar_zenith_rad = math.radians(90 - solar_elevation_angle_deg)

    nodes = xmldoc.getElementsByTagNameNS("*", "bandSpecificMetadata")
    # XML parser refers to bands by numbers 1-4
    for node in nodes:
      bn = node.getElementsByTagNameNS("*", "bandNumber")[0].firstChild.data
      try:
        i = int(bn) - 1
        if mode == "BGRN":
          value = node.getElementsByTagNameNS("*", "reflectanceCoefficient")[0].firstChild.data
          bands[i] *= float(value) * 10000
        elif mode == "3A":
          radiometricScaleFactor = float(node.getElementsByTagNameNS("*", "radiometricScaleFactor")[0].firstChild.data)
          coeff = radiometricScaleFactor * ((math.pi * math.pow(sun_distance, 2)) / (EAI[i] * math.cos(solar_zenith_rad))) * 10000
          bands[i] *= coeff
      except ValueError:
        print("{} doesn't look like a channel".format(bn))

    # Set spatial characteristics of the output object to mirror the input
    kwargs = src.meta
    kwargs.update(compress='lzw')

    processed_filename = tif_file.replace("Analytic.tif", "Analytic_toa.tif")

    with rasterio.open(processed_filename, 'w', **kwargs) as dst:
      dst.write(bands.astype(rasterio.uint16))
  except Exception as e:
    print("ERROR! : " + e)
