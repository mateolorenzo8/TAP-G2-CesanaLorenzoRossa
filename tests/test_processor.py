import os
from pathlib import Path
from unittest.mock import patch
import multiprocessing
import pytest
import yaml
from PIL import Image

from processor import (
    process_single_image,
    run_pipeline,
    process_images,
    load_config,
    ProcessPoolExecutor,
)
import image_processor


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

    def test_error_handling_corrupted_file(self, tmp_path):
        """Verifica que un archivo corrupto capture la excepción y no cause crash."""
        corrupted_path = tmp_path / "corrupted.png"
        corrupted_path.write_bytes(b"esto no es una imagen valida")
        output_dir = tmp_path / "output_corrupt"
        output_dir.mkdir(parents=True, exist_ok=True)

        # No debe lanzar excepción
        success, error = process_single_image(str(corrupted_path), str(output_dir), {})

        assert success is False
        assert error is not None
        # No se debió generar ninguna imagen en output_dir
        assert len(list(output_dir.glob("*"))) == 0

    def test_error_handling_nonexistent_file(self, tmp_path):
        """Verifica que una ruta inexistente capture la excepción adecuadamente."""
        nonexistent_path = tmp_path / "does_not_exist.png"
        output_dir = tmp_path / "output_nonexistent"
        output_dir.mkdir(parents=True, exist_ok=True)

        success, error = process_single_image(str(nonexistent_path), str(output_dir), {})

        assert success is False
        assert error is not None


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
        # pipeline: resize(800x800, stretch) -> rotate(45, crop) -> brightness -> rotate -> grayscale
        # copies: 3
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

    def test_run_pipeline_respects_max_cores(self, tmp_path, dummy_images_dir, test_config_file):
        """Verifica que run_pipeline configure ProcessPoolExecutor con el max_cores especificado en config."""
        output_dir = tmp_path / "output_cores"
        config_path, _ = test_config_file(transformations={"brightness": {"generate_count": 0}})
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        config["max_cores"] = 1

        with patch("processor.ProcessPoolExecutor", wraps=ProcessPoolExecutor) as mock_executor:
            run_pipeline(str(dummy_images_dir), str(output_dir), config)
            assert mock_executor.call_args[1]["max_workers"] == 1

    def test_run_pipeline_default_cores_when_not_specified(self, tmp_path, dummy_images_dir, test_config_file):
        """Verifica que run_pipeline use cpu_count por defecto cuando max_cores no está definido."""
        output_dir = tmp_path / "output_default_cores"
        config_path, _ = test_config_file(transformations={"brightness": {"generate_count": 0}})
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        with patch("processor.ProcessPoolExecutor", wraps=ProcessPoolExecutor) as mock_executor:
            run_pipeline(str(dummy_images_dir), str(output_dir), config)
            assert mock_executor.call_args[1]["max_workers"] == multiprocessing.cpu_count()


class TestPipelineTransformations:
    """Pruebas unitarias e integración para el formato nuevo con pipeline y copies."""

    def test_pipeline_execution_order(self, tmp_path, dummy_image_factory):
        """Verifica que las transformaciones se ejecuten en el orden estricto del YAML."""
        # Imagen inicial 200x100
        img_path = dummy_image_factory("order_test.png", size=(200, 100))

        # Pipeline A: primero rotar 90 (200x100 -> 100x200), luego resize stretch a (50, 70) -> tamaño final (50, 70)
        output_dir_a = tmp_path / "out_order_a"
        config_a = {
            "pipeline": [
                {"type": "rotate", "angle": 90, "mode": "crop"},
                {"type": "resize", "width": 50, "height": 70, "mode": "stretch"},
            ]
        }
        process_single_image(str(img_path), str(output_dir_a), config_a)
        with Image.open(output_dir_a / "order_test.png") as img:
            assert img.size == (50, 70)

        # Pipeline B: primero resize a (50, 70), luego rotar 90 -> tamaño final debe ser (70, 50)
        output_dir_b = tmp_path / "out_order_b"
        config_b = {
            "pipeline": [
                {"type": "resize", "width": 50, "height": 70, "mode": "stretch"},
                {"type": "rotate", "angle": 90, "mode": "crop"},
            ]
        }
        process_single_image(str(img_path), str(output_dir_b), config_b)
        with Image.open(output_dir_b / "order_test.png") as img:
            assert img.size == (70, 50)

    def test_pipeline_repeating_steps(self, tmp_path, dummy_image_factory):
        """Verifica que se puedan repetir pasos de transformación en el pipeline."""
        img_path = dummy_image_factory("repeat_test.png", size=(100, 100))
        output_dir = tmp_path / "out_repeat"

        # Repetir rotación ortogonal dos veces (90 + 90 = 180) y cambiar tamaño
        config = {
            "pipeline": [
                {"type": "rotate", "angle": 90, "mode": "crop"},
                {"type": "resize", "width": 60, "height": 40, "mode": "stretch"},
                {"type": "rotate", "angle": 90, "mode": "crop"},
            ]
        }
        process_single_image(str(img_path), str(output_dir), config)
        with Image.open(output_dir / "repeat_test.png") as img:
            # 60x40 rotado 90 ortogonal queda en 40x60
            assert img.size == (40, 60)

    def test_pipeline_with_copies_and_brightness(self, tmp_path, dummy_image_factory):
        """Verifica que 'copies' genere la cantidad indicada de variantes con sufijo _aug_i."""
        img_path = dummy_image_factory("copies_test.png", size=(50, 50))
        output_dir = tmp_path / "out_copies"

        config = {
            "copies": 3,
            "pipeline": [
                {"type": "resize", "width": 30, "height": 30, "mode": "stretch"},
                {"type": "brightness", "min_factor": 0.8, "max_factor": 1.2},
            ]
        }
        process_single_image(str(img_path), str(output_dir), config)

        generated = sorted(list(output_dir.glob("*.png")))
        assert len(generated) == 3
        expected = ["copies_test_aug_0.png", "copies_test_aug_1.png", "copies_test_aug_2.png"]
        assert [f.name for f in generated] == expected

        for f in generated:
            with Image.open(f) as img:
                assert img.size == (30, 30)

    def test_pipeline_grayscale_step(self, tmp_path, dummy_image_factory):
        """Verifica que un paso grayscale en el pipeline convierta los canales adecuadamente."""
        img_path = dummy_image_factory("gray_pipe.png", size=(40, 40), color=(200, 100, 50))
        output_dir = tmp_path / "out_gray_pipe"

        config = {
            "pipeline": [
                {"type": "grayscale"},
            ]
        }
        process_single_image(str(img_path), str(output_dir), config)

        with Image.open(output_dir / "gray_pipe.png") as img:
            r, g, b = img.split()
            assert r.tobytes() == g.tobytes() == b.tobytes()

    def test_pipeline_invalid_step_type_reported(self, tmp_path, dummy_image_factory):
        """Verifica que un tipo de transformación inválido capture el error y no produzca salida."""
        img_path = dummy_image_factory("invalid_step.png", size=(40, 40))
        output_dir = tmp_path / "out_invalid_step"

        config = {
            "pipeline": [
                {"type": "desconocido_123"},
            ]
        }
        success, error = process_single_image(str(img_path), str(output_dir), config)

        assert success is False
        assert "Tipo de transformación no soportado" in error
        assert len(list(output_dir.glob("*"))) == 0

    def test_run_pipeline_with_pipeline_and_copies_yaml(self, tmp_path, dummy_images_dir):
        """Verifica la ejecución completa de run_pipeline con el nuevo formato YAML."""
        yaml_content = """
max_cores: 2
transformations:
  copies: 2
  pipeline:
    - type: resize
      width: 120
      height: 120
      mode: stretch
    - type: rotate
      angle: 90
      mode: crop
"""
        config_path = tmp_path / "new_format_config.yaml"
        config_path.write_text(yaml_content, encoding="utf-8")
        output_dir = tmp_path / "out_new_format_pipeline"

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        failed = run_pipeline(str(dummy_images_dir), str(output_dir), config)

        assert failed == []
        # dummy_images_dir tiene 4 imágenes válidas * 2 copias = 8 archivos generados
        generated = list(output_dir.glob("*"))
        assert len(generated) == 8
        for f in generated:
            with Image.open(f) as img:
                assert img.size == (120, 120)


class TestProcessImagesLibrary:
    """Pruebas específicas para el uso del paquete como biblioteca de Python."""

    def test_library_imports(self):
        """Verifica que la función process_images sea importable desde processor y desde image_processor."""
        import processor
        import image_processor

        assert hasattr(processor, "process_images")
        assert hasattr(image_processor, "process_images")
        assert callable(processor.process_images)
        assert callable(image_processor.process_images)

    def test_process_images_with_yaml_file_path(self, tmp_path, dummy_images_dir, test_config_file):
        """Verifica que process_images acepte directamente la ruta a un archivo config.yaml (str o Path)."""
        config_path, _ = test_config_file(
            transformations={
                "copies": 2,
                "pipeline": [
                    {"type": "resize", "width": 64, "height": 64, "mode": "stretch"}
                ]
            }
        )
        output_dir = tmp_path / "out_lib_yaml"

        failed = process_images(str(dummy_images_dir), output_dir, config=str(config_path), show_progress=False)

        assert failed == []
        generated = list(output_dir.glob("*"))
        assert len(generated) == 8  # 4 imagenes * 2 copias
        for f in generated:
            with Image.open(f) as img:
                assert img.size == (64, 64)

    def test_process_images_via_image_processor_package(self, tmp_path, dummy_images_dir):
        """Verifica que la invocación como biblioteca (image_processor.process_images) funcione correctamente."""
        output_dir = tmp_path / "out_lib_pkg"
        config = {
            "transformations": {
                "copies": 0,
                "pipeline": [
                    {"type": "resize", "width": 50, "height": 50, "mode": "stretch"}
                ]
            }
        }

        failed = image_processor.process_images(dummy_images_dir, output_dir, config=config, show_progress=False)

        assert failed == []
        generated = list(output_dir.glob("*"))
        assert len(generated) == 4
        for f in generated:
            with Image.open(f) as img:
                assert img.size == (50, 50)

    def test_process_images_with_dict_config_shorthand(self, tmp_path, dummy_images_dir):
        """Verifica que process_images acepte un diccionario directo con 'pipeline' sin 'transformations'."""
        output_dir = tmp_path / "out_lib_dict_shorthand"
        config = {
            "copies": 1,
            "pipeline": [
                {"type": "resize", "width": 32, "height": 32, "mode": "stretch"}
            ]
        }

        failed = process_images(str(dummy_images_dir), str(output_dir), config=config, show_progress=False)

        assert failed == []
        generated = list(output_dir.glob("*"))
        assert len(generated) == 4
        for f in generated:
            with Image.open(f) as img:
                assert img.size == (32, 32)

    def test_process_images_single_image_input(self, tmp_path, dummy_image_factory):
        """Verifica que process_images procese una sola imagen dada como ruta a archivo."""
        img_path = dummy_image_factory("solo.png", size=(100, 100))
        output_dir = tmp_path / "out_lib_single"

        config = {
            "pipeline": [
                {"type": "resize", "width": 40, "height": 40, "mode": "stretch"}
            ]
        }

        failed = process_images(str(img_path), str(output_dir), config=config, show_progress=False)

        assert failed == []
        out_file = output_dir / "solo.png"
        assert out_file.exists()
        with Image.open(out_file) as img:
            assert img.size == (40, 40)

    def test_process_images_list_of_images_input(self, tmp_path, dummy_image_factory):
        """Verifica que process_images acepte una lista explícita de rutas de imágenes."""
        img1 = dummy_image_factory("img1.png", size=(50, 50))
        img2 = dummy_image_factory("img2.png", size=(60, 60))
        output_dir = tmp_path / "out_lib_list"

        config = {"copies": 0}

        failed = process_images([img1, img2], output_dir, config=config, show_progress=False)

        assert failed == []
        assert (output_dir / "img1.png").exists()
        assert (output_dir / "img2.png").exists()

    def test_process_images_max_cores_override(self, tmp_path, dummy_images_dir):
        """Verifica que el parámetro max_cores se respete como argumento directo en process_images."""
        output_dir = tmp_path / "out_lib_cores"

        with patch("processor.ProcessPoolExecutor", wraps=ProcessPoolExecutor) as mock_executor:
            process_images(
                dummy_images_dir,
                output_dir,
                config={"copies": 0},
                max_cores=2,
                show_progress=False,
            )
            assert mock_executor.call_args[1]["max_workers"] == 2

    def test_process_images_nonexistent_input_raises(self, tmp_path):
        """Verifica que si la ruta de entrada no existe se lance FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            process_images(tmp_path / "non_existent_folder", tmp_path / "out", show_progress=False)

    def test_process_images_nonexistent_config_raises(self, tmp_path, dummy_images_dir):
        """Verifica que si la ruta al archivo de config no existe se lance FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            process_images(dummy_images_dir, tmp_path / "out", config="inexistente.yaml", show_progress=False)

    def test_process_images_invalid_config_type_raises(self, tmp_path, dummy_images_dir):
        """Verifica que pasar un tipo de configuración inválido lance TypeError."""
        with pytest.raises(TypeError):
            process_images(dummy_images_dir, tmp_path / "out", config=12345, show_progress=False)
