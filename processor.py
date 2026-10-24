import os
import random
import sys
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from tqdm import tqdm


def process_single_image(input_path, output_dir, config):
    try:
        # 1. Abrir imagen
        with Image.open(input_path) as img:
            img = img.convert("RGB")  # Asegurar compatibilidad de color

            # 2. Grayscale
            if config.get('grayscale'):
                img = ImageOps.grayscale(img)
                img = img.convert("RGB")  # Mantener formato 3 canales por si acaso

            # 3. Rotación
            rot_config = config.get('rotate')
            if rot_config and rot_config['angle'] != 0:
                angle = rot_config['angle']
                if angle not in [90, 180, 270]:
                    expand = (rot_config.get('mode') == 'fill')
                    img = img.rotate(angle, expand=expand, fillcolor=(0, 0, 0))
                else:
                    img = img.rotate(angle, expand=True)

            # 4. Resize
            res_config = config.get('resize')
            if res_config:
                target_size = (res_config['width'], res_config['height'])
                mode = res_config.get('mode', 'stretch')

                if mode == 'stretch':
                    img = img.resize(target_size, Image.Resampling.LANCZOS)
                elif mode == 'fit':
                    img.thumbnail(target_size, Image.Resampling.LANCZOS)
                elif mode == 'crop':
                    img = ImageOps.fit(img, target_size, method=Image.Resampling.LANCZOS)

            # 5. Brillo y Guardado Múltiple
            bright_config = config.get('brightness')
            if bright_config and bright_config.get('generate_count', 0) > 0:
                enhancer = ImageEnhance.Brightness(img)
                base_name = Path(input_path).stem
                ext = Path(input_path).suffix

                for i in range(bright_config['generate_count']):
                    factor = random.uniform(bright_config['min_factor'], bright_config['max_factor'])
                    final_img = enhancer.enhance(factor)
                    out_name = f"{base_name}_aug_{i}{ext}"
                    final_img.save(os.path.join(output_dir, out_name), quality=85)
            else:
                # Si no hay variación de brillo, guardar una sola copia
                out_name = Path(input_path).name
                img.save(os.path.join(output_dir, out_name), quality=85)

        return True, None
    except Exception as e:
        print(f"\nError procesando {input_path}: {e}")
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
        futures = {
            executor.submit(process_single_image, img_path, output_dir, config['transformations']): img_path
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
