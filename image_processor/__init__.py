"""
image_processor: Biblioteca de procesamiento y aumento masivo de imágenes.
"""

from processor import (
    process_images,
    run_pipeline,
    process_single_image,
    apply_transformation,
    get_pipeline_and_copies,
    load_config,
)

__version__ = "0.1.0"

__all__ = [
    "process_images",
    "run_pipeline",
    "process_single_image",
    "apply_transformation",
    "get_pipeline_and_copies",
    "load_config",
]
