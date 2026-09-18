"""

This script (generate_report.py) generates a ZIP archive...

This script validates the presence and structure of required files (CSV, config, README),
checks for missing images listed in results.csv, and packages all content—including the 
'grids' folder—into a single ZIP file named report.zip.

Used for reporting and archiving results of image-based evaluations.
"""

import os
import csv
import zipfile

RESULTS_FILE = 'results.csv'
CONFIG_FILE = 'config.json'
GRIDS_DIR = 'grids'
README_FILE = 'README.txt'
OUTPUT_ZIP = 'report.zip'


required_files = [RESULTS_FILE, CONFIG_FILE, README_FILE]
for file in required_files:
    if not os.path.exists(file):
        raise FileNotFoundError(f"{file} not found!")

if not os.path.isdir(GRIDS_DIR):
    raise FileNotFoundError("Grids directory not found!")


required_columns = {'id', 'image_path', 'score'}
with open(RESULTS_FILE, newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    if not required_columns.issubset(reader.fieldnames):
        raise ValueError(f"CSV missing required columns: {required_columns - set(reader.fieldnames)}")

    for row in reader:
        if not os.path.exists(row['image_path']):
            raise FileNotFoundError(f"Image file not found: {row['image_path']}")

with zipfile.ZipFile(OUTPUT_ZIP, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    zf.write(RESULTS_FILE)
    zf.write(CONFIG_FILE)
    zf.write(README_FILE)

    for foldername, subfolders, filenames in os.walk(GRIDS_DIR):
        for filename in filenames:
            file_path = os.path.join(foldername, filename)
            arcname = os.path.relpath(file_path, start='.')
            zf.write(file_path, arcname=arcname)




print("✅ report.zip created successfully!")
