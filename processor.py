import multiprocessing
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps
from tqdm import tqdm

VALID_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}

# Claves del formato viejo del YAML (dict plano), para detectarlo y avisar.
LEGACY_KEYS = {"resize", "rotate", "grayscale", "brightness"}
ALLOWED_KEYS = {"pipeline", "copies"}


# ---------------------------------------------------------------------------
# Transformaciones
# Cada una recibe una imagen (+ parámetros) y devuelve una imagen nueva.
# Ninguna modifica la imagen de entrada.
# ---------------------------------------------------------------------------

def t_grayscale(img):
    img = ImageOps.grayscale(img)
    return img.convert("RGB")  # Mantener formato 3 canales por si acaso


def t_rotate(img, angle, mode="crop"):
    normalized = angle % 360
    if normalized == 0:
        return img
    if normalized in (90, 180, 270):
        return img.rotate(angle, expand=True)
    # 'fill' expande el canvas, 'crop' mantiene el tamaño original
    return img.rotate(angle, expand=(mode == "fill"), fillcolor=(0, 0, 0))


def t_resize(img, width, height, mode="stretch"):
    size = (width, height)
    if mode == "stretch":
        return img.resize(size, Image.Resampling.LANCZOS)
    if mode == "fit":
        img = img.copy()  # thumbnail modifica la imagen in place
        img.thumbnail(size, Image.Resampling.LANCZOS)
        return img
    if mode == "crop":
        return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)
    raise ValueError(f"modo de resize desconocido: '{mode}'")


def t_brightness(img, min_factor, max_factor):
    # El factor se sortea en cada llamada, así cada copia sale distinta
    factor = random.uniform(min_factor, max_factor)
    return ImageEnhance.Brightness(img).enhance(factor)


# Registro: conecta el nombre usado en el YAML ('type') con su función.
# Para sumar una transformación nueva: escribir la función y agregarla acá.
TRANSFORMS = {
    "grayscale": t_grayscale,
    "rotate": t_rotate,
    "resize": t_resize,
    "brightness": t_brightness,
}


def apply_step(img, step):
    params = dict(step)
    name = params.pop("type")
    return TRANSFORMS[name](img, **params)


def apply_pipeline(img, steps):
    """Aplica los pasos en el mismo orden en que aparecen en la lista."""
    for step in steps:
        img = apply_step(img, step)
    return img


# ---------------------------------------------------------------------------
# Validación (se hace una sola vez, antes de lanzar los procesos)
# ---------------------------------------------------------------------------

def validate_pipeline(steps):
    if not isinstance(steps, list):
        raise ValueError("'pipeline' debe ser una lista de pasos.")

    # Se prueba cada paso con una imagen mínima para detectar parámetros
    # faltantes, parámetros desconocidos o modos inválidos.
    dummy = Image.new("RGB", (8, 8))
    for n, step in enumerate(steps, start=1):
        if not isinstance(step, dict) or "type" not in step:
            raise ValueError(f"Paso #{n}: debe ser un diccionario con la clave 'type'.")
        if step["type"] not in TRANSFORMS:
            disponibles = ", ".join(TRANSFORMS)
            raise ValueError(
                f"Paso #{n}: transformación desconocida '{step['type']}'. "
                f"Disponibles: {disponibles}."
            )
        try:
            apply_step(dummy, step)
        except Exception as e:
            raise ValueError(f"Paso #{n} ('{step['type']}') inválido: {e}") from e


def validate_config(config):
    """Valida el config completo y devuelve la sección 'transformations'."""
    if not isinstance(config, dict) or not isinstance(config.get("transformations"), dict):
        raise ValueError("El config debe tener una sección 'transformations'.")
    transformations = config["transformations"]

    legacy = LEGACY_KEYS & transformations.keys()
    if legacy:
        raise ValueError(
            f"El config usa el formato anterior (claves: {', '.join(sorted(legacy))}). "
            "Ahora las transformaciones van en una lista ordenada bajo "
            "'transformations.pipeline', y cada paso lleva su 'type'."
        )

    unknown = transformations.keys() - ALLOWED_KEYS
    if unknown:
        raise ValueError(
            f"Claves desconocidas en 'transformations': {', '.join(sorted(map(str, unknown)))}. "
            f"Permitidas: {', '.join(sorted(ALLOWED_KEYS))}."
        )

    if "pipeline" not in transformations:
        raise ValueError("Falta 'transformations.pipeline' (puede ser una lista vacía).")
    validate_pipeline(transformations["pipeline"])

    copies = transformations.get("copies", 1)
    if isinstance(copies, bool) or not isinstance(copies, int) or copies < 1:
        raise ValueError("'copies' debe ser un entero mayor o igual a 1.")

    return transformations


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------

def process_single_image(input_path, output_dir, config):
    """Procesa una imagen. Devuelve None si salió bien, o un mensaje de error."""
    steps = config['pipeline']
    copies = config.get('copies', 1)
    path = Path(input_path)

    try:
        with Image.open(input_path) as img:
            img = img.convert("RGB")  # Asegurar compatibilidad de color

            for i in range(copies):
                result = apply_pipeline(img, steps)

                if copies == 1:
                    out_name = path.name
                else:
                    out_name = f"{path.stem}_aug_{i}{path.suffix}"

                result.save(os.path.join(output_dir, out_name), quality=85)
        return None

    except Exception as e:
        return f"{input_path}: {e}"


def run_pipeline(input_dir, output_dir, config):
    """Corre el pipeline sobre todas las imágenes. Devuelve la cantidad de fallos."""
    transformations = validate_config(config)

    if not os.path.isdir(input_dir):
        raise ValueError(f"El directorio de entrada no existe: {input_dir}")
    if Path(input_dir).resolve() == Path(output_dir).resolve():
        raise ValueError(
            "El directorio de salida debe ser distinto del de entrada "
            "(si no, se sobrescribirían las imágenes originales)."
        )

    os.makedirs(output_dir, exist_ok=True)

    # Obtener lista de imágenes
    images = sorted(
        os.path.join(input_dir, f) for f in os.listdir(input_dir)
        if Path(f).suffix.lower() in VALID_EXTS
    )

    total = len(images)
    if total == 0:
        print("No se encontraron imágenes válidas en el directorio de entrada.")
        return 0

    print(f"Encontradas {total} imágenes. Iniciando procesamiento en paralelo...")

    start_time = time.perf_counter()
    errors = []

    # Usar Multiprocessing con el número total de cores disponibles
    num_cores = multiprocessing.cpu_count()

    with ProcessPoolExecutor(max_workers=num_cores) as executor:
        futures = [
            executor.submit(process_single_image, img_path, output_dir, transformations)
            for img_path in images
        ]

        # Barra de progreso que se actualiza conforme cada imagen termina
        with tqdm(total=total, desc="Procesando", unit="img", file=sys.stdout) as pbar:
            for future in as_completed(futures):
                error = future.result()
                if error:
                    errors.append(error)
                    tqdm.write(f"Error procesando {error}")
                pbar.update(1)

    elapsed_time = time.perf_counter() - start_time
    if elapsed_time >= 60:
        mins, secs = divmod(elapsed_time, 60)
        time_str = f"{int(mins)}m {secs:.2f}s ({elapsed_time:.2f}s)"
    else:
        time_str = f"{elapsed_time:.2f}s"

    print(f"Procesamiento completado en {time_str}.")
    if errors:
        print(f"{len(errors)} de {total} imágenes fallaron (ver errores arriba).")

    return len(errors)