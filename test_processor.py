import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from processor import process_single_image, run_pipeline


class ProcessorTests(unittest.TestCase):
    def setUp(self):
        # Crea un directorio temporal aislado para cada prueba y guarda allí la imagen de entrada.
        # Así, las pruebas no modifican archivos del proyecto ni dependen de datos externos.
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        self.input_dir.mkdir()
        self.image_path = self.input_dir / "sample.png"
        Image.new("RGB", (8, 4), (100, 150, 200)).save(self.image_path)

    def tearDown(self):
        # Elimina el directorio temporal y todo su contenido al terminar cada prueba.
        self.temp_dir.cleanup()

    def process(self, transformations):
        # Los tests llaman self.process(...); aquí se ejecuta process_single_image
        # importada de processor.py con la imagen temporal y las transformaciones indicadas.
        self.output_dir.mkdir(exist_ok=True)
        process_single_image(str(self.image_path), str(self.output_dir), transformations)

    def test_grayscale_keeps_equal_rgb_channels(self):
        # Se espera sample.png con el mismo valor en rojo, verde y azul en cada píxel.
        self.process({"grayscale": True})

        with Image.open(self.output_dir / "sample.png") as result:
            red, green, blue = result.convert("RGB").getpixel((0, 0))

        self.assertEqual(red, green)
        self.assertEqual(green, blue)

    def test_right_angle_rotation_swaps_dimensions(self):
        # La salida sample.png debe medir 4x8 píxeles, con ancho y alto intercambiados.
        self.process({"rotate": {"angle": 90}})

        with Image.open(self.output_dir / "sample.png") as result:
            self.assertEqual(result.size, (4, 8))

    def test_arbitrary_rotation_expands_only_in_fill_mode(self):
        # A 45 grados, fill debe producir una salida mayor que 8x4; crop debe conservar 8x4.
        self.process({"rotate": {"angle": 45, "mode": "fill"}})
        with Image.open(self.output_dir / "sample.png") as expanded:
            self.assertGreater(expanded.width, 8)
            self.assertGreater(expanded.height, 4)

        self.output_dir.joinpath("sample.png").unlink()
        self.process({"rotate": {"angle": 45, "mode": "crop"}})
        with Image.open(self.output_dir / "sample.png") as cropped:
            self.assertEqual(cropped.size, (8, 4))

    def test_resize_stretch_uses_exact_target_dimensions(self):
        # Se espera que sample.png mida exactamente 3x5 píxeles, aunque cambie su proporción.
        self.process({"resize": {"width": 3, "height": 5, "mode": "stretch"}})

        with Image.open(self.output_dir / "sample.png") as result:
            self.assertEqual(result.size, (3, 5))

    def test_resize_fit_preserves_aspect_ratio(self):
        # En un límite de 4x4, se espera una salida de 4x2 que conserva la proporción original.
        self.process({"resize": {"width": 4, "height": 4, "mode": "fit"}})

        with Image.open(self.output_dir / "sample.png") as result:
            self.assertEqual(result.size, (4, 2))

    def test_resize_crop_fills_exact_target_dimensions(self):
        # Se espera una salida de 4x4 píxeles; el contenido sobrante se recorta.
        self.process({"resize": {"width": 4, "height": 4, "mode": "crop"}})

        with Image.open(self.output_dir / "sample.png") as result:
            self.assertEqual(result.size, (4, 4))

    def test_brightness_generates_requested_variants(self):
        # Se esperan sample_aug_0.png y sample_aug_1.png; el píxel inicial (100, 150, 200)
        # debe quedar en (150, 225, 255) al aplicar el factor fijo 1.5, con azul limitado a 255.
        self.process(
            {"brightness": {"generate_count": 2, "min_factor": 1.5, "max_factor": 1.5}}
        )

        generated_files = sorted(self.output_dir.glob("sample_aug_*.png"))
        self.assertEqual(len(generated_files), 2)
        self.assertEqual([path.name for path in generated_files], ["sample_aug_0.png", "sample_aug_1.png"])
        with Image.open(generated_files[0]) as result:
            self.assertEqual(result.convert("RGB").getpixel((0, 0)), (150, 225, 255))

    def test_pipeline_processes_supported_extensions_only(self):
        # La salida debe contener sample.png y second.webp, sin notes.txt; se usa un worker
        # para limitar recursos y se conserva la ejecución real del pipeline.
        (self.input_dir / "notes.txt").write_text("not an image")
        with Image.open(self.image_path) as image:
            image.save(self.input_dir / "second.webp")

        with patch("processor.multiprocessing.cpu_count", return_value=1):
            run_pipeline(
                str(self.input_dir),
                str(self.output_dir),
                {"transformations": {}},
            )

        self.assertEqual(
            {path.name for path in self.output_dir.iterdir()},
            {"sample.png", "second.webp"},
        )


if __name__ == "__main__":
    unittest.main()