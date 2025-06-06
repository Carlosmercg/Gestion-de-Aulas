# dti_worker.py
"""
Worker DTI que se conecta al broker (backend DEALER) con ZeroMQ.
Mantiene la misma lógica de asignación que el DTI original, pero
ya no recibe conexiones directas de las facultades.
"""
import zmq
import threading
import time
import json
import os

# ——————————————————————————————————————————
# Configuración de red (ajusta la IP/puerto)
# ——————————————————————————————————————————
BROKER_BACKEND_ADDR = "tcp://10.43.96.74:5560"  # backend del broker

# ——————————————————————————————————————————
# Parámetros de recursos y estructuras globales
# ——————————————————————————————————————————
SALONES_DISPONIBLES_ORIGINALES = 380
LABORATORIOS_DISPONIBLES_ORIGINALES = 60

disponibilidad_por_semestre = {}
resultados_asignacion = {}
estado_asignaciones = {}
lock = threading.Lock()  # protege recursos compartidos

# ——————————————————————————————————————————
# Utilidades de persistencia (idénticas a tu DTI)
# ——————————————————————————————————————————
def cargar_estado_asignaciones() -> None:
    """Inicializa/limpia el archivo de estado de asignaciones."""
    global estado_asignaciones
    archivo_estado = "resultados/estado_asignaciones.json"
    if os.path.exists(archivo_estado):
        with open(archivo_estado, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
    estado_asignaciones.clear()
    disponibilidad_por_semestre.clear()

# ——————————————————————————————————————————
# Lógica de negocio (idéntica a tu DTI)
# ——————————————————————————————————————————
def procesar_programa(programa: dict, facultad: str, semestre: str) -> None:
    with lock:
        # Inicializar disponibilidad del semestre
        if semestre not in estado_asignaciones:
            estado_asignaciones[semestre] = {
                "salones_disponibles": SALONES_DISPONIBLES_ORIGINALES,
                "laboratorios_disponibles": LABORATORIOS_DISPONIBLES_ORIGINALES,
                "salones_solicitados": 0,
                "laboratorios_solicitados": 0,
            }
            disponibilidad_por_semestre[semestre] = {
                "salones": SALONES_DISPONIBLES_ORIGINALES,
                "laboratorios": LABORATORIOS_DISPONIBLES_ORIGINALES,
            }

        disponibles = disponibilidad_por_semestre[semestre]
        estado = estado_asignaciones[semestre]

        # Acumular solicitudes
        estado["salones_solicitados"] += programa["salones"]
        estado["laboratorios_solicitados"] += programa["laboratorios"]

        resultado = {
            "facultad": facultad,
            "programa": programa["nombre"],
            "salones_solicitados": programa["salones"],
            "laboratorios_solicitados": programa["laboratorios"],
            "salones_asignados": 0,
            "laboratorios_asignados": 0,
        }

        salones_usados_como_labs = 0

        # Asignación de laboratorios
        if disponibles["laboratorios"] >= programa["laboratorios"]:
            disponibles["laboratorios"] -= programa["laboratorios"]
            resultado["laboratorios_asignados"] = programa["laboratorios"]
            print(f"[DTI-W] {programa['nombre']} ({facultad}) recibió "
                  f"{programa['laboratorios']} laboratorios.")
        elif disponibles["salones"] >= programa["laboratorios"]:
            disponibles["salones"] -= programa["laboratorios"]
            resultado["salones_asignados"] += programa["laboratorios"]
            salones_usados_como_labs = programa["laboratorios"]
            print(f"[DTI-W] {programa['nombre']} ({facultad}) recibió "
                  f"{programa['laboratorios']} salones como laboratorios.")
        else:
            print(f"[DTI-W] {programa['nombre']} ({facultad}) no recibió "
                  "laboratorios ni salones como sustituto.")

        # Asignación de salones normales
        if disponibles["salones"] >= programa["salones"]:
            disponibles["salones"] -= programa["salones"]
            resultado["salones_asignados"] += programa["salones"]
            print(f"[DTI-W] {programa['nombre']} ({facultad}) recibió "
                  f"{programa['salones']} salones.")
        else:
            print(f"[DTI-W] {programa['nombre']} ({facultad}) no recibió salones.")

        if salones_usados_como_labs:
            resultado["salones_como_laboratorios"] = salones_usados_como_labs

        clave = f"{facultad}_{semestre}"
        resultados_asignacion.setdefault(clave, []).append(resultado)

        # Actualizar disponibilidad
        estado["salones_disponibles"] = max(disponibles["salones"], 0)
        estado["laboratorios_disponibles"] = max(disponibles["laboratorios"], 0)

    time.sleep(1)  # Simula carga de trabajo

# ——————————————————————————————————————————
# Worker principal: recibe peticiones del broker
# ——————————————————————————————————————————
def manejar_dti_worker() -> None:
    ctx = zmq.Context()
    socket = ctx.socket(zmq.REP)
    socket.connect(BROKER_BACKEND_ADDR)

    print(f"[DTI-W] Conectado al broker en {BROKER_BACKEND_ADDR}")

    while True:
        try:
            mensaje = socket.recv_json()

            programas = mensaje["programas"]
            facultad = mensaje["facultad"]
            semestre = mensaje["semestre"]

            print(f"[DTI-W] Solicitud recibida: {facultad} – {semestre}")
            hilos = []
            resultados_programas = []

            for prog in programas:
                hilo = threading.Thread(target=procesar_programa,
                                        args=(prog, facultad, semestre))
                hilo.start()
                hilos.append(hilo)

            for hilo in hilos:
                hilo.join()

            # Recolectar resultados
            clave = f"{facultad}_{semestre}"
            for resultado in resultados_asignacion.get(clave, []):
                resultados_programas.append({
                    "programa": resultado["programa"],
                    "salones_solicitados": resultado["salones_solicitados"],
                    "laboratorios_solicitados": resultado["laboratorios_solicitados"],
                    "salones_asignados": resultado["salones_asignados"],
                    "laboratorios_asignados": resultado["laboratorios_asignados"],
                    "salones_como_laboratorios":
                        resultado.get("salones_como_laboratorios", 0),
                })

            guardar_resultados_global()
            guardar_estado_asignaciones()

            socket.send_json({
                "resultado": resultados_programas,
                "estado": {
                    "salones_disponibles":
                        disponibilidad_por_semestre[semestre]["salones"],
                    "laboratorios_disponibles":
                        disponibilidad_por_semestre[semestre]["laboratorios"],
                },
            })

        except Exception as e:
            print(f"[DTI-W] Error: {e}")
            socket.send_json({"status": "error", "mensaje": str(e)})

    socket.close()
    ctx.term()

# ——————————————————————————————————————————
# Arranque
# ——————————————————————————————————————————
def iniciar_dti_worker() -> None:
    cargar_estado_asignaciones()
    threading.Thread(target=manejar_dti_worker, daemon=True).start()
    print("[DTI-W] Worker iniciado y en espera…")
    # Mantener hilo principal vivo
    while True:
        time.sleep(10)

if __name__ == "__main__":
    iniciar_dti_worker()
