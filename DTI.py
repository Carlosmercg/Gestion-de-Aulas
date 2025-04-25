import zmq
import threading
import time
import json
import os
import signal
import sys

SALONES_DISPONIBLES_ORIGINALES = 380
LABORATORIOS_DISPONIBLES_ORIGINALES = 60

disponibilidad_por_semestre = {}
lock = threading.Lock()
resultados_asignacion = {}
estado_asignaciones = {}

detener_servidor = False

def handler(sig, frame):
    global detener_servidor
    print("\n[DTI] Señal de interrupción recibida. Deteniendo servidor...")
    detener_servidor = True

signal.signal(signal.SIGINT, handler)

def cargar_estado_asignaciones():
    global estado_asignaciones
    archivo_estado = "resultados/estado_asignaciones.json"
    os.makedirs("resultados", exist_ok=True)
    with open(archivo_estado, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=4)
    estado_asignaciones = {}
    disponibilidad_por_semestre.clear()

def guardar_estado_asignaciones():
    archivo_estado = "resultados/estado_asignaciones.json"
    os.makedirs("resultados", exist_ok=True)
    with open(archivo_estado, "w", encoding="utf-8") as f:
        json.dump(estado_asignaciones, f, ensure_ascii=False, indent=4)

def procesar_programa(programa, facultad, semestre):
    with lock:
        if semestre not in estado_asignaciones:
            estado_asignaciones[semestre] = {
                'salones_disponibles': SALONES_DISPONIBLES_ORIGINALES,
                'laboratorios_disponibles': LABORATORIOS_DISPONIBLES_ORIGINALES,
                'salones_solicitados': 0,
                'laboratorios_solicitados': 0
            }
            disponibilidad_por_semestre[semestre] = {
                'salones': SALONES_DISPONIBLES_ORIGINALES,
                'laboratorios': LABORATORIOS_DISPONIBLES_ORIGINALES
            }

        disponibles = disponibilidad_por_semestre[semestre]
        estado = estado_asignaciones[semestre]

        estado['salones_solicitados'] += programa['salones']
        estado['laboratorios_solicitados'] += programa['laboratorios']

        resultado = {
            "facultad": facultad,
            "programa": programa['nombre'],
            "salones_solicitados": programa['salones'],
            "laboratorios_solicitados": programa['laboratorios'],
            "salones_asignados": 0,
            "laboratorios_asignados": 0
        }

        salones_usados_como_labs = 0

        if disponibles['laboratorios'] >= programa['laboratorios']:
            disponibles['laboratorios'] -= programa['laboratorios']
            resultado["laboratorios_asignados"] = programa['laboratorios']
            print(f"[DTI] {programa['nombre']} ({facultad}) recibió {programa['laboratorios']} laboratorios.")
        elif disponibles['salones'] >= programa['laboratorios']:
            disponibles['salones'] -= programa['laboratorios']
            resultado["salones_asignados"] += programa['laboratorios']
            salones_usados_como_labs = programa['laboratorios']
            print(f"[DTI] {programa['nombre']} ({facultad}) recibió {programa['laboratorios']} salones como laboratorios.")
        else:
            print(f"[DTI] {programa['nombre']} ({facultad}) no recibió laboratorios ni salones como sustituto.")

        if disponibles['salones'] >= programa['salones']:
            disponibles['salones'] -= programa['salones']
            resultado["salones_asignados"] += programa['salones']
            print(f"[DTI] {programa['nombre']} ({facultad}) recibió {programa['salones']} salones.")
        else:
            print(f"[DTI] {programa['nombre']} ({facultad}) no recibió salones.")

        if salones_usados_como_labs > 0:
            resultado["salones_como_laboratorios"] = salones_usados_como_labs

        clave = f"{facultad}_{semestre}"
        if clave not in resultados_asignacion:
            resultados_asignacion[clave] = []
        resultados_asignacion[clave].append(resultado)

        estado['salones_disponibles'] = max(disponibles['salones'], 0)
        estado['laboratorios_disponibles'] = max(disponibles['laboratorios'], 0)

    time.sleep(1)

def guardar_resultados_global():
    resultados_por_semestre = {}
    for clave, datos in resultados_asignacion.items():
        facultad, semestre = clave.rsplit("_", 1)
        if semestre not in resultados_por_semestre:
            resultados_por_semestre[semestre] = []
        resultados_por_semestre[semestre].extend([
            {**r, "facultad": facultad} for r in datos
        ])

    os.makedirs("resultados", exist_ok=True)
    for semestre, datos in resultados_por_semestre.items():
        with open(f"resultados/asignacion_completa_{semestre}.json", "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)

def manejar_dti():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://10.43.103.197:5556")

    print("[DTI] Servidor DTI iniciado, escuchando en el puerto 5556...")

    while not detener_servidor:
        try:
            if socket.poll(1000):
                mensaje = socket.recv_json()

                programas = mensaje["programas"]
                facultad = mensaje["facultad"]
                semestre = mensaje["semestre"]

                print(f"[DTI] Solicitud recibida para {facultad} - {semestre}:")
                for programa in programas:
                    print(f"  - Programa: {programa['nombre']}, Salones solicitados: {programa['salones']}, Laboratorios solicitados: {programa['laboratorios']}")

                hilos = []
                resultados_programas = []
                for programa in programas:
                    hilo = threading.Thread(target=procesar_programa, args=(programa, facultad, semestre))
                    hilo.start()
                    hilos.append(hilo)

                for hilo in hilos:
                    hilo.join()

                clave = f"{facultad}_{semestre}"
                for programa in programas:
                    for resultado in resultados_asignacion.get(clave, []):
                        if resultado["programa"] == programa["nombre"]:
                            resultados_programas.append({
                                "programa": programa["nombre"],
                                "salones_solicitados": resultado["salones_solicitados"],
                                "laboratorios_solicitados": resultado["laboratorios_solicitados"],
                                "salones_asignados": resultado["salones_asignados"],
                                "laboratorios_asignados": resultado["laboratorios_asignados"],
                                "salones_como_laboratorios": resultado.get("salones_como_laboratorios", 0)
                            })

                socket.send_json({
                    "resultado": resultados_programas,
                    "estado": {
                        "salones_disponibles": disponibilidad_por_semestre[semestre]["salones"],
                        "laboratorios_disponibles": disponibilidad_por_semestre[semestre]["laboratorios"]
                    }
                })

                # ✅ Guardar estado actualizado después de cada solicitud
                guardar_estado_asignaciones()

            else:
                print("[DTI] Esperando solicitudes...")
                time.sleep(1)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    cargar_estado_asignaciones()
    manejar_dti()
