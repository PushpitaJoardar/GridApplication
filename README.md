# GridApplication

agents_to_cell_csv.py ------Map agent trajectory points (lat/longitude) to grid cells and write a CSV per cell_id.
In order to run agents_to_cell_csv.py, 
you need to install 
"conda install -c conda-forge pandas geopandas shapely pyproj -y" 
and 
run "python agents_to_cell_csvs.py   --parquet "/datassd1_8tb/p2t4_iarpa_data/ta1.simulation1/trial/dev/past/agent_bucket=100/data.zstd.parquet"   --grid "/datassd4_8tb/p2t4_common_data/pushpita/GridApplication/Grid_wgs84.geojson"   --out-root "/datassd4_8tb/p2t4_common_data/datassd4_8tb/p2t4_common_data/Grid_folder"   --bucket-id 100" in stitch. 
"/datassd1_8tb/p2t4_iarpa_data/ta1.simulation1/trial/dev/past/agent_bucket=100/data.zstd.parquet" is the path for bucket file. 
"/datassd4_8tb/p2t4_common_data/pushpita/GridApplication/Grid_wgs84.geojson" is the path for the grid informantion file. 
"/datassd4_8tb/p2t4_common_data/datassd4_8tb/p2t4_common_data/Grid_folder" contains all the cells.
