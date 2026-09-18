import csv
import json
import zipfile
from pathlib import Path

# These are the columns we expect in the results.csv
REQUIRED_COLUMNS = {"image_path", "sampler", "steps", "cfg", "preset", "seed"}

def validate_csv_schema(csv_path):
    """
    Opens the CSV file and checks if it has all required columns.
    Handles missing headers and throws readable errors.
    """
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or missing a header row.")

        header_fields = set(reader.fieldnames)
        if not REQUIRED_COLUMNS.issubset(header_fields):
            missing = REQUIRED_COLUMNS - header_fields
            raise ValueError(f"Missing required columns: {missing}")

        return list(reader)

def collect_files(csv_rows):
    """
    From the rows in the CSV, grab all valid image paths.
    Filters out rows with missing or empty 'image_path' fields.
    """
    files = set()
    for idx, row in enumerate(csv_rows):
        if "image_path" not in row:
            raise ValueError(f"Row {idx} missing 'image_path' key: {row}")
        image_path = row["image_path"]
        if image_path and image_path.strip():
            files.add(image_path)
        else:
            print(f"Skipping row {idx} due to empty image_path.")
    return files

def create_report_zip(output_path="report.zip"):
    """
    This function:
    - Validates the results.csv file
    - Ensures all images listed exist and are safe
    - Packages everything into report.zip
    """
    base_dir = Path(__file__).parent
    csv_path = base_dir / "results.csv"
    config_path = base_dir / "config.json"
    readme_path = base_dir / "README.md"
    zip_path = base_dir / output_path

    # Step 1: Validate CSV
    csv_rows = validate_csv_schema(csv_path)

    # Step 2: Collect all valid image paths
    image_paths = collect_files(csv_rows)

    # Step 3: Zip all files
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(csv_path, arcname="results.csv")
        zipf.write(config_path, arcname="config.json")
        zipf.write(readme_path, arcname="README.md")

        for path in image_paths:
            norm_path = Path(path).resolve()
            # Prevent path traversal by ensuring image is inside project directory
            if ".." in path or not str(norm_path).startswith(str(base_dir.resolve())):
                raise ValueError(f"🚨 Invalid image path: {path}")

            full_path = base_dir / path
            if not full_path.exists():
                raise FileNotFoundError(f"Image not found: {full_path}")

            zipf.write(full_path, arcname=path)

    print(f"Done! Report created at: {zip_path}")

if __name__ == "__main__":
    create_report_zip()
