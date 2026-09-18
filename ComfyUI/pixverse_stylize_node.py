from PIL import Image

class PixVerseStylize:
    NAME = "PixVerseStylize"

    # Static set of allowed styles for fast lookups
    ALLOWED_STYLES = {
        "watercolor", "oil painting", "sketch", "manga", "cartoon",
        "cyberpunk", "pixel art", "charcoal", "realism", "pop art",
        "comic", "vintage", "pastel", "gothic", "anime", "steampunk",
        "neon", "3d render", "graffiti", "low poly"
    }

    def process(self, image: Image.Image, style: str) -> Image.Image:
        # Normalize input style for case-insensitive match
        style = style.strip().lower()
        if style not in {s.lower() for s in self.ALLOWED_STYLES}:
            raise ValueError(
                f"Unsupported style '{style}'. Supported styles: {', '.join(sorted(self.ALLOWED_STYLES))}"
            )
        return image  # Stub output for now
