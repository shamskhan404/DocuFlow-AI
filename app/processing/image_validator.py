# Responsible for checking image validity (Check image dimensions, Reject excessively large images, Ensure the image is suitable for further processing).
from PIL import Image


def validate_image(
    image: Image.Image,
    min_width: int = 50,
    min_height: int = 50,
    max_pixels: int = 50_000_000
):

    width, height = image.size

    if width < min_width or height < min_height:
        raise ValueError("Image resolution is too small.")

    if width * height > max_pixels:
        raise ValueError("Image resolution exceeds allowed limit.")

    if image.mode not in ("RGB", "L"):
        raise ValueError("Unsupported image color mode.")

    return True
