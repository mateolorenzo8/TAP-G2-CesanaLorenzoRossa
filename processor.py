import os
import random
import sys
import time
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from tqdm import tqdm
import yaml


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
    """
    Procesa un archivo de imagen individual aplicando las transformaciones configuradas.
    Retorna una tupla (éxito: bool, error: str | None).
    """
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


def load_config(config=None):
    """
    Carga y normaliza la configuración.

    Parámetros:
        config (dict | str | Path | None):
            - Si es None: intenta cargar 'config.yaml' si existe en el directorio actual,
              o retorna un diccionario vacío.
            - Si es str o Path: lee el archivo YAML correspondiente.
            - Si es dict: devuelve una copia del diccionario.

    Retorna:
        dict: Diccionario de configuración normalizado.
    """
    if config is None:
        default_config = Path("config.yaml")
        if default_config.is_file():
            with open(default_config, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
        else:
            loaded = {}
    elif isinstance(config, (str, Path)):
        config_path = Path(config)
        if not config_path.is_file():
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
    elif isinstance(config, dict):
        loaded = dict(config)
    else:
        raise TypeError(
            f"Configuración inválida: se esperaba dict, str, Path o None, pero se recibió {type(config).__name__}"
        )

    # Si se pasaron transformaciones directamente en el nivel raíz sin clave 'transformations',
    # las encapsulamos para compatibilidad.
    if "transformations" not in loaded:
        if any(k in loaded for k in ("pipeline", "copies", "resize", "rotate", "grayscale", "brightness")):
            cores_val = loaded.get("max_cores")
            workers_val = loaded.get("max_workers")
            loaded = {
                "max_cores": cores_val,
                "max_workers": workers_val,
                "transformations": loaded,
            }

    return loaded


def process_images(
    input_path,
    output_dir,
    config=None,
    max_cores=None,
    show_progress=True,
):
    """
    Punto de entrada principal para utilizar la herramienta como biblioteca de Python.

    Parámetros:
        input_path (str | Path | list[str | Path]):
            Directorio con imágenes a procesar, ruta a un archivo de imagen individual,
            o lista de rutas de imágenes.
        output_dir (str | Path):
            Directorio donde se guardarán las imágenes procesadas.
        config (dict | str | Path | None, opcional):
            Configuración de transformaciones (diccionario, ruta a archivo YAML o None).
            Por defecto busca 'config.yaml' si existe.
        max_cores (int, opcional):
            Cantidad máxima de núcleos de CPU a utilizar. Si se omite, usa el valor de la
            configuración o todos los disponibles.
        show_progress (bool, opcional):
            Si es True, muestra la barra de progreso (tqdm) y resúmenes en consola.
            Por defecto True.

    Retorna:
        list[tuple[str, str]]: Lista de tuplas (ruta_imagen, error) para imágenes que fallaron.
                               Si todo se procesó correctamente, retorna lista vacía [].
    """
    loaded_config = load_config(config)

    if max_cores is not None:
        loaded_config['max_cores'] = max_cores

    output_dir_str = str(output_dir)
    os.makedirs(output_dir_str, exist_ok=True)

    valid_exts = {'.jpg', '.jpeg', '.png', '.webp'}

    # Resolver lista de imágenes según el tipo de input_path
    if isinstance(input_path, (list, tuple, set)):
        images = [str(p) for p in input_path if Path(p).suffix.lower() in valid_exts]
    else:
        p = Path(input_path)
        if not p.exists():
            raise FileNotFoundError(f"Directorio o archivo de entrada no encontrado: {input_path}")
        if p.is_file():
            if p.suffix.lower() in valid_exts:
                images = [str(p)]
            else:
                images = []
        elif p.is_dir():
            images = [
                os.path.join(str(p), f) for f in os.listdir(p)
                if Path(f).suffix.lower() in valid_exts
            ]
        else:
            images = []

    total = len(images)
    if total == 0:
        if show_progress:
            print("No se encontraron imágenes válidas en el directorio de entrada.")
        return []

    if show_progress:
        print(f"Encontradas {total} imágenes. Iniciando procesamiento en paralelo...")

    # Determinar el número de cores a usar
    available_cores = multiprocessing.cpu_count()
    config_cores = (
        loaded_config.get('max_cores')
        or loaded_config.get('max_workers')
        or (loaded_config.get('execution', {}).get('max_cores') if isinstance(loaded_config.get('execution'), dict) else None)
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
        transformations_config = loaded_config.get('transformations', {})
        futures = {
            executor.submit(process_single_image, img_path, output_dir_str, transformations_config): img_path
            for img_path in images
        }

        if show_progress:
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
        else:
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

    if show_progress:
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


def run_pipeline(input_dir, output_dir, config):
    """
    Ejecuta el pipeline completo de procesamiento masivo.
    Mantenido para total retrocompatibilidad.
    """
    return process_images(
        input_path=input_dir,
        output_dir=output_dir,
        config=config,
        show_progress=True,
    )
