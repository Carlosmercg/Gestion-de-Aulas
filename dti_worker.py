"""
DTI-worker concurrente con candado de archivo.
Cada worker comparte la disponibilidad usando la BD 'recursos.db'
y un FileLock (recursos.db.lock) para asegurar atomicidad.
"""

import zmq, threading, time
from db import (
    inicializar_bd,
    obtener_y_bloquear,      # NUEVO: devuelve lock, conn y dict disponibles
    guardar_y_desbloquear    # NUEVO: actualiza BD y libera lock
)


SALONES_ORIG = 380
LABS_ORIG    = 60

resultados_asignacion = {}          # solo para respuesta al cliente

PRIMARY_BACK   = "tcp://10.43.96.74:5560"
SECONDARY_BACK = "tcp://10.43.103.30:5561"

# ------------------------------------------------------------------
def asignar_recursos(programa, facu, semestre):
    """Realiza la asignación para UN programa dentro de la sección crítica."""
    # 1️⃣ Tomar candado + leer fila
    lock, conn, disp = obtener_y_bloquear(
        semestre, SALONES_ORIG, LABS_ORIG
    )

    try:
        res = {
            "facultad": facu,
            "programa": programa["nombre"],
            "salones_solicitados": programa["salones"],
            "laboratorios_solicitados": programa["laboratorios"],
            "salones_asignados": 0,
            "laboratorios_asignados": 0,
        }

        salones_usados_labs = 0

        # --- asignación de labs ---
        if disp["laboratorios"] >= programa["laboratorios"]:
            disp["laboratorios"] -= programa["laboratorios"]
            res["laboratorios_asignados"] = programa["laboratorios"]
            print(f"[DTI-W] {res['programa']} ({facu}) → "
                  f"{res['laboratorios_asignados']} labs.", flush=True)

        elif disp["salones"] >= programa["laboratorios"]:
            disp["salones"] -= programa["laboratorios"]
            res["salones_asignados"] += programa["laboratorios"]
            salones_usados_labs = programa["laboratorios"]
            print(f"[DTI-W] {res['programa']} ({facu}) → "
                  f"{salones_usados_labs} salones como labs.", flush=True)

        # --- asignación de salones ---
        if disp["salones"] >= programa["salones"]:
            disp["salones"] -= programa["salones"]
            res["salones_asignados"] += programa["salones"]
            print(f"[DTI-W] {res['programa']} ({facu}) → "
                  f"{programa['salones']} salones.", flush=True)

        if salones_usados_labs:
            res["salones_como_laboratorios"] = salones_usados_labs

        # 2️⃣ guardar nuevos saldos y soltar lock
        guardar_y_desbloquear(lock, conn, semestre, disp)

        # 3️⃣ almacenar para la respuesta
        clave = f"{facu}_{semestre}"
        resultados_asignacion.setdefault(clave, []).append(res)

    except Exception as e:
        # ante error, liberar lock para no quedar bloqueado
        try:
            guardar_y_desbloquear(lock, conn, semestre, disp)
        except Exception:
            pass
        raise e

# ------------------------------------------------------------------
def manejar_dti_worker():
    ctx  = zmq.Context()
    sock = ctx.socket(zmq.REP)

    # Opciones que evitan bloqueos y permiten conmutar rápido
    sock.setsockopt(zmq.LINGER,    0)   # cierra sin esperar
    sock.setsockopt(zmq.IMMEDIATE, 1)   # error inmediato si no hay peer
    sock.setsockopt(zmq.RCVTIMEO,  8000)  # espera de respuesta del broker
    sock.setsockopt(zmq.SNDTIMEO,  3000)  # espera de envío al broker

    # 🔗 Conéctate a LOS DOS brokers
    for ep in (PRIMARY_BACK, SECONDARY_BACK):
        sock.connect(ep)
    print(f"[DTI-W] Conectado a {PRIMARY_BACK} y {SECONDARY_BACK}")

    while True:
        try:
            msg = sock.recv_json()            # llegará de cualquiera de los brokers

            # Health-check del broker
            if msg.get("tipo") == "ping":
                sock.send_json({"status": "ok"})
                continue

            facu      = msg["facultad"]
            semestre  = msg["semestre"]
            programas = msg["programas"]

            # Procesar secuencialmente cada programa
            for prog in programas:
                asignar_recursos(prog, facu, semestre)

            # Construir respuesta
            clave = f"{facu}_{semestre}"
            resp  = resultados_asignacion.get(clave, [])

            # Leer saldo final
            _, _, disp = obtener_y_bloquear(semestre, SALONES_ORIG, LABS_ORIG)
            from filelock import FileLock
            FileLock("recursos.db.lock").release()

            sock.send_json({
                "resultado": resp,
                "estado": {
                    "salones_disponibles": disp["salones"],
                    "laboratorios_disponibles": disp["laboratorios"]
                }
            })

        except zmq.error.Again:
            # Timeout → el broker al que se envió no respondió.
            # ZeroMQ intentará la otra ruta en la próxima operación.
            continue
        except Exception as e:
            print(f"[DTI-W] Error: {e}", flush=True)
            sock.send_json({"status": "error", "mensaje": str(e)})


# ------------------------------------------------------------------
def iniciar_dti_worker():
    inicializar_bd()
    threading.Thread(target=manejar_dti_worker, daemon=True).start()
    print("[DTI-W] Worker listo…")
    while True:
        time.sleep(10)

if __name__ == "__main__":
    iniciar_dti_worker()
