# Procesador Masivo de Imágenes CLI

Pipeline de procesamiento y aumento de imágenes por lotes (batch processing), diseñado para alto rendimiento mediante procesamiento paralelo multinúcleo (`multiprocessing`), completamente contenerizado con **Docker** y desacoplado de su configuración.

---

## 📁 Estructura del Repositorio

```text
├── Dockerfile          # Definición de la imagen del contenedor (Python 3.14-slim)
├── .dockerignore       # Archivos excluidos del contexto de compilación (incluye config.yaml)
├── config.yaml         # Archivo de configuración con los parámetros de transformación y ejecución
├── main.py             # Punto de entrada CLI (parseo de argumentos y carga de configuración)
├── processor.py        # Motor de procesamiento en paralelo (Pillow, ProcessPoolExecutor, tqdm)
├── pyproject.toml      # Definición de dependencias del proyecto (uv/pip)
├── requirements.txt    # Dependencias congeladas para la instalación dentro del contenedor
└── README.md           # Documentación técnica del proyecto
```

---

## ⚙️ Características Técnicas

- **Procesamiento Paralelo**: Utiliza `ProcessPoolExecutor` distribuyendo la carga de trabajo entre núcleos de CPU. Permite limitar la cantidad de núcleos en uso mediante el parámetro opcional `max_cores` o utilizar todos los disponibles por defecto (`multiprocessing.cpu_count()`).
- **Pipeline de Transformaciones Secuencial**:
  - Arquitectura modular basada en un pipeline ordenado de pasos (`pipeline`), donde cada operación se aplica de forma sucesiva en el orden especificado.
  - Permite repetir operaciones o definir secuencias arbitrarias (por ejemplo: redimensionar antes de rotar, o viceversa).
  - Operaciones soportadas:
    - **Redimensionamiento (`resize`)**: Algoritmos `stretch` (deforma al tamaño exacto), `fit` (mantiene relación de aspecto) y `crop` (recorta al centro).
    - **Rotación (`rotate`)**: Ángulo arbitrario con modo `fill` (expande el lienzo para incluir toda la imagen) o `crop` (conserva las dimensiones originales recortando esquinas).
    - **Escala de grises (`grayscale`)**: Conversión a blanco y negro preservando el espacio de color de 3 canales (RGB).
    - **Ajuste de brillo (`brightness`)**: Soporta factor fijo (`factor`) o muestreo aleatorio uniforme dentro de un rango (`min_factor` y `max_factor`).
- **Aumento de Datos (Data Augmentation)**: Control de variantes por imagen mediante el parámetro `copies`. Si `copies > 0`, se generan copias aumentadas con sufijo `_aug_{i}` aplicando el pipeline a cada una. Si es `0`, se genera una única imagen con su nombre original.
- **Manejo de Errores y Diagnóstico**: Resiliencia frente a archivos corruptos o imágenes dañadas sin interrumpir el procesamiento en lote, con un resumen detallado al finalizar de las imágenes que fallaron y el motivo del error.
- **Compatibilidad Retroactiva**: El motor admite tanto la nueva sintaxis de pipeline (`pipeline` y `copies`) como el formato anterior basado en diccionario de transformaciones.
- **Configuración Desacoplada**: El archivo `config.yaml` no reside dentro de la imagen de Docker, permitiendo modificar las reglas de procesamiento sin recompilar el contenedor.
- **Barra de Progreso Interactiva**: Monitoreo en tiempo real con métricas de velocidad (img/s) y tiempo estimado (ETA) mediante `tqdm` y futuros asíncronos (`as_completed`).

---

## 🐳 Compilación de la Imagen Docker

Para construir la imagen localmente bajo el nombre `image-processor`, ejecuta desde la raíz del repositorio:

```bash
docker build -t image-processor .
```

## 🚀 Ejecución desde la Consola

El contenedor está configurado con un `ENTRYPOINT` que invoca a `main.py`. Debido a que el entorno de ejecución está aislado, las rutas locales deben montarse en el contenedor usando volúmenes (`-v`).

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
| `--rm` | Elimina automáticamente el contenedor al finalizar la ejecución. |
| `-v <local>:<contenedor>` | Monta un directorio o archivo del sistema anfitrión dentro del contenedor. |
| `-i /app/input` | Ruta interna del directorio donde se encuentran las imágenes de entrada. |
| `-o /app/output` | Ruta interna del directorio donde se guardarán las imágenes procesadas. |
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

El archivo de configuración define los recursos a emplear, la cantidad de variantes y la secuencia ordenada de transformaciones a aplicar:

```yaml
# Número máximo de cores a utilizar en paralelo (opcional, por defecto usa todos los disponibles)
max_cores: 4

transformations:
  # Cantidad de variantes generadas por cada imagen original
  # Si es 0, genera una sola imagen con el nombre original. Si es > 0, genera imágenes con sufijo _aug_{i}
  copies: 3

  # Pipeline secuencial: las operaciones se ejecutan en el orden estricto en que se declaran, se pueden repetir operaciones y alternar su órden
  pipeline:
    # 1. Redimensionamiento
    - type: resize
      width: 800
      height: 800
      mode: stretch # Opciones: 'stretch' (deforma), 'fit' (aspect ratio), 'crop' (recorte central)

    # 2. Rotación
    - type: rotate
      angle: 45
      mode: crop # Opciones: 'fill' (expande el lienzo), 'crop' (conserva dimensiones)

    # 3. Conversión a escala de grises
    - type: grayscale

    # 4. Ajuste o variación de brillo
    - type: brightness
      min_factor: 0.5 # Factor mínimo (< 1 oscurece)
      max_factor: 1.5 # Factor máximo (> 1 aclara)
      # Nota: También admite 'factor: 1.2' para aplicar un brillo constante fijo
    
    # 5. Ajuste de escala de grises
    - type: grayscale
```

### Detalle de parámetros del Pipeline

| Transformación | Parámetro | Tipo | Descripción |
|---|---|---|---|
| `resize` | `width` | Entero | Ancho objetivo en píxeles. |
| | `height` | Entero | Alto objetivo en píxeles. |
| | `mode` | String | `'stretch'` (deforma al tamaño exacto), `'fit'` (mantiene relación de aspecto), `'crop'` (recorta al centro). |
| `rotate` | `angle` | Numérico | Grados de rotación en sentido antihorario. |
| | `mode` | String | `'fill'` (expande el lienzo), `'crop'` (conserva dimensiones originales). |
| `grayscale` | *(ninguno)* | - | Convierte la imagen a escala de grises manteniendo 3 canales RGB. |
| `brightness` | `min_factor`, `max_factor` | Flotante | Rango para variación aleatoria (1.0 es original, `<1.0` oscurece, `>1.0` aclara). |
| | `factor` | Flotante | *(Opcional)* Factor fijo de brillo en lugar de rango aleatorio. |
