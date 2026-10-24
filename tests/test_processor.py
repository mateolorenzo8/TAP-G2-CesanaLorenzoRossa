import os
from pathlib import Path
import pytest
import yaml
from PIL import Image

from processor import process_single_image, run_pipeline


class TestProcessSingleImage:
    """Pruebas unitarias para la función process_single_image."""

    def test_process_without_transformations(self, tmp_path, dummy_image_factory):
        """Verifica que sin transformaciones se copia la imagen preservando modo RGB."""
        img_path = dummy_image_factory("original.png", size=(120, 80), color=(100, 150, 200))
        output_dir = tmp_path / "output_basic"
        output_dir.mkdir(parents=True, exist_ok=True)

        config = {}
        process_single_image(str(img_path), str(output_dir), config)

        out_path = output_dir / "original.png"
        assert out_path.exists(), "La imagen de salida debería existir"

        with Image.open(out_path) as out_img:
            assert out_img.size == (120, 80)
            assert out_img.mode == "RGB"

    def test_grayscale_transformation(self, tmp_path, dummy_image_factory):
        """Verifica que la transformación a escala de grises iguala los canales R, G y B."""
        # Creamos una imagen dummy con colores bien diferenciados (R=255, G=50, B=20)
        img_path = dummy_image_factory("color.png", size=(50, 50), color=(255, 50, 20))
        output_dir = tmp_path / "output_grayscale"
        output_dir.mkdir(parents=True, exist_ok=True)

        config = {"grayscale": True}
        process_single_image(str(img_path), str(output_dir), config)

        out_path = output_dir / "color.png"
        assert out_path.exists()

        with Image.open(out_path) as out_img:
            assert out_img.mode == "RGB"
            # En escala de grises representada en RGB, todos los canales deben ser idénticos
            r_band, g_band, b_band = out_img.split()
            assert r_band.tobytes() == g_band.tobytes() == b_band.tobytes()

    @pytest.mark.parametrize("angle, expected_size", [
        (90, (60, 100)),
        (180, (100, 60)),
        (270, (60, 100)),
    ])
    def test_rotate_orthogonal(self, tmp_path, dummy_image_factory, angle, expected_size):
        """Verifica rotaciones ortogonales (90, 180, 270) con expansión de dimensiones."""
        img_path = dummy_image_factory("orthogonal.png", size=(100, 60))
        output_dir = tmp_path / f"output_rot_{angle}"
        output_dir.mkdir(parents=True, exist_ok=True)

        config = {"rotate": {"angle": angle, "mode": "crop"}}
        process_single_image(str(img_path), str(output_dir), config)

        out_path = output_dir / "orthogonal.png"
        assert out_path.exists()

        with Image.open(out_path) as out_img:
            assert out_img.size == expected_size

    def test_rotate_arbitrary_angle_crop_vs_fill(self, tmp_path, dummy_image_factory):
        """Verifica que modo 'fill' expande el canvas y modo 'crop' mantiene el tamaño original."""
        img_path = dummy_image_factory("arbitrary.png", size=(100, 60))

        # 1. Modo 'crop' (expand=False)
        output_crop = tmp_path / "output_rot_crop"
        output_crop.mkdir(parents=True, exist_ok=True)
        config_crop = {"rotate": {"angle": 45, "mode": "crop"}}
        process_single_image(str(img_path), str(output_crop), config_crop)

        with Image.open(output_crop / "arbitrary.png") as img_crop:
            assert img_crop.size == (100, 60), "El modo 'crop' debe conservar las dimensiones originales"

        # 2. Modo 'fill' (expand=True)
        output_fill = tmp_path / "output_rot_fill"
        output_fill.mkdir(parents=True, exist_ok=True)
        config_fill = {"rotate": {"angle": 45, "mode": "fill"}}
        process_single_image(str(img_path), str(output_fill), config_fill)

        with Image.open(output_fill / "arbitrary.png") as img_fill:
            # Al rotar 45° con expand=True, el bounding box resultante es mayor
            assert img_fill.size[0] > 100 and img_fill.size[1] > 60

    def test_rotate_zero_angle(self, tmp_path, dummy_image_factory):
        """Verifica que ángulo 0 no altera la rotación ni dimensiones."""
        img_path = dummy_image_factory("rot_zero.png", size=(80, 50))
        output_dir = tmp_path / "output_rot_zero"
        output_dir.mkdir(parents=True, exist_ok=True)

        config = {"rotate": {"angle": 0, "mode": "fill"}}
        process_single_image(str(img_path), str(output_dir), config)

        with Image.open(output_dir / "rot_zero.png") as out_img:
            assert out_img.size == (80, 50)

    def test_resize_stretch(self, tmp_path, dummy_image_factory):
        """Verifica que resize con modo 'stretch' deforma al tamaño exacto."""
        img_path = dummy_image_factory("stretch.png", size=(200, 100))
        output_dir = tmp_path / "output_stretch"
        output_dir.mkdir(parents=True, exist_ok=True)

        config = {"resize": {"width": 80, "height": 80, "mode": "stretch"}}
        process_single_image(str(img_path), str(output_dir), config)

        with Image.open(output_dir / "stretch.png") as out_img:
            assert out_img.size == (80, 80)

    def test_resize_crop(self, tmp_path, dummy_image_factory):
        """Verifica que resize con modo 'crop' recorta ajustando al tamaño objetivo."""
        img_path = dummy_image_factory("crop.png", size=(300, 150))
        output_dir = tmp_path / "output_crop"
        output_dir.mkdir(parents=True, exist_ok=True)

        config = {"resize": {"width": 100, "height": 100, "mode": "crop"}}
        process_single_image(str(img_path), str(output_dir), config)

        with Image.open(output_dir / "crop.png") as out_img:
            assert out_img.size == (100, 100)

    def test_resize_fit(self, tmp_path, dummy_image_factory):
        """Verifica que resize con modo 'fit' mantiene la relación de aspecto sin sobrepasar los límites."""
        # Imagen original 200x100 (relación 2:1)
        img_path = dummy_image_factory("fit.png", size=(200, 100))
        output_dir = tmp_path / "output_fit"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Si el tamaño objetivo es 100x100, para mantener 2:1 debe quedar en 100x50
        config = {"resize": {"width": 100, "height": 100, "mode": "fit"}}
        process_single_image(str(img_path), str(output_dir), config)

        with Image.open(output_dir / "fit.png") as out_img:
            assert out_img.size == (100, 50)

    def test_brightness_augmentation(self, tmp_path, dummy_image_factory):
        """Verifica que se generen 'generate_count' copias con los sufijos esperados."""
        img_path = dummy_image_factory("bright.png", size=(50, 50))
        output_dir = tmp_path / "output_bright"
        output_dir.mkdir(parents=True, exist_ok=True)

        count = 3
        config = {
            "brightness": {
                "generate_count": count,
                "min_factor": 0.5,
                "max_factor": 1.5
            }
        }
        process_single_image(str(img_path), str(output_dir), config)

        generated_files = sorted(list(output_dir.glob("*.png")))
        assert len(generated_files) == count

        expected_names = [f"bright_aug_{i}.png" for i in range(count)]
        actual_names = [f.name for f in generated_files]
        assert actual_names == expected_names

        # La imagen original no debe estar presente como copia simple
        assert not (output_dir / "bright.png").exists()

    def test_brightness_disabled_zero_count(self, tmp_path, dummy_image_factory):
        """Verifica que con generate_count=0 se genera una única copia con nombre original."""
        img_path = dummy_image_factory("nobright.png", size=(50, 50))
        output_dir = tmp_path / "output_nobright"
        output_dir.mkdir(parents=True, exist_ok=True)

        config = {
            "brightness": {
                "generate_count": 0,
                "min_factor": 0.5,
                "max_factor": 1.5
            }
        }
        process_single_image(str(img_path), str(output_dir), config)

        generated_files = list(output_dir.glob("*.png"))
        assert len(generated_files) == 1
        assert generated_files[0].name == "nobright.png"

    @pytest.mark.parametrize("extension", [".jpg", ".jpeg", ".png", ".webp"])
    def test_supported_image_formats(self, tmp_path, dummy_image_factory, extension):
        """Verifica que process_single_image procese adecuadamente cada formato soportado."""
        filename = f"sample{extension}"
        img_path = dummy_image_factory(filename, size=(80, 80))
        output_dir = tmp_path / f"output_{extension.strip('.')}"
        output_dir.mkdir(parents=True, exist_ok=True)

        config = {"resize": {"width": 40, "height": 40, "mode": "stretch"}}
        process_single_image(str(img_path), str(output_dir), config)

        out_path = output_dir / filename
        assert out_path.exists()
        with Image.open(out_path) as out_img:
            assert out_img.size == (40, 40)

    def test_error_handling_corrupted_file(self, tmp_path, capsys):
        """Verifica que un archivo corrupto capture la excepción y no cause crash."""
        corrupted_path = tmp_path / "corrupted.png"
        corrupted_path.write_bytes(b"esto no es una imagen valida")
        output_dir = tmp_path / "output_corrupt"
        output_dir.mkdir(parents=True, exist_ok=True)

        # No debe lanzar excepción
        process_single_image(str(corrupted_path), str(output_dir), {})

        captured = capsys.readouterr()
        assert "Error procesando" in captured.out
        # No se debió generar ninguna imagen en output_dir
        assert len(list(output_dir.glob("*"))) == 0

    def test_error_handling_nonexistent_file(self, tmp_path, capsys):
        """Verifica que una ruta inexistente capture la excepción adecuadamente."""
        nonexistent_path = tmp_path / "does_not_exist.png"
        output_dir = tmp_path / "output_nonexistent"
        output_dir.mkdir(parents=True, exist_ok=True)

        process_single_image(str(nonexistent_path), str(output_dir), {})

        captured = capsys.readouterr()
        assert "Error procesando" in captured.out


class TestRunPipeline:
    """Pruebas de integración para la función run_pipeline."""

    def test_run_pipeline_with_custom_config_yaml(self, tmp_path, dummy_images_dir, test_config_file):
        """Verifica la ejecución del pipeline completo a partir de un archivo YAML generado."""
        config_path, config_data = test_config_file(
            transformations={
                "resize": {"width": 100, "height": 100, "mode": "stretch"},
                "rotate": {"angle": 90, "mode": "crop"},
                "grayscale": False,
                "brightness": {
                    "generate_count": 2,
                    "min_factor": 0.9,
                    "max_factor": 1.1
                }
            }
        )

        output_dir = tmp_path / "pipeline_output"

        # Leemos el archivo YAML como se haría en producción
        with open(config_path, "r", encoding="utf-8") as f:
            loaded_config = yaml.safe_load(f)

        run_pipeline(str(dummy_images_dir), str(output_dir), loaded_config)

        # dummy_images_dir contiene 4 imágenes válidas (.jpg, .jpeg, .png, .webp)
        # Con generate_count: 2 se deben haber generado 4 * 2 = 8 imágenes
        output_files = [f for f in output_dir.iterdir() if f.is_file()]
        assert len(output_files) == 8

        # Verificar que los archivos generados tienen las dimensiones del resize
        for f in output_files:
            with Image.open(f) as img:
                # Rotación 90 luego resize a (100, 100) -> tamaño final debe ser (100, 100)
                assert img.size == (100, 100)

    def test_run_pipeline_filters_unsupported_files(self, tmp_path, dummy_images_dir, test_config_file):
        """Verifica que run_pipeline omita archivos que no sean imágenes válidas (.txt, .csv)."""
        config_path, _ = test_config_file(
            transformations={"brightness": {"generate_count": 0}}
        )

        output_dir = tmp_path / "pipeline_filter_output"

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        run_pipeline(str(dummy_images_dir), str(output_dir), config)

        output_filenames = [f.name for f in output_dir.iterdir() if f.is_file()]
        assert len(output_filenames) == 4
        assert "ignored_notes.txt" not in output_filenames
        assert "data.csv" not in output_filenames

    def test_run_pipeline_creates_output_directory(self, tmp_path, dummy_images_dir, test_config_file):
        """Verifica que run_pipeline cree automáticamente el directorio de salida si no existe."""
        nested_output_dir = tmp_path / "nested" / "deeply" / "output_dir"
        assert not nested_output_dir.exists()

        config_path, _ = test_config_file(
            transformations={"brightness": {"generate_count": 1, "min_factor": 1.0, "max_factor": 1.0}}
        )

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        run_pipeline(str(dummy_images_dir), str(nested_output_dir), config)

        assert nested_output_dir.exists()
        assert len(list(nested_output_dir.iterdir())) > 0

    def test_run_pipeline_empty_directory(self, tmp_path, test_config_file, capsys):
        """Verifica que run_pipeline maneje directorios sin imágenes sin arrojar excepciones."""
        empty_input_dir = tmp_path / "empty_dir"
        empty_input_dir.mkdir(parents=True, exist_ok=True)
        output_dir = tmp_path / "empty_output"

        config_path, _ = test_config_file()
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        run_pipeline(str(empty_input_dir), str(output_dir), config)

        captured = capsys.readouterr()
        assert "No se encontraron imágenes válidas" in captured.out
        # El directorio de salida no debe tener imágenes
        assert len(list(output_dir.glob("*"))) == 0

    def test_run_pipeline_with_project_config_yaml(self, tmp_path, dummy_images_dir, project_config_path):
        """
        Prueba de integración directa con el archivo de configuración real 'config.yaml' del repositorio.
        Asegura compatibilidad entre la configuración del proyecto y el procesamiento sobre imágenes dummy.
        """
        output_dir = tmp_path / "project_config_output"

        with open(project_config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        run_pipeline(str(dummy_images_dir), str(output_dir), config)

        # En config.yaml:
        # resize: width=800, height=800, mode="stretch"
        # rotate: angle=45, mode="crop"
        # brightness: generate_count=3
        # 4 imágenes dummy de entrada * 3 aumentos = 12 imágenes generadas
        output_files = list(output_dir.glob("*"))
        assert len(output_files) == 12

        # Comprobamos que las imágenes resultantes cumplan las propiedades configuradas
        for out_file in output_files:
            with Image.open(out_file) as img:
                assert img.size == (800, 800)
                assert img.mode == "RGB"

    def test_run_pipeline_reports_failed_images(self, tmp_path, dummy_image_factory, test_config_file, capsys):
        """Verifica que run_pipeline reporte e identifique al final las imágenes que fallaron."""
        input_dir = tmp_path / "mixed_dataset"
        input_dir.mkdir(parents=True, exist_ok=True)
        dummy_image_factory("ok1.png", size=(50, 50), directory=input_dir)

        # Archivo con extensión de imagen válida pero contenido corrupto
        corrupt_file = input_dir / "corrupt.png"
        corrupt_file.write_bytes(b"datos corruptos no imagen")

        output_dir = tmp_path / "output_mixed"
        config_path, _ = test_config_file(transformations={"brightness": {"generate_count": 0}})
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        failed_images = run_pipeline(str(input_dir), str(output_dir), config)

        captured = capsys.readouterr()
        assert "Imágenes que fallaron (1/2):" in captured.out
        assert "corrupt.png" in captured.out
        assert len(failed_images) == 1
        assert str(corrupt_file) == failed_images[0][0]

    def test_run_pipeline_reports_all_success(self, tmp_path, dummy_images_dir, test_config_file, capsys):
        """Verifica que run_pipeline reporte éxito total cuando todas las imágenes se procesan correctamente."""
        output_dir = tmp_path / "output_all_success"
        config_path, _ = test_config_file(transformations={"brightness": {"generate_count": 0}})
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        failed_images = run_pipeline(str(dummy_images_dir), str(output_dir), config)

        captured = capsys.readouterr()
        assert "Todas las imágenes se procesaron correctamente." in captured.out
        assert failed_images == []
