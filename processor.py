import os
import random
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance
from concurrent.futures import ProcessPoolExecutor
import multiprocessing


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

    except Exception as e:
        print(f"Error procesando {input_path}: {e}")


def run_pipeline(input_dir, output_dir, config):
    os.makedirs(output_dir, exist_ok=True)

    # Obtener lista de imágenes
    valid_exts = {'.jpg', '.jpeg', '.png', '.webp'}
    images = [
        os.path.join(input_dir, f) for f in os.listdir(input_dir)
        if Path(f).suffix.lower() in valid_exts
    ]

    print(f"Encontradas {len(images)} imágenes. Procesando...")

    # Usar Multiprocessing con el número total de cores disponibles
    num_cores = multiprocessing.cpu_count()

    with ProcessPoolExecutor(max_workers=num_cores) as executor:
        # Mapeamos la función a todas las imágenes en paralelo
        futures = []
        for img_path in images:
            futures.append(
                executor.submit(process_single_image, img_path, output_dir, config['transformations'])
            )

        # Esperar a que terminen
        for future in futures:
            future.result()

    print("Procesamiento completado.")