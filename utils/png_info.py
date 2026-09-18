
from PIL import PngImagePlugin

def extract_png_metadata(image_path):
    """
    Extracts text metadata from a PNG file, even if it contains an alpha channel.

    Args:
        image_path (str): Path to the PNG image file.

    Returns:
        dict: A dictionary of key-value metadata pairs embedded in the PNG.
    """
    with open(image_path, 'rb') as f:
        img = PngImagePlugin.PngImageFile(f)
        return img.text
