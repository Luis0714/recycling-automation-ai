# Recycling Automation System

# Descripción general

El **Recycling Automation System** es el módulo principal encargado de la automatización inteligente del sistema de reciclaje. Este proyecto será desarrollado en Python y tendrá la responsabilidad de integrar la detección de objetos, el procesamiento mediante visión artificial y la comunicación con Arduino para automatizar la apertura de las canecas correspondientes.

El sistema funcionará como el núcleo lógico del proyecto, actuando como intermediario entre el hardware físico (sensores y servomotores) y los procesos de inteligencia artificial encargados de identificar los residuos.

---

# Objetivo del sistema

Desarrollar un sistema automatizado capaz de detectar la presencia de un objeto, identificar su categoría mediante visión artificial y controlar la apertura automática de la caneca correspondiente a través de comunicación serial con Arduino.

---

# Responsabilidades principales

El sistema tendrá las siguientes responsabilidades:

## 1. Escuchar eventos provenientes de Arduino

El Arduino será el encargado de monitorear el sensor de proximidad HC-SR04. Cuando detecte que un objeto se encuentra cerca del sistema, enviará una señal o evento al programa desarrollado en Python indicando que debe iniciarse el proceso de identificación.

### Ejemplo conceptual

```text
OBJECT_DETECTED
```

---

## 2. Activar la cámara del sistema

Una vez recibido el evento de detección, el sistema deberá abrir la cámara conectada al computador utilizando OpenCV para capturar imágenes o video del objeto acercado por el usuario.

---

## 3. Procesar la imagen capturada

El sistema deberá ejecutar el módulo de reconocimiento de objetos utilizando técnicas de visión artificial e inteligencia artificial.

El proceso incluirá:

- Captura de imagen.
- Procesamiento visual.
- Identificación del objeto.
- Clasificación del objeto según la categoría correspondiente.

### Ejemplos de clasificación

| Objeto detectado | Categoría |
|---|---|
| Botella plástica | Plástico |
| Lata | Metal |
| Residuo orgánico | Orgánico |

---

## 4. Determinar la caneca correspondiente

Una vez identificado el objeto, el sistema deberá decidir cuál caneca debe abrirse de acuerdo con la categoría detectada.

### Ejemplo

```text
Botella plástica → Caneca plástico
```

---

## 5. Comunicarse con Arduino mediante serial

Después de determinar la categoría correcta, el sistema enviará un comando serial al Arduino indicando qué caneca debe abrirse.

### Ejemplos

```text
OPEN_PLASTIC
OPEN_METAL
OPEN_ORGANIC
```

---

## 6. Ejecutar el flujo automatizado completo

El sistema deberá coordinar todo el flujo de automatización desde la detección inicial hasta la apertura final de la caneca.

---

# Flujo general del sistema

```text
1. Sensor detecta objeto
            ↓
2. Arduino envía evento
            ↓
3. Python recibe evento
            ↓
4. Se activa la cámara
            ↓
5. Se captura imagen
            ↓
6. IA identifica objeto
            ↓
7. Se determina categoría
            ↓
8. Python envía comando
            ↓
9. Arduino abre caneca
```

---

# Tecnologías principales

| Tecnología | Función |
|---|---|
| Python | Lógica principal del sistema |
| OpenCV | Captura y procesamiento de imágenes |
| YOLO / IA | Reconocimiento de objetos |
| PySerial | Comunicación serial con Arduino |
| Arduino Uno | Control físico del sistema |
| HC-SR04 | Detección de proximidad |
| Servomotores | Apertura de canecas |

---

# Funcionalidades del sistema

## Funcionalidades principales

- Detección automática de objetos.
- Captura automática mediante cámara.
- Reconocimiento inteligente de residuos.
- Clasificación automática por categoría.
- Comunicación serial con Arduino.
- Apertura automatizada de canecas.

---

# Posibles funcionalidades futuras

- Registro de estadísticas de reciclaje.
- Dashboard de monitoreo.
- Historial de clasificaciones.
- Mejora del modelo de inteligencia artificial.
- Soporte para más categorías de residuos.
- Monitoreo en tiempo real.

---

# Resultado esperado

El sistema permitirá automatizar parcialmente el proceso de reciclaje mediante el uso de sensores, visión artificial e inteligencia artificial, logrando identificar residuos y abrir automáticamente la caneca adecuada según el tipo de objeto detectado.

---

# Nota de implementación y simulación

Durante las primeras fases de desarrollo, el sistema será construido como si el Arduino y todos los componentes físicos ya estuvieran conectados y funcionando correctamente. Sin embargo, inicialmente se utilizarán mecanismos de simulación para permitir el desarrollo y las pruebas del software sin depender del hardware físico.

La idea es dejar toda la arquitectura preparada desde el inicio para trabajar con Arduino real, evitando tener que modificar la lógica principal más adelante.

## Estrategia de simulación

### Simulación de entrada del sensor

En lugar de recibir realmente el evento desde Arduino, se podrá utilizar temporalmente:

```python
simulate_object_detected()
```

o incluso:

```python
input("Presione ENTER para simular objeto detectado")
```

Esto permitirá disparar manualmente el flujo de automatización.

---

### Simulación de envío de comandos al Arduino

En vez de enviar inicialmente comandos reales mediante serial, el sistema podrá utilizar temporalmente:

```python
print("OPEN_PLASTIC")
```

o:

```python
simulate_serial_send("OPEN_PLASTIC")
```

---

# Objetivo de esta estrategia

La finalidad es que toda la lógica del sistema quede desacoplada del hardware real.

De esta manera:

- El reconocimiento de objetos.
- El procesamiento IA.
- La lógica de clasificación.
- La estructura del sistema.

podrán desarrollarse y probarse desde etapas tempranas.

---

# Integración futura con hardware real

Cuando el Arduino esté completamente conectado, únicamente será necesario reemplazar las funciones de simulación por las funciones reales de comunicación serial.

## Ejemplo conceptual

### Simulación actual

```python
def send_command(command):
    print(f"Simulando envío: {command}")
```

### Implementación real futura

```python
def send_command(command):
    serial.write(command.encode())
```

---

# Beneficios de este enfoque

- Permite avanzar sin depender del hardware físico.
- Facilita pruebas tempranas.
- Reduce bloqueos durante el desarrollo.
- Mantiene el sistema desacoplado.
- Facilita el mantenimiento.
- Permite integrar el Arduino real con cambios mínimos.
- Mejora la organización del proyecto.