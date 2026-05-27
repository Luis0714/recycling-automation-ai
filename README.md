# Recycling Automation System (AI)

Pipeline en Python: sensor de proximidad → captura de imagen → clasificación de residuo → comando a la caneca (simulado por consola).

## Requisitos

- Python 3.11+ (recomendado)
- Webcam (modo cámara real)
- Windows/macOS/Linux con escritorio si usas vista previa OpenCV (`imshow`)

## Instalación

Desde la raíz del proyecto:

```powershell
# Crear entorno virtual
python -m venv .venv

# Activar (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt
```

El clasificador usa por defecto `model/best.pt` (modelo custom del proyecto).

Opcional: copia o edita `.env` (variables con prefijo `RAS_`). Ejemplo para Arduino:

```env
RAS_SERIAL_PORT=COM3
RAS_SERIAL_BAUDRATE=9600
```

## Ejecutar el proyecto

Todos los comandos asumen el entorno activado (`.venv`) y estar en la carpeta del repo.

### Simulación rápida (sin cámara ni YOLO)

Un ciclo con categoría fija y sensor inmediato:

```powershell
python main.py --sensor immediate --once
```

Varios ciclos: pulsa **ENTER** entre cada uno (simula sensor de cercanía):

```powershell
python main.py
```

### Webcam + YOLO (uso habitual)

**Un ciclo** al iniciar (abre cámara, 5 s para colocar el objeto, **ESC** captura antes, clasifica y termina):

```powershell
python main.py --camera opencv --classifier yolo --sensor immediate
```

**Un ciclo cada vez que tú indiques** (recomendado): tras cada resultado, pulsa **ENTER** para el siguiente:

```powershell
python main.py --camera opencv --classifier yolo
```

Equivalente explícito:

```powershell
python main.py --camera opencv --classifier yolo --sensor enter
```

### Arduino (sensor serial)

Configura `RAS_SERIAL_PORT` en `.env` o pásalo por CLI. El programa espera líneas como `DETECTED`:

```powershell
python main.py --camera opencv --classifier yolo --sensor serial --serial-port COM3
```

### Modo hardware por `.env`

Si en `.env` tienes `RAS_RUN_MODE=hardware`, puedes omitir `--camera opencv` (usa webcam por defecto):

```powershell
# .env: RAS_RUN_MODE=hardware
python main.py --classifier yolo
```

### Otros comandos útiles

| Objetivo | Comando |
|----------|---------|
| Un solo ciclo (cualquier sensor) | `python main.py --once ...` |
| Bucle sin fin con `immediate` | `python main.py --sensor immediate --continuous --camera opencv --classifier yolo` |
| Sin ventanas (servidor/CI) | `python main.py --camera opencv --classifier yolo --no-preview` |
| Otra cámara (índice 1) | `python main.py --camera opencv --camera-index 1 --classifier yolo` |
| Imagen fija en simulación | `python main.py --fixture ruta\imagen.jpg --classifier yolo` |
| Ignorar clases YOLO | `python main.py --camera opencv --classifier yolo --yolo-skip person` |
| Confianza YOLO | `python main.py --camera opencv --classifier yolo --yolo-conf 0.5` |
| Confianza minima de categoria | `python main.py --camera opencv --classifier yolo --yolo-category-conf 0.45` |
| Stub sin ML | `python main.py --classifier stub --category organic` |

Detener un bucle: **Ctrl+C**.

## Comportamiento del bucle

| `--sensor` | Por defecto |
|------------|-------------|
| `enter` | Repite; cada ciclo espera **ENTER** |
| `serial` | Repite; cada ciclo espera línea del Arduino |
| `immediate` | **Un ciclo y sale**; usa `--continuous` para repetir sin parar |

## Variables de entorno (`RAS_*`)

| Variable | Descripción |
|----------|-------------|
| `RAS_RUN_MODE` | `simulation` (default) o `hardware` |
| `RAS_SERIAL_PORT` | Puerto COM del Arduino |
| `RAS_SERIAL_BAUDRATE` | Baudios (default `9600`) |
| `RAS_CAMERA_DEVICE_INDEX` | Índice de webcam (default `0`) |
| `RAS_CAMERA_PLACEMENT_PREVIEW_MS` | Segundos de vista previa para colocar objeto (default `5000`) |
| `RAS_CLASSIFIER_BACKEND` | `stub` o `yolo` |
| `RAS_YOLO_MODEL_PATH` | Modelo `.pt` (default `model/best.pt`) |
| `RAS_YOLO_CONFIDENCE` | Umbral 0–1 (default `0.35`) |
| `RAS_YOLO_CATEGORY_CONFIDENCE` | Umbral minimo para aceptar categoria final (default `0.45`) |
| `RAS_YOLO_SKIP_CLASSES` | Clases a ignorar (default vacío) |

## Mapeo actual a canecas (3 canecas)

- `plastic` y `metal` -> `BLANCO` (aprovechables)
- `organic` -> `VERDE` (organicos)
- `unknown` -> `NO_ACTION` (no abre ninguna caneca)

## Dashboard de cámara

- Fondo del layout de vista previa: `asset/dashboard.png`
- Modelo custom usado por defecto: `model/best.pt`
- Si no tienes imágenes por clase, el panel lateral muestra texto:
  - clase detectada
  - categoría
  - confianza
  - destino de caneca

## Ayuda CLI

```powershell
python main.py --help
```

## Estructura

```
domain/       Modelos y mapeo categoría → comando
ports/        Protocolos (interfaces)
application/  Pipeline del ciclo
adapters/     Cámara, YOLO, sensor, actuador
main.py       Punto de entrada CLI
config.py     Settings (Pydantic + .env)
```
Sin Arduino, paso a paso:
python main.py --sensor enter --camera opencv --classifier yolo

Sin Arduino, ciclos continuos:
python main.py --sensor immediate --continuous --camera opencv --classifier yolo

Con Arduino:
python main.py --sensor serial --serial-port COM4 --serial-baud 9600 --camera opencv --classifier yolo
