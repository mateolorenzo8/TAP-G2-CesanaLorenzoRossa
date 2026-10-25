import os
import random
import sys
import time
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from tqdm import tqdm


def apply_transformation(img, step):
    """Aplica una transformación individual sobre la imagen."""
    trans_type = str(step.get('type', '')).lower().strip()

    if trans_type == 'grayscale':
        img = ImageOps.grayscale(img)
        return img.convert("RGB")

    elif trans_type == 'rotate':
        angle = step.get('angle', 0)
        if angle != 0:
            if angle not in [90, 180, 270]:
                expand = (step.get('mode') == 'fill')
                return img.rotate(angle, expand=expand, fillcolor=(0, 0, 0))
            else:
                return img.rotate(angle, expand=True)
        return img

    elif trans_type == 'resize':
        target_size = (step['width'], step['height'])
        mode = step.get('mode', 'stretch')
        if mode == 'stretch':
            return img.resize(target_size, Image.Resampling.LANCZOS)
        elif mode == 'fit':
            img_copy = img.copy()
            img_copy.thumbnail(target_size, Image.Resampling.LANCZOS)
            return img_copy
        elif mode == 'crop':
            return ImageOps.fit(img, target_size, method=Image.Resampling.LANCZOS)
        else:
            raise ValueError(f"Modo de resize no válido: {mode}")

    elif trans_type == 'brightness':
        enhancer = ImageEnhance.Brightness(img)
        if 'min_factor' in step and 'max_factor' in step:
            factor = random.uniform(step['min_factor'], step['max_factor'])
        elif 'factor' in step:
            factor = step['factor']
        else:
            factor = 1.0
        return enhancer.enhance(factor)

    else:
        raise ValueError(f"Tipo de transformación no soportado: '{trans_type}'")


def get_pipeline_and_copies(config):
    """
    Normaliza la configuración de transformaciones.
    Soporta tanto el nuevo formato con 'pipeline' y 'copies'
    como el formato legacy para retrocompatibilidad.
    """
    if not config:
        return [], 0

    # Nuevo formato: lista ordenada de pasos bajo 'pipeline'
    if "pipeline" in config:
        pipeline = config.get("pipeline") or []
        copies = config.get("copies", 0)
        return pipeline, copies

    # Formato anterior (compatibilidad): orden fijo grayscale -> rotate -> resize -> brightness
    pipeline = []
    if config.get('grayscale'):
        pipeline.append({'type': 'grayscale'})

    rot_config = config.get('rotate')
    if rot_config and rot_config.get('angle', 0) != 0:
        pipeline.append({'type': 'rotate', **rot_config})

    res_config = config.get('resize')
    if res_config:
        pipeline.append({'type': 'resize', **res_config})

    bright_config = config.get('brightness')
    copies = 0
    if bright_config:
        copies = bright_config.get('generate_count', 0)
        if copies > 0:
            pipeline.append({'type': 'brightness', **bright_config})

    return pipeline, copies


def process_single_image(input_path, output_dir, config):
    try:
        pipeline, copies = get_pipeline_and_copies(config)

        # 1. Abrir imagen
        with Image.open(input_path) as img:
            base_img = img.convert("RGB")  # Asegurar compatibilidad de color
            base_name = Path(input_path).stem
            ext = Path(input_path).suffix

            os.makedirs(output_dir, exist_ok=True)

            if copies > 0:
                for i in range(copies):
                    current_img = base_img.copy()
                    for step in pipeline:
                        current_img = apply_transformation(current_img, step)
                    out_name = f"{base_name}_aug_{i}{ext}"
                    current_img.save(os.path.join(output_dir, out_name), quality=85)
            else:
                current_img = base_img.copy()
                for step in pipeline:
                    current_img = apply_transformation(current_img, step)
                out_name = Path(input_path).name
                current_img.save(os.path.join(output_dir, out_name), quality=85)

        return True, None
    except Exception as e:
        return False, str(e)


def run_pipeline(input_dir, output_dir, config):
    os.makedirs(output_dir, exist_ok=True)

    # Obtener lista de imágenes
    valid_exts = {'.jpg', '.jpeg', '.png', '.webp'}
    images = [
        os.path.join(input_dir, f) for f in os.listdir(input_dir)
        if Path(f).suffix.lower() in valid_exts
    ]

    total = len(images)
    if total == 0:
        print("No se encontraron imágenes válidas en el directorio de entrada.")
        return []

    print(f"Encontradas {total} imágenes. Iniciando procesamiento en paralelo...")

    # Determinar el número de cores a usar (configurable desde config.yaml con 'max_cores')
    available_cores = multiprocessing.cpu_count()
    config_cores = (
        config.get('max_cores')
        or config.get('max_workers')
        or (config.get('execution', {}).get('max_cores') if isinstance(config.get('execution'), dict) else None)
    )

    if config_cores is not None:
        try:
            config_cores = int(config_cores)
            if config_cores > 0:
                num_cores = min(config_cores, available_cores)
            else:
                num_cores = available_cores
        except (ValueError, TypeError):
            num_cores = available_cores
    else:
        num_cores = available_cores

    failed_images = []
    with ProcessPoolExecutor(max_workers=num_cores) as executor:
        transformations_config = config.get('transformations', {})
        futures = {
            executor.submit(process_single_image, img_path, output_dir, transformations_config): img_path
            for img_path in images
        }

        # Barra de progreso que se actualiza conforme cada imagen termina
        with tqdm(total=total, desc="Procesando", unit="img", file=sys.stdout) as pbar:
            for future in as_completed(futures):
                img_path = futures[future]
                try:
                    result = future.result()
                    if isinstance(result, tuple):
                        success, error = result
                        if not success:
                            failed_images.append((img_path, error))
                    elif result is False:
                        failed_images.append((img_path, "Error desconocido"))
                except Exception as exc:
                    failed_images.append((img_path, str(exc)))
                pbar.update(1)

    print("Procesamiento completado.")
    if failed_images:
        failed_images.sort(key=lambda x: str(x[0]))
        print(f"\nImágenes que fallaron ({len(failed_images)}/{total}):")
        for img_path, err in failed_images:
            if err:
                print(f" - {img_path}: {err}")
            else:
                print(f" - {img_path}")
    else:
        print("Todas las imágenes se procesaron correctamente.")

    return failed_images
