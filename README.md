# Smart Recycling — Python (AI + Arduino)

Sistema de clasificación de residuos con YOLO + Arduino + Supabase. Este
módulo es la "puerta de entrada" del sistema: detecta residuos, abre la
caneca correspondiente y persiste cada evento.

## Arquitectura

```
┌──────────────┐    ┌────────────────┐    ┌────────────────┐
│  Cámara      │───▶│  YOLO          │───▶│  send_to_ard.  │──▶ Arduino
│  (OpenCV)    │    │  (ultralytics) │    │  (BestDetection)│
└──────────────┘    └────────────────┘    └────────────────┘
                                                  │
                                                  ▼ (arduino first, sync)
                                         ┌────────────────┐
                                         │  Supabase      │ (async, queue + worker)
                                         │  Event Writer  │──▶ Supabase REST
                                         └────────────────┘

Manual bin opening (web → Python):

  Web app INSERT ──▶ manual_bin_openings
                          │
                          └─postgres_changes (Realtime)─▶ SupabaseBinCommandSubscriber
                                                              │
                                                              ▼
                                                       BinCommandHandler
                                                              │
                                                              ▼
                                                       arduino_bridge.request_open
                                                              │
                                                              ▼
                                                       Arduino abre la caneca
```

## Estructura

```
recycling-automation-ai/
├── main.py                          # entrypoint: wiring
├── config.py                        # Pydantic v2 Settings (prefijo RAS_)
├── requirements.txt
├── .env.example                     # variables de entorno
├── README.md
├── migrations/
│   └── 0001_init.sql                # schema Supabase (tablas + RLS + realtime)
├── domain/
│   ├── detection_event.py           # dataclass del evento
│   ├── model_loader.py
│   ├── waste_classes.py
│   └── waste_mapping.py
├── ports/
│   ├── persistence.py               # Protocol: DetectionRepository, ManualOpeningRepository
│   └── realtime.py                  # Protocol: BinCommandSubscriber
├── adapters/
│   ├── arduino_serial.py            # bridge Arduino + request_open
│   ├── scanning_tkinter.py          # YOLO scanner + callback BestDetection
│   ├── ui_tkinter.py                # ventana Tkinter
│   ├── supabase_persistence.py      # implementación Supabase de los repos
│   └── supabase_realtime.py         # suscriptor postgres_changes
└── application/
    ├── event_writer.py              # queue.Queue + worker + fallback JSONL
    ├── bin_command_handler.py       # per-station lock + Arduino + UPDATE
    └── persistence_service.py       # orquestador
```

## 12 clases YOLO (kendrickfff/waste-classification-yolov8-ken)

| Clase            | Caneca Arduino | Categoría         |
|------------------|----------------|-------------------|
| battery          | ROJO           | No aprovechables  |
| biological       | VERDE          | Orgánicos         |
| brown-glass      | VERDE          | Orgánicos         |
| cardboard        | BLANCO         | Aprovechables     |
| clothes          | NEGRO          | No aprovechables  |
| green-glass      | VERDE          | Orgánicos         |
| metal            | BLANCO         | Aprovechables     |
| paper            | BLANCO         | Aprovechables     |
| plastic          | BLANCO         | Aprovechables     |
| shoes            | NEGRO          | No aprovechables  |
| trash            | NEGRO          | No aprovechables  |
| white-glass      | VERDE          | Orgánicos         |

## Variables de entorno

Copia `.env.example` a `.env` y completa:

| Variable                          | Descripción                                             | Fuente                                         |
|----------------------------------|---------------------------------------------------------|------------------------------------------------|
| `RAS_SERIAL_PORT`                | Puerto del Arduino (ej. `COM3`, `/dev/ttyUSB0`).        | Administrador de dispositivos / `ls /dev/tty*`  |
| `RAS_SERIAL_BAUDRATE`            | Baudios (default `9600`).                               | Firmware del Arduino                           |
| `RAS_CAMERA_DEVICE_INDEX`        | Índice de la cámara (default `0`).                      | Sistema operativo                              |
| `RAS_YOLO_MODEL_PATH`            | Ruta al `.pt` o `None` para descargar de HF.            | Local o Hugging Face                           |
| `RAS_YOLO_CONFIDENCE`            | Umbral mínimo de confianza (default `0.35`).            | -                                              |
| `RAS_STATION_ID`                 | Identificador de la estación (default `station-001`).   | Debe existir en la tabla `stations`            |
| `RAS_SUPABASE_URL`               | Project URL de Supabase.                                | Project Settings → API                         |
| `RAS_SUPABASE_SERVICE_KEY`       | **service_role** secret (servidor, no el anon).         | Project Settings → API                         |
| `RAS_LOCAL_BUFFER_DIR`           | Carpeta para el buffer offline (default `var`).         | Local                                          |

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# (opcional) PyTorch con CUDA: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
cp .env.example .env
# Edita .env con tus credenciales
```

## Migración de base de datos

Aplica `migrations/0001_init.sql` en el SQL editor de Supabase (es idempotente).
Crea las tablas `stations`, `detections`, `manual_bin_openings`, las
políticas de RLS y activa Realtime sobre `manual_bin_openings`.

## Ejecución

```bash
python main.py
```

La ventana de Tkinter permanece oculta hasta que el Arduino envíe `DETECTED`
vía serial. Cuando llega una detección:

1. YOLO clasifica el objeto durante ~8 segundos.
2. Se envía el comando al Arduino (`BLANCO` / `NEGRO` / `VERDE` / `ROJO`).
3. El evento se encola para persistirlo en Supabase (batch async).
4. Cuando Arduino envía `DEPOSITO_COMPLETO:`, la ventana se oculta y el
   sistema vuelve a esperar.

## Modo manual desde la web

1. La web inserta una fila en `manual_bin_openings` con `status='pending'`.
2. El subscriber de Supabase Realtime la recibe en el proceso Python.
3. `BinCommandHandler` la traduce en `arduino_bridge.request_open(bin)`.
4. La fila se actualiza a `status='opened'` (o `error`) con `latency_ms`.
5. La UI web ve la actualización vía `postgres_changes` y muestra el resultado.

### Recovery on reconnect

Si el proceso Python está offline cuando se inserta una fila, al
reconectarse el subscriber ejecuta un `SELECT pending` de los últimos 5
minutos y los procesa. Las filas más viejas se marcan `timeout`.

### Fallback offline

Si Supabase está caído, los eventos se escriben en
`var/detection_buffer.jsonl` y se reintentan al reconectar (en el
próximo arranque del worker).

## Múltiples estaciones (futuro)

`PersistenceService.add_station(station_id, bridge)` permite registrar
múltiples bridges para un solo proceso. Cada estación tiene su propio
lock para serializar aperturas. Ejecuta un proceso por estación
(`RAS_STATION_ID=station-002 python main.py`) para una configuración
más simple.
