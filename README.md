# 🏫 Sistema de Asignación de Aulas y Laboratorios por Facultad

Este proyecto simula un sistema distribuido para la asignación de salones y laboratorios a programas académicos de distintas facultades. El sistema tiene dos versiones de funcionamiento:

- ✅ **Versión 1: Comunicación asíncrona directa**
- ⚖️ **Versión 2: Comunicación mediante Broker para balanceo de carga**

---

## 📘 Descripción general

Cada facultad envía solicitudes de salones y laboratorios que son procesadas por un servidor DTI central. En la versión 2, se incorpora un Broker (ROUTER ⇄ DEALER) que balancea la carga entre varios procesos `DTI Worker`.

---

## 🧱 Componentes principales

| Componente     | Descripción                                                                 |
|----------------|-----------------------------------------------------------------------------|
| **Programas**  | Lee un archivo JSON con las solicitudes por facultad y las envía a su puerto respectivo. |
| **Facultades** | Recibe las solicitudes desde Programas en un puerto asignado y reenvía la solicitud al DTI. |
| **Facultades_broker** | Recibe las solicitudes desde Programas en un puerto asignado y reenvía la solicitud al Broker. |
| **DTI**        | Asigna recursos (salones/labs), guarda los resultados en archivos JSON y responde. |
| **Broker**     | (Solo en versión 2) Balancea solicitudes entre múltiples procesos `DTI Worker`. |

---

## 🌐 Direcciones IP y puertos

| Proceso         | IP              | Puertos           | Notas                                  |
|-----------------|------------------|--------------------|----------------------------------------|
| Programas       | `10.43.103.204`  | -                  | Envía a `Facultades`                   |
| Facultades      | `10.43.103.102`  | 6000–6090          | Cada facultad tiene un puerto propio   |
| DTI (v1)        | `10.43.103.96.74`  | 5556               | Comunicación directa desde Facultades  |
| DTI_Respaldo (v1)        | `10.43.103.197`  | 5556               | Comunicación directa desde Facultades  |
| HealtChecker (v1)        | Dinamica  | 5556               | Revision si DTI esta vivo, para cambios con el DTI_Respaldo  |
| DTI Worker (v2) | Dinámica         | conecta a :5560    | Comunicación interna con Broker        |
| Facultades_broker (v2)      | `10.43.103.102`  | 6000–6090 // conecta a :5550           | Cada facultad tiene un puerto propio   |
| Broker (v2)     | `10.43.96.74`    | 5555 (frontend), 5560 (backend) | Balanceo ROUTER ⇄ DEALER |
| Broker_sec (v2)     | `10.43.103.30`    | 5556 (frontend), 5561 (backend) | Balanceo ROUTER ⇄ DEALER (respaldo) |
| health_checkbb (v2)        | `10.43.96.74`  | 6000               | Revision si Broker esta vivo, para cambios con el Broker_sec  |

---

## 🛠 Requisitos

- Python 3.8+
- `pyzmq` (`pip install pyzmq`)
- Archivo `solicitudes.json` válido
- Carpeta `resultados/` creada y con permisos de escritura

---

## 🔁 Flujo del sistema

### ✅ Versión 1 – Comunicación directa asíncrona

---

## 🧪 Ejecución

### ✅ Versión 1 – Asíncrona directa

```bash
# En DTI (10.43.103.197)
python DTI.py

# En DTI respaldo (10.43.96.74)
python DTI_Respaldo.py

# En healtcheck (Dinamico)
python HealtChecker.py

# En Facultades (10.43.103.102)
python facultades.py

#Crear solicitudes
Hay programa que simula la solicitudes, es decir crea el json
se compila antes de compilar programas
crearsolicitudes.py

# En Programas (10.43.103.204)
python programas.py
```
## 🧪 Ejecución

### ✅ Versión 2 – Con Broker

```bash
# En Broker (10.43.96.74)
python broker.py

# En Broker respaldo (10.43.103.30)
python broker_sec.py

# En healtcheck (10.43.96.74)
python health_checkbb.py

# En DTI Worker(s)
python dti_worker.py   # puede ejecutar múltiples instancias

# En Facultades (10.43.103.102)
python facultades_broker.py   # ahora conecta con el broker

#Crear solicitudes
Hay programa que simula la solicitudes, es decir crea el json
se compila antes de compilar programas
crearsolicitudes.py

# En Programas (10.43.103.204)
python programas.py
```
---

## 📑 Formato **exacto** del archivo `solicitudes.json`

```jsonc
{
  "semestre": "2025-1",
  "facultades": [
    {
      "nombre": "Facultad de Ingeniería",
      "programas": [
        {
          "nombre": "Ingeniería Civil",
          "salones": 7,
          "laboratorios": 3
        },
        {
          "nombre": "Ingeniería Electrónica",
          "salones": 6,
          "laboratorios": 2
        }
      ]
    },
    {
      "nombre": "Facultad de Artes",
      "programas": [
        {
          "nombre": "Bellas Artes",
          "salones": 5,
          "laboratorios": 2
        }
      ]
    }
  ]
}
