import sys
import os
import tempfile
from PIL import Image, PngImagePlugin

# Ensure the parent directory is in the path to allow local imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the metadata extraction function
from utils.png_info import extract_png_metadata

def run_test():
    # Create a temporary file path for the test PNG
    temp_dir = tempfile.gettempdir()
    png_path = os.path.join(temp_dir, "test_transparent.png")

    # Create an RGBA image with transparency
    img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))  # Red square with alpha

    # Add metadata to the PNG
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Description", "Test image with alpha channel")

    # Save the image with metadata
    img.save(png_path, "PNG", pnginfo=meta)

    # Extract metadata using the target function
    metadata = extract_png_metadata(png_path)

    # Output and assertions
    print("\n Metadata returned by parser:", metadata)
    assert "Description" in metadata, "Description key not found in metadata"
    assert metadata["Description"] == "Test image with alpha channel", "Description value mismatch"
    print("Test passed: Metadata extracted successfully.\n")

if __name__ == "__main__":
    run_test()
