
# Responsible for optional image transformations:
# - Resize oversized images
# - Perform optional grayscale conversion
# - Apply image enhancement
# - Prepare images for downstream processing
# - Preserve original images to avoid losing useful visual information

from PIL import Image, ImageEnhance, ImageFilter


def preprocess_image(
    image: Image.Image,
    max_dimension: int = 3000,
    grayscale: bool = False,
    enhance: bool = True,
    contrast_factor: float = 1.2,
    sharpness_factor: float = 1.3
) -> Image.Image:

    # Work on a copy to preserve the original image
    processed = image.copy()

    # 1. Resize only when the image exceeds the limit
    width, height = processed.size

    if max(width, height) > max_dimension:

        scale = max_dimension / max(width, height)

        new_size = (
            int(width * scale),
            int(height * scale)
        )

        processed = processed.resize(
            new_size,
            Image.Resampling.LANCZOS
        )

    # 2. Optional grayscale conversion
    if grayscale:
        processed = processed.convert("L")

    # 3. Image enhancement
    if enhance:

        # Improve contrast
        processed = ImageEnhance.Contrast(
            processed
        ).enhance(contrast_factor)

        # Improve sharpness
        processed = ImageEnhance.Sharpness(
            processed
        ).enhance(sharpness_factor)

    return processed
