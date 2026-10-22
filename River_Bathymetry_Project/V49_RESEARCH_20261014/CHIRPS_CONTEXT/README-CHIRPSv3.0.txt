== README FOR ==


Climate Hazards Center Infrared Precipitation with Stations version 3.0 (CHIRPS v3.0). 
Quasi-global satellite and observation-based precipitation estimates over land, 60°N to 60°S, from 1981 to near-real time.


== PRODUCED BY ==


   Climate Hazards Center
   Department of Geography
   University of California Santa Barbara


  In collaboration with:
The United States Department of State Famine Early Warning Systems Network (FEWS NET) and the US Geological Survey Earth Resources Observation and Science Center (USGS EROS)


== SUMMARY ==


The Climate Hazards Center InfraRed Precipitation with Stations version 3 (CHIRPS v3.0) data archive is a quasi-global (60°N-60°S, 180°W-180°E), gridded high resolution 0.05 degree, 1981 to near-real time precipitation time series. The terrestrial precipitation estimates are available in pentadal to annual time intervals. In addition to the quasi-global extent, subsets are available for Africa and Latin America (from Mexico to all of South America) regions. All spatial domains are available in several file formats (NetCDF, GeoTIFF, BIL, PNG) and are located in separate subdirectories.


Two CHIRPS products are produced operationally: A rapid preliminary version, and a later final version. The preliminary CHIRPS product is available for the entire domain two days after the end of a pentad (on the 2nd, 7th, 12th, 17th, 22nd and 27th day of each month). The preliminary CHIRPS v3.0 uses readily available in situ station observations, including reports from the World Meteorological Organization (WMO) Global Telecommunications System (GTS), NOAA’s Global Historical Climatology Network (GHCN), Synoptic Summary of the Day (SSOD), and from Mexico’s National Water Commission (CONAGUA). Additional data sources include:
* Instituto de Hidrología, Meteorología y Estudios Ambientales (IDEAM, Colombia’s Institute of Hydrology, Meteorology and Environmental Studies)
* Instituto Meteorológico Nacional de Costa Rica (IMN, Costa Rica’s National Meteorological Agency)
* Republic of Korea Meteorological Administration
* Drought Information System for Southern South America (SISSA) 
* Instituto Nacional de Sismología, Vulcanologia, Meteorologia e Hidrología (INSIVUMEH, Guatemala’s National Institute for Seismology, Vulcanology, Meteorology and Hydrology)
* Dirección Meteorológica de Chile (Chilean Meteorological Service) 
* Deutscher Wetterdienst (DWD, German Meteorological Service)
* 3D-Printed Automatic Weather Stations (3D-PAWS) in Kenya


In the preliminary CHIRPS these inputs do not undergo the same rigorous quality control screening that is used for the final CHIRPS. The final CHIRPS product, which is updated monthly, undergo multiple quality control steps. CHIRPS Final data is typically complete during the third week of the following month. The final version of CHIRPS products are calculated at that time, for all times/domains/formats.


== VERSION HISTORY ==


   Version 3.0 released 2025.01.01
   Version 2.0 released 2015.02.12


== Changes in Version 3.0 ==


Since v2.0 we have added new stations around the world. CHIRPS v3.0 uses more than 90 sources of station data–nearly four times that of CHIRPS v2.0. The CHC received about 80,000 new station normals from the Global Precipitation Climatology Centre (GPCC); these were incorporated into the climatology (CHPclim2) used in CHIRPS v3.0. Additional station data sources include observations from a new network of 3D Printed Automatic Weather Stations (3D-PAWS) that are currently reporting in Kenya.


In CHIRPS v3.0 we also made a switch to gauge-undercatch corrected station data. This is a location-based adjustment that accounts for the influence of wind on the amount of rainfall captured by a gauge, a correction that was not accounted for in CHIRPS v2.0. As a result, CHIRPS v3.0 is overall wetter compared to CHIRPS v2.0. 


Beyond station-based improvements, the satellite-only precipitation  algorithm–CHIRP3–estimates a wider range of precipitation values. This improvement is due to a reduction in the intercept term in the v3.0 formulation. While not always exactly zero, this term is greatly reduced in the new algorithm, while the slope term is increased in magnitude. This adjustment increases the variance of the b1*CCD (where b is the beta coefficient) variations in CHIRP v3.0.


Other key improvements include:
* A 10 degree increase in spatial extent. CHIRPS v3.0 extends to 60°N-60°S
* In CHIRPS v3.0, missing data is filled with higher resolution unbiased 0.25° ERA5 data while CHIRPS v2 was filled with 0.5° CFS data.


Expanded diagnostics are made publicly available for version 3.0. These include CHIRPS number of stations by country, missing satellite data (fill maps), station comparison plots, global monthly quality control plots, global monthly station density maps, list of stations used in CHIRPS v3.0 Final, list of stations used in the CHIRPS v3.0 Prelim, list of stations per month by country, and gridded global data layers of Legates gauge-undercatch monthly correction factors that are used to adjust station data in CHIRPS.


== ACCESS ==


   Online display and access,
     https://data.chc.ucsb.edu/products/CHIRPS/v3.0/

   CHC landing page for all protocols and all data
	https://data.chc.ucsb.edu/

   Early Warning Explorer:  The Early Warning eXplorer (EWX) is an interactive web-based mapping tool that allows users to visualize geospatial data related to drought monitoring and famine early warning. CHIRPS v3  data, anomaly and z-score layers are included in the UCSB CHC’s EWX. 
    Climate Hazards Center EWX: https://ewx3.chc.ucsb.edu/ewx/index.html


== FOLDERS ==


   pentads_africa        Africa subset pentadal fields. BILs, PNGs, and TIFFs. 
   pentads_global        Global pentadal fields. BILs, COGs, TIFFs and NetCDFs.
   pentads_latam         Mexico to South America subset pentadal fields. BILs and TIFFs.
   dekads_africa         Africa subset dekadal fields. BILs, PNGs and TIFFs.
   dekads_global         Global dekadal fields. BILs, NetCDFs and TIFFs.
   dekads_latam          Mexico to South America subset dekadal fields. BILs and TIFFs.
   monthly_africa        Africa subset monthly fields. BILs, TIFFs, and PNGs.
   monthly_global        Global monthly fields. BILs, COGS, NetCDFs, and TIFFs.
   monthly_latam         Mexico to South America monthly fields. BILs and TIFFs.
   2-monthly_global      Global 2-monthly fields. TIFFs.
   3-monthly_global      Global 3-monthly fields. TIFFs.
   4-monthly_global      Global 4-monthly fields. TIFFs.
   5-monthly_global      Global 5-monthly fields. TIFFs.
   6-monthly_global      Global 6-monthly fields. TIFFs.
   annual_africa         Africa subset annual fields. TIFFs.
   annual_global         Global annual fields. TIFFs and NetCDF.
   annual_latam          Mexico to South America subset annual fields. TIFFs.
   diagnostics           Various data/plots giving more detail about CHIRPS processing and results
  


== GET ADDED TO OUR USERS LIST ==


   If you would like to receive updates on CHIRPS 
   processing/validations/publications etc. send an email to
      pete@geog.ucsb.edu 
Or    rnsaldivar@ucsb.edu




== CONTACT ==


   Data:
   Pete Peterson
   pete@geog.ucsb.edu
Or
   Robert Saldivar 
   rnsaldivar@ucsb.edu


   Science:
   Chris Funk
   chris@geog.ucsb.edu


   Web: chc.ucsb.edu/data/chirps3
          




