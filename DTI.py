import zmq
import threading
import time
import json
import os
import signal
import sys

# Disponibilidades originales
SALONES_DISPONIBLES_ORIGINALES = 380  # Cantidad inicial de salones disponibles
LABORATORIOS_DISPONIBLES_ORIGINALES = 60  # Cantidad inicial de laboratorios disponibles

# Diccionarios para manejar la disponibilidad por semestre
disponibilidad_por_semestre = {}  # Diccionario que mantiene la disponibilidad por semestre
lock = threading.Lock()  # Lock para manejar acceso concurrente a los datos
resultados_asignacion = {}  # Diccionario donde se almacenan los resultados de la asignación
estado_asignaciones = {}  # Diccionario donde se mantiene el estado de asignaciones por semestre

detener_servidor = False  # Bandera global para detener el servidor


# Función para manejar la interrupción (Ctrl+C)
# Parámetros:
#   - sig: Señal recibida.
#   - frame: Información del marco de la señal.
#
# Funcionalidad:
# Esta función establece la bandera `detener_servidor` como `True` cuando se recibe una señal de interrupción,
# permitiendo así detener el servidor de manera ordenada.
#
# Uso de recursos:
#   - Utiliza recursos del sistema para recibir señales de interrupción (señales del sistema operativo).
def handler(sig, frame):
    global detener_servidor
    print("\n[DTI] Señal de interrupción recibida. Deteniendo servidor...")
    detener_servidor = True

signal.signal(signal.SIGINT, handler)  # Configura la señal de interrupción para detener el servidor


# Función para cargar el estado de las asignaciones
#
# Parámetros:
#   Ninguno
#
# Funcionalidad:
# Carga el estado de las asignaciones desde un archivo JSON si existe. Si no, inicializa el estado y limpia los datos.
#
# Uso de recursos:
#   - Acceso a archivos: Lee un archivo JSON (si existe) para cargar el estado previo de las asignaciones.
#   - Memoria: Carga los datos del estado en memoria.
def cargar_estado_asignaciones():
    global estado_asignaciones
    archivo_estado = "resultados/estado_asignaciones.json"
    if os.path.exists(archivo_estado):
        with open(archivo_estado, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
        estado_asignaciones = {}
        disponibilidad_por_semestre.clear()


# Función para guardar el estado de las asignaciones
#
# Parámetros:
#   Ninguno
#
# Funcionalidad:
# Guarda el estado de las asignaciones en un archivo JSON, creando el directorio de resultados si es necesario.
#
# Uso de recursos:
#   - Acceso a archivos: Guarda el estado en un archivo JSON.
#   - Memoria: Los resultados se mantienen en memoria hasta que se guardan en el archivo.
def guardar_estado_asignaciones():
    archivo_estado = "resultados/estado_asignaciones.json"
    os.makedirs("resultados", exist_ok=True)
    with open(archivo_estado, "w", encoding="utf-8") as f:
        json.dump(estado_asignaciones, f, ensure_ascii=False, indent=4)


# Función para procesar las solicitudes de un programa de una facultad
# Parámetros:
#   - programa (dict): Información del programa a procesar.
#   - facultad (str): Nombre de la facultad.
#   - semestre (str): Semestre para el cual se realiza la asignación.
#
# Funcionalidad:
# Procesa la solicitud de un programa, asignando los recursos (salones y laboratorios) disponibles y actualizando
# la disponibilidad por semestre.
#
# Uso de recursos:
#   - Memoria: Utiliza memoria para almacenar las asignaciones y los estados intermedios.
#   - Lock: Se utiliza un `lock` para garantizar que solo un hilo acceda a los datos de asignación de manera concurrente.
#   - Salones y laboratorios: Asigna los recursos disponibles (salones y laboratorios) según las solicitudes de los programas.
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

        # Asignación de salones
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

        # Actualizar el estado de asignaciones
        estado['salones_disponibles'] = max(disponibles['salones'], 0)
        estado['laboratorios_disponibles'] = max(disponibles['laboratorios'], 0)

    time.sleep(1)


# Función para guardar los resultados globales
#
# Parámetros:
#   Ninguno
#
# Funcionalidad:
# Guarda los resultados completos de las asignaciones en archivos JSON por semestre.
#
# Uso de recursos:
#   - Acceso a archivos: Guarda los resultados en archivos JSON por semestre.
#   - Memoria: Carga y almacena los resultados de las asignaciones por semestre en memoria antes de guardarlos.
def guardar_resultados_global():
    resultados_por_semestre = {}
    for clave, datos in resultados_asignacion.items():
        facultad, semestre = clave.rsplit("_", 1)
        if semestre not in resultados_por_semestre:
            resultados_por_semestre[semestre] = []
        resultados_por_semestre[semestre].extend([  # Actualiza los resultados con los datos por facultad
            {**r, "facultad": facultad} for r in datos
        ])

    os.makedirs("resultados", exist_ok=True)
    for semestre, datos in resultados_por_semestre.items():
        with open(f"resultados/asignacion_completa_{semestre}.json", "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)


# Función que maneja las solicitudes del servidor DTI
#
# Parámetros:
#   Ninguno
#
# Funcionalidad:
# Espera solicitudes de asignación de recursos, procesa los programas recibidos y actualiza los resultados y el estado.
# Responde al cliente con los resultados de la asignación.
#
# Uso de recursos:
#   - Comunicación de red: Utiliza `zmq` para recibir solicitudes y enviar respuestas.
#   - Memoria: Guarda los resultados de las asignaciones en memoria y los transmite de vuelta.
#   - Hilos: Crea hilos para procesar las solicitudes de manera concurrente.
def manejar_dti():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://10.43.103.197:5556")  # Puerto de escucha

    print("[DTI] Servidor DTI iniciado, escuchando en el puerto 5556...")

    while not detener_servidor:
        try:
            if socket.poll(1000):  # Espera hasta 1 segundo por mensaje
                mensaje = socket.recv_json()  # Recibe el mensaje del cliente

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
            else:
                print("[DTI] Esperando solicitudes...")
                time.sleep(1)
        except KeyboardInterrupt:
            break


# Iniciar servidor DTI
if __name__ == "__main__":
    cargar_estado_asignaciones()
    manejar_dti()
