# Procesador Masivo de Imágenes

Pipeline de procesamiento y aumento de imágenes por lotes (batch processing), pensado para alto rendimiento mediante procesamiento paralelo multinúcleo (`multiprocessing`), que podés usar tanto como **herramienta CLI / Docker** como **biblioteca de Python**.

---

## 📁 Estructura del Repositorio

```text
├── Dockerfile              # Definición de la imagen del contenedor (Python 3.14-slim)
├── .dockerignore           # Archivos excluidos del contexto de compilación (incluye config.yaml)
├── config.yaml             # Archivo de configuración con los parámetros de transformación y ejecución
├── main.py                 # Punto de entrada CLI (parseo de argumentos y carga de configuración)
├── processor.py            # Motor de procesamiento en paralelo (Pillow, ProcessPoolExecutor, tqdm)
├── image_processor/        # Paquete para usar como biblioteca de Python
│   └── __init__.py         # Re-exporta process_images, run_pipeline, etc.
├── pyproject.toml          # Definición de dependencias y empaquetado del proyecto (pip/uv)
├── requirements.txt        # Dependencias congeladas para la instalación adentro del contenedor
├── tests/                  # Suite completa de pruebas unitarias e integración (pytest)
└── README.md               # Documentación técnica del proyecto
```

---

## 📦 Instalación

### Desde PyPI

Podés instalar la biblioteca en cualquier proyecto usando **uv** o **pip**:

```bash
# Con uv (recomendado)
uv add Image-pipeline-processor

# O con uv pip en un entorno virtual activo:
uv pip install Image-pipeline-processor

# O con pip tradicional:
pip install Image-pipeline-processor
```

### Instalación local para desarrollo
Si clonaste este repo y querés trabajar en modo editable:
```bash
uv pip install -e .
# o con pip:
pip install -e .
```

---

## 🐍 Uso como Biblioteca de Python

Podés importar y usar el procesador directamente en tus scripts y módulos de Python. Está disponible importando tanto `image_processor` como `processor`:

### Ejemplos de uso

#### 1. Usando un archivo de configuración YAML
```python
import image_processor  # o: import processor

# Procesa las imágenes usando el archivo config.yaml
errores = image_processor.process_images(
    input_path="ruta/a/imagenes_origen",
    output_dir="ruta/a/salida",
    config="config.yaml"
)

if not errores:
    print("Todas las imágenes se procesaron con éxito.")
else:
    print(f"Fallaron {len(errores)} imágenes:", errores)
```

#### 2. Pasando la configuración como diccionario de Python
```python
from image_processor import process_images

configuracion = {
    "copies": 2,
    "pipeline": [
        {"type": "resize", "width": 800, "height": 800, "mode": "fit"},
        {"type": "grayscale"},
        {"type": "brightness", "min_factor": 0.8, "max_factor": 1.2}
    ]
}

process_images(
    input_path="ruta/a/imagenes",
    output_dir="ruta/a/destino",
    config=configuracion,
    max_cores=4
)
```

#### 3. Procesar una imagen individual o una lista de imágenes
```python
import processor

# Una sola imagen:
processor.process_images("foto.png", "salida/", config="config.yaml")

# Lista de imágenes que elijas:
processor.process_images(["img1.jpg", "img2.png"], "salida/", config="config.yaml")
```

#### 4. Modo silencioso (sin la barra de progreso en consola)
```python
import image_processor

image_processor.process_images(
    input_path="fotos/",
    output_dir="salida/",
    config="config.yaml",
    show_progress=False
)
```

---

## ⚙️ Características Técnicas

- **Uso Dual (CLI y Biblioteca)**: Lo podés usar como biblioteca de Python (`image_processor.process_images(...)` o `processor.process_images(...)`) o mandarlo por consola vía `image-processor`, `python main.py` o Docker.
- **Procesamiento Paralelo**: Usa `ProcessPoolExecutor` repartiendo el trabajo entre los núcleos de tu CPU. Te permite limitar cuántos núcleos usar mediante el parámetro opcional `max_cores`, o tirar con todos los disponibles por defecto (`multiprocessing.cpu_count()`).
- **Pipeline de Transformaciones Secuencial**:
  - Arquitectura modular basada en un pipeline ordenado de pasos (`pipeline`), donde cada operación se aplica una tras otra en el orden exacto que definas.
  - Te permite repetir operaciones o armar secuencias como quieras (por ejemplo: achicar antes de rotar, o al revés).
  - Operaciones soportadas:
    - **Redimensionamiento (`resize`)**: Algoritmos `stretch` (deforma al tamaño exacto), `fit` (mantiene relación de aspecto) y `crop` (recorta al centro).
    - **Rotación (`rotate`)**: Ángulo que quieras con modo `fill` (agranda el lienzo para que entre toda la imagen) o `crop` (mantiene el tamaño original recortando las esquinas).
    - **Escala de grises (`grayscale`)**: Pasa la imagen a blanco y negro preservando el espacio de color de 3 canales (RGB).
    - **Ajuste de brillo (`brightness`)**: Soporta un factor fijo (`factor`) o sorteo aleatorio uniforme dentro de un rango (`min_factor` y `max_factor`).
- **Aumento de Datos (Data Augmentation)**: Control de variantes por imagen mediante el parámetro `copies`. Si ponés `copies > 0`, genera copias aumentadas con el sufijo `_aug_{i}` aplicándole el pipeline a cada una. Si ponés `0`, te genera una sola imagen con su nombre original.
- **Manejo de Errores y Diagnóstico**: Resiliencia frente a archivos corruptos o imágenes rotas sin cortar el procesamiento del lote, tirándote al final un resumen detallado de las imágenes que fallaron y por qué.
- **Compatibilidad Retroactiva**: El motor soporta tanto la sintaxis nueva de pipeline (`pipeline` y `copies`) como el formato viejo con diccionario de transformaciones, además de la función histórica `run_pipeline(...)`.
- **Configuración Desacoplada**: El archivo `config.yaml` no queda metido adentro de la imagen de Docker, así que podés tocar las reglas de procesamiento sin tener que recompilar el contenedor.
- **Barra de Progreso Interactiva**: Monitoreo en tiempo real con métricas de velocidad (img/s) y tiempo estimado (ETA) gracias a `tqdm` y futuros asíncronos (`as_completed`).

---

## 🐳 Compilación de la Imagen Docker

Para buildear la imagen localmente con el nombre `image-processor`, mandale desde la raíz del repo:

```bash
docker build -t image-processor .
```

## 🚀 Ejecución desde la Consola

El contenedor viene con un `ENTRYPOINT` que llama a `main.py`. Como el entorno corre aislado, tenés que montar las carpetas locales en el contenedor usando volúmenes (`-v`).

### Sintaxis del comando

```bash
docker run --rm \
  -v "<RUTA_LOCAL_IMAGENES_ORIGEN>:/app/input" \
  -v "<RUTA_LOCAL_DESTINO>:/app/output" \
  -v "<RUTA_LOCAL_CONFIG_YAML>:/app/config.yaml" \
  image-processor \
  -i /app/input \
  -o /app/output \
  -c /app/config.yaml
```

### Parámetros explicados:

| Parámetro Docker / CLI | Descripción |
|---|---|
| `--rm` | Borra automáticamente el contenedor apenas termina la ejecución. |
| `-v <local>:<contenedor>` | Monta una carpeta o archivo de tu máquina adentro del contenedor. |
| `-i /app/input` | Ruta interna de la carpeta donde están las imágenes a procesar. |
| `-o /app/output` | Ruta interna de la carpeta donde se van a guardar las imágenes listas. |
| `-c /app/config.yaml` | Ruta interna al archivo YAML de configuración montado. |

### Ejemplo concreto

```bash
docker run --rm \
  -v "/Users/user/Downloads/photos:/app/input" \
  -v "/Users/user/Desktop/processed:/app/output" \
  -v "$(pwd)/config.yaml:/app/config.yaml" \
  image-processor \
  -i /app/input \
  -o /app/output \
  -c /app/config.yaml
```

---

## 🛠️ Configuración (`config.yaml`)

En el archivo de configuración definís qué recursos usar, cuántas variantes sacar y la secuencia ordenada de transformaciones a aplicar:

```yaml
# Número máximo de cores a utilizar en paralelo (opcional, por defecto usa todos los disponibles)
max_cores: 4

transformations:
  # Cantidad de variantes generadas por cada imagen original
  # Si es 0, genera una sola imagen con el nombre original. Si es > 0, genera imágenes con sufijo _aug_{i}
  copies: 3

  # Pipeline secuencial: las operaciones se ejecutan en el orden estricto en que las declares; podés repetir operaciones y alternar su orden
  pipeline:
    # 1. Redimensionamiento
    - type: resize
      width: 800
      height: 800
      mode: stretch # Opciones: 'stretch' (deforma), 'fit' (aspect ratio), 'crop' (recorte central)

    # 2. Rotación
    - type: rotate
      angle: 45
      mode: crop # Opciones: 'fill' (agranda el lienzo), 'crop' (mantiene dimensiones)

    # 3. Conversión a escala de grises
    - type: grayscale

    # 4. Ajuste o variación de brillo
    - type: brightness
      min_factor: 0.5 # Factor mínimo (< 1 oscurece)
      max_factor: 1.5 # Factor máximo (> 1 aclara)
      # Nota: También podés pasarle 'factor: 1.2' para clavar un brillo constante fijo
```

### Detalle de parámetros del Pipeline

| Transformación | Parámetro | Tipo | Descripción |
|---|---|---|---|
| `resize` | `width` | Entero | Ancho objetivo en píxeles. |
| | `height` | Entero | Alto objetivo en píxeles. |
| | `mode` | String | `'stretch'` (deforma al tamaño exacto), `'fit'` (mantiene relación de aspecto), `'crop'` (recorta al centro). |
| `rotate` | `angle` | Numérico | Grados de rotación en sentido antihorario. |
| | `mode` | String | `'fill'` (agranda el lienzo), `'crop'` (conserva dimensiones originales). |
| `grayscale` | *(ninguno)* | - | Pasa la imagen a escala de grises manteniendo los 3 canales RGB. |
| `brightness` | `min_factor`, `max_factor` | Flotante | Rango para variar al azar (1.0 es original, `<1.0` oscurece, `>1.0` aclara). |
| | `factor` | Flotante | *(Opcional)* Factor fijo de brillo en vez de un rango aleatorio. |
