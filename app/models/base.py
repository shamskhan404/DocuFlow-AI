# Defines One architecture for diffent models..
from abc import ABC, abstractmethod


class BaseOCRModel(ABC):

    @abstractmethod
    def load(self):
        """Load the OCR model."""
        pass

    @abstractmethod
    def predict(self, image):
        """Extract text and layout information from an image."""
        pass

    @abstractmethod
    def unload(self):
        """Release model resources."""
        pass