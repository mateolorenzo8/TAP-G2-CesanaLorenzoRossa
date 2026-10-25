# Procesador Masivo de Imágenes CLI

Pipeline de procesamiento y aumento de imágenes por lotes (batch processing), diseñado para alto rendimiento mediante procesamiento paralelo multinúcleo (`multiprocessing`), completamente contenerizado con **Docker** y desacoplado de su configuración.

---

## 📁 Estructura del Repositorio

```text
├── Dockerfile          # Definición de la imagen del contenedor (Python 3.14-slim)
├── .dockerignore       # Archivos excluidos del contexto de compilación (incluye config.yaml)
├── config.yaml         # Archivo de configuración con los parámetros de transformación
├── main.py             # Punto de entrada CLI (parseo de argumentos y carga de configuración)
├── processor.py        # Motor de procesamiento en paralelo (Pillow, ProcessPoolExecutor, tqdm)
├── pyproject.toml      # Definición de dependencias del proyecto (uv/pip)
├── requirements.txt    # Dependencias congeladas para la instalación dentro del contenedor
└── README.md           # Documentación técnica del proyecto
```

---

## ⚙️ Características Técnicas

- **Procesamiento Paralelo**: Utiliza `ProcessPoolExecutor` aprovechando todos los núcleos de CPU disponibles (`multiprocessing.cpu_count()`).
- **Pipeline de Transformaciones**:
  - Escala de grises (`grayscale`).
  - Rotación arbitraria con soporte de canvas expandido (`rotate`).
  - Redimensionamiento (`resize`) con algoritmos `stretch`, `fit` (manteniendo aspect ratio) y `crop` (recorte central).
  - Aumento de datos mediante variación aleatoria de brillo (`brightness`).
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
  -v "/Users/mateo/Downloads/test:/app/input" \
  -v "/Users/mateo/Desktop/poc:/app/output" \
  -v "$(pwd)/config.yaml:/app/config.yaml" \
  image-processor \
  -i /app/input \
  -o /app/output \
  -c /app/config.yaml
```

---

## 🛠️ Configuración (`config.yaml`)

El pipeline aplica las operaciones definidas en el bloque `transformations`:

```yaml
transformations:
  # Redimensionamiento de imagen
  resize:
    width: 800
    height: 800
    mode: "fit" # Opciones: 'stretch' (deforma), 'fit' (aspect ratio), 'crop' (recorte central)

  # Rotación en grados
  rotate:
    angle: 45
    mode: "fill" # 'fill' (expande el lienzo), 'crop' (conserva dimensiones)

  # Conversión a blanco y negro
  grayscale: true

  # Aumento por variaciones de brillo
  brightness:
    generate_count: 3 # Cantidad de imágenes generadas por cada original
    min_factor: 0.5   # Factor mínimo (< 1 oscurece)
    max_factor: 1.5   # Factor máximo (> 1 aclara)
```

