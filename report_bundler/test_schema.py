import csv

def test_csv_schema():
    """
    Make sure results.csv contains all required metadata columns.
    You can add more optional fields in the future if needed.
    """
    required = {"image_path", "sampler", "steps", "cfg", "preset", "seed"}

    with open("results.csv", newline='') as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames is not None, "Missing header row in CSV"
        header = set(reader.fieldnames)

        assert required.issubset(header), f"Missing columns: {required - header}"
