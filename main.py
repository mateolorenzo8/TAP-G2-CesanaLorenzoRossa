import argparse
import sys

import yaml

from processor import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Procesador masivo de imágenes CLI")
    parser.add_argument("-i", "--input", required=True, help="Directorio de imágenes crudas")
    parser.add_argument("-o", "--output", required=True, help="Directorio de salida")
    parser.add_argument("-c", "--config", required=True, help="Ruta al archivo config.yaml")

    args = parser.parse_args()

    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        print(f"Error al leer el archivo de configuración: {e}")
        sys.exit(1)

    try:
        failed = run_pipeline(args.input, args.output, config)
    except ValueError as e:
        # Errores de configuración o de directorios: mensaje claro, sin traceback
        print(f"Error: {e}")
        sys.exit(1)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()