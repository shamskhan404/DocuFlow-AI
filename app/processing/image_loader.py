# Responsible for (loading images, Check file existence, Load images using Pillow, Correct EXIF orientation, Convert images into RGB format.
from pathlib import Path
from PIL import Image, ImageOps


SUPPORTED_FORMATS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
    ".webp"
}


def load_image(image_path: str) -> Image.Image:

    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported image format: {path.suffix}")

    with Image.open(path) as image:

        image = ImageOps.exif_transpose(image)

        # Standardize color representation
        image = image.convert("RGB")

        return image.copy()
