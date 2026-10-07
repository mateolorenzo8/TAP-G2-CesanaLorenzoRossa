import os
from pathlib import Path
import pytest
import yaml
from PIL import Image


@pytest.fixture
def dummy_image_factory(tmp_path):
    """
    Factory fixture to create dummy images with custom parameters:
    filename, size, color, and target directory.
    """
    def _create_image(filename="dummy.png", size=(100, 60), color=(255, 100, 50), directory=None):
        target_dir = Path(directory) if directory else (tmp_path / "input_images")
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename
        
        img = Image.new("RGB", size, color=color)
        img.save(file_path)
        return file_path

    return _create_image


@pytest.fixture
def dummy_images_dir(tmp_path, dummy_image_factory):
    """
    Creates a directory populated with multiple valid dummy images
    in various supported formats (.jpg, .jpeg, .png, .webp)
    plus non-image files to test filtering.
    """
    input_dir = tmp_path / "dataset"
    input_dir.mkdir(parents=True, exist_ok=True)

    # Valid dummy images
    dummy_image_factory("sample1.jpg", size=(120, 80), color=(200, 50, 50), directory=input_dir)
    dummy_image_factory("sample2.jpeg", size=(150, 100), color=(50, 200, 50), directory=input_dir)
    dummy_image_factory("sample3.png", size=(200, 120), color=(50, 50, 200), directory=input_dir)
    dummy_image_factory("sample4.webp", size=(90, 90), color=(255, 255, 0), directory=input_dir)

    # Non-image files that should be ignored by run_pipeline
    (input_dir / "ignored_notes.txt").write_text("Not an image file", encoding="utf-8")
    (input_dir / "data.csv").write_text("id,val\n1,2", encoding="utf-8")

    return input_dir


@pytest.fixture
def test_config_file(tmp_path):
    """
    Factory fixture to write a temporary YAML configuration file.
    """
    def _create_config(transformations=None, filename="test_config.yaml"):
        if transformations is None:
            transformations = {
                "resize": {"width": 200, "height": 200, "mode": "stretch"},
                "rotate": {"angle": 90, "mode": "crop"},
                "grayscale": False,
                "brightness": {
                    "generate_count": 2,
                    "min_factor": 0.8,
                    "max_factor": 1.2
                }
            }
        
        config_data = {"transformations": transformations}
        config_path = tmp_path / filename
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)
        
        return config_path, config_data

    return _create_config


@pytest.fixture
def project_config_path():
    """
    Returns the Path to the project's root config.yaml.
    """
    config_path = Path(__file__).parent.parent / "config.yaml"
    assert config_path.exists(), f"El archivo config.yaml no se encontró en {config_path}"
    return config_path
