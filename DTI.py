import zmq
import threading
import time
import json
import os

# Disponibilidades originales
SALONES_DISPONIBLES_ORIGINALES = 380
LABORATORIOS_DISPONIBLES_ORIGINALES = 60

# Diccionarios para manejar la disponibilidad por semestre
disponibilidad_por_semestre = {}

lock = threading.Lock()
resultados_asignacion = {}
estado_asignaciones = {}

def cargar_estado_asignaciones():
    global estado_asignaciones
    archivo_estado = "resultados/estado_asignaciones.json"
    if os.path.exists(archivo_estado):
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
        # Inicializar estado y disponibilidad del semestre si no existen
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

        # Referencias locales
        disponibles = disponibilidad_por_semestre[semestre]
        estado = estado_asignaciones[semestre]

        # Acumulamos solicitudes
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

        # Asignación de laboratorios
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

        # Asignación de salones normales
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

        # Actualizar estado_asignaciones con la disponibilidad restante
        estado['salones_disponibles'] = disponibles['salones']
        estado['laboratorios_disponibles'] = disponibles['laboratorios']

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
    socket.bind("tcp://*:5556")

    print("[DTI] Servidor DTI iniciado, escuchando en el puerto 5556...")

    while True:
        try:
            mensaje = socket.recv_json()

            programas = mensaje["programas"]
            facultad = mensaje["facultad"]
            semestre = mensaje["semestre"]

            print(f"[DTI] Solicitud recibida para {facultad} - {semestre}:")
            for programa in programas:
                print(f"  - Programa: {programa['nombre']}, Salones solicitados: {programa['salones']}, Laboratorios solicitados: {programa['laboratorios']}")

            hilos = []
            for programa in programas:
                hilo = threading.Thread(target=procesar_programa, args=(programa, facultad, semestre))
                hilo.start()
                hilos.append(hilo)

            for hilo in hilos:
                hilo.join()

            guardar_resultados_global()
            guardar_estado_asignaciones()

            socket.send_json({
                "status": "ok",
                "mensaje": f"{len(programas)} programas procesados correctamente para {facultad}."
            })

        except Exception as e:
            print(f"[DTI] Error: {e}")
            socket.send_json({"status": "error", "mensaje": str(e)})

    socket.close()
    context.term()

def iniciar_dti():
    cargar_estado_asignaciones()
    dti_thread = threading.Thread(target=manejar_dti)
    dti_thread.start()

if __name__ == "__main__":
    iniciar_dti()
