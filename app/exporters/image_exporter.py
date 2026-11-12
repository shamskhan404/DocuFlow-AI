from pathlib import Path
from PIL import Image


class ImageExporter:

    def __init__(self, output_dir="output/processed"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, image: Image.Image, filename: str):

        output_path = self.output_dir / filename

        image.save(output_path, format="PNG")

        print(f"Processed image saved: {output_path}")

        return output_path