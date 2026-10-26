from pathlib import Path

# Importamos la librería (instalada vía PyPI con 'Image-pipeline-processor')
# Correr "uv add Image-pipeline-processor" para instalar dependencias
import image_processor

# ===========================================================================
# Caso 1: Pasando un archivo config.yaml
# ===========================================================================
def main_con_archivo_config():
    """
    Ejemplo 1: Procesa una carpeta entera de imágenes tomando la configuración
    desde un archivo 'config.yaml'.
    """

    print("\n" + "=" * 60)
    print(" CASO 1: Procesamiento pasando parametros como archivo YAML")
    print("=" * 60)

    # Invocamos la librería pasándole la ruta del config
    fallos = image_processor.process_images(
        input_path="MercedesF1car",
        output_dir="MercedesF1car_yaml",
        config="config.yaml",
    )


# ===========================================================================
# Caso 2: Pasando los parámetros directamente en Python (dict)
# ===========================================================================
def main_con_parametros_dict():
    """
    Ejemplo 2: Procesa imágenes configurando el pipeline y la cantidad de copias
    directamente desde un diccionario de Python en memoria (sin archivos YAML).
    """

    print("\n" + "=" * 60)
    print(" CASO 2: Procesamiento pasando parametros como diccionario Python")
    print("=" * 60)

    # Definimos el pipeline y las copias en un dict
    parametros = {
        "copies": 3,  # Genera 3 variantes aumentadas (_aug_0, _aug_1, _aug_2)
        "pipeline": [
            # 1. Resize exacto deformando (stretch)
            {"type": "resize", "width": 250, "height": 250, "mode": "stretch"},
            # 2. Rotación de 45° agrandando el canvas
            {"type": "rotate", "angle": 45, "mode": "fill"},
            # 3. Variación de brillo estocástica
            {"type": "brightness", "min_factor": 0.5, "max_factor": 1.5},
        ],
    }

    fallos = image_processor.process_images(
        input_path="MercedesF1car",
        output_dir="MercedesF1car_dict",
        config=parametros,
        max_cores=4,         # Opcional: limitar uso de núcleos de CPU
        show_progress=True,  # Muestra barra de progreso tqdm
    )


# ===========================================================================
# Caso 3: Pasando fotos puntuales (archivo único o lista de rutas)
# ===========================================================================
def main_con_fotos_puntuales():
    """
    Ejemplo 3: En vez de pasarle una carpeta completa, le mandamos una foto
    específica o una lista con solo las fotos que queremos procesar.
    """
    print("\n" + "=" * 60)
    print(" CASO 3: Procesamiento pasando fotos puntuales (lista o archivo único)")
    print("=" * 60)

    pipeline_puntual = {
        "copies": 0,  # 0 = una sola imagen resultante manteniendo el nombre original
        "pipeline": [
            {"type": "resize", "width": 150, "height": 150, "mode": "crop"},
            {"type": "grayscale"},
        ],
    }

    # Opción A: Pasando una foto puntual (con su extensión .jpg)
    image_processor.process_images(
        input_path="MercedesF1car/00000004.jpg",
        output_dir="MercedesF1car_individual",
        config=pipeline_puntual,
        show_progress=False,  # Opcional: modo silencioso sin barra
    )

    # Opción B: Pasando una lista seleccionada de fotos (con su extensión .jpg)
    image_processor.process_images(
        input_path=["MercedesF1car/00000004.jpg", "MercedesF1car/00000008.jpg"],
        output_dir="MercedesF1car_lista",
        config=pipeline_puntual,
        show_progress=True,
    )


if __name__ == "__main__":
    try:
        main_con_archivo_config()
        main_con_parametros_dict()
        main_con_fotos_puntuales()
    finally:
        print("\n ¡Pruebas completadas!")
