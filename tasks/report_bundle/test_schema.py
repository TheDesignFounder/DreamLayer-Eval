import csv

def test_csv_schema(filename):
    required_columns = {'id', 'image_path', 'score'}
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        headers = set(reader.fieldnames)
        missing = required_columns - headers
        if missing:
            raise ValueError(f"CSV is missing required columns: {missing}")
        print("✅ CSV schema test passed!")

if __name__ == "__main__":
    test_csv_schema('results.csv')
