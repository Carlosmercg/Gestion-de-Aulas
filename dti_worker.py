"""
DTI-worker con estado centralizado en SQLite.
Cada worker se conecta al broker y comparte la disponibilidad
de salones/laboratorios mediante la BD 'recursos.db'.
"""

import zmq, threading, time, os
from db import inicializar_bd, obtener_disponibilidad, actualizar_disponibilidad

BROKER_BACKEND_ADDR = "tcp://10.43.96.74:5560"

SALONES_DISPONIBLES_ORIGINALES = 380
LABORATORIOS_DISPONIBLES_ORIGINALES = 60

resultados_asignacion = {}          # sólo para devolver al cliente
lock = threading.Lock()             # protege operaciones por programa

# ------------------------------------------------------------------
# ------------------------------------------------------------------
def procesar_programa(programa: dict, facultad: str, semestre: str) -> None:
    with lock:
        disponibles = obtener_disponibilidad(
            semestre,
            SALONES_DISPONIBLES_ORIGINALES,
            LABORATORIOS_DISPONIBLES_ORIGINALES
        )

        resultado = {
            "facultad": facultad,
            "programa": programa["nombre"],
            "salones_solicitados": programa["salones"],
            "laboratorios_solicitados": programa["laboratorios"],
            "salones_asignados": 0,
            "laboratorios_asignados": 0,
        }

        salones_usados_como_labs = 0

        # Asignar laboratorios o salones para laboratorios
        if disponibles["laboratorios"] >= programa["laboratorios"]:
            disponibles["laboratorios"] -= programa["laboratorios"]
            resultado["laboratorios_asignados"] = programa["laboratorios"]
            print(f"[DTI-W] {programa['nombre']} ({facultad}) recibió "
                  f"{programa['laboratorios']} laboratorios.", flush=True)
        elif disponibles["salones"] >= programa["laboratorios"]:
            disponibles["salones"] -= programa["laboratorios"]
            resultado["salones_asignados"] += programa["laboratorios"]
            salones_usados_como_labs = programa["laboratorios"]
            print(f"[DTI-W] {programa['nombre']} ({facultad}) recibió "
                  f"{programa['laboratorios']} salones como laboratorios.", flush=True)
        else:
            print(f"[DTI-W] {programa['nombre']} ({facultad}) no recibió "
                  "laboratorios ni salones como sustituto.", flush=True)

        # Asignar salones normales
        if disponibles["salones"] >= programa["salones"]:
            disponibles["salones"] -= programa["salones"]
            resultado["salones_asignados"] += programa["salones"]
            print(f"[DTI-W] {programa['nombre']} ({facultad}) recibió "
                  f"{programa['salones']} salones.", flush=True)
        else:
            print(f"[DTI-W] {programa['nombre']} ({facultad}) no recibió salones.", flush=True)

        if salones_usados_como_labs:
            resultado["salones_como_laboratorios"] = salones_usados_como_labs

        actualizar_disponibilidad(semestre, disponibles)

        clave = f"{facultad}_{semestre}"
        resultados_asignacion.setdefault(clave, []).append(resultado)



# ------------------------------------------------------------------
def manejar_dti_worker() -> None:
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REP)
    sock.connect(BROKER_BACKEND_ADDR)
    print(f"[DTI-W] Conectado al broker en {BROKER_BACKEND_ADDR}")

    while True:
        try:
            msg = sock.recv_json()
            facultad  = msg["facultad"]
            semestre  = msg["semestre"]
            programas = msg["programas"]

            # Procesar secuencialmente para evitar conflictos en la BD
            for prog in programas:
                procesar_programa(prog, facultad, semestre)

            # preparar respuesta
            clave = f"{facultad}_{semestre}"
            resp = resultados_asignacion.get(clave, [])

            disponibles = obtener_disponibilidad(
                semestre,
                SALONES_DISPONIBLES_ORIGINALES,
                LABORATORIOS_DISPONIBLES_ORIGINALES
            )

            sock.send_json({
                "resultado": resp,
                "estado": {
                    "salones_disponibles": disponibles["salones"],
                    "laboratorios_disponibles": disponibles["laboratorios"]
                }
            })

        except Exception as e:
            print(f"[DTI-W] Error: {e}")
            sock.send_json({"status": "error", "mensaje": str(e)})


# ------------------------------------------------------------------
def iniciar_dti_worker() -> None:
    inicializar_bd()
    threading.Thread(target=manejar_dti_worker, daemon=True).start()
    print("[DTI-W] Worker iniciado y en espera…")
    while True:
        time.sleep(10)

if __name__ == "__main__":
    iniciar_dti_worker()
