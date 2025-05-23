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

lock = threading.Lock()  # Lock utilizado para sincronizar el acceso a recursos compartidos
resultados_asignacion = {}  # Almacena los resultados de asignaciones
estado_asignaciones = {}  # Almacena el estado de disponibilidad y solicitudes

# Función: cargar_estado_asignaciones
# Parámetros: Ninguno
#
# Funcionalidad:
# Esta función se encarga de cargar el estado de las asignaciones desde un archivo JSON. Si el archivo no existe,
# crea un nuevo archivo y borra los datos anteriores. También limpia los diccionarios que mantienen el estado 
# de las asignaciones y la disponibilidad de los recursos.
#
# Uso de recursos:
# - Maneja archivos JSON para almacenar y cargar el estado de las asignaciones.
# - Limpia los diccionarios globales para reiniciar el estado.
def cargar_estado_asignaciones():
    global estado_asignaciones
    archivo_estado = "resultados/estado_asignaciones.json"
    if os.path.exists(archivo_estado):
        with open(archivo_estado, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
        estado_asignaciones = {}
        disponibilidad_por_semestre.clear()


# Función: guardar_estado_asignaciones
# Parámetros: Ninguno
#
# Funcionalidad:
# Guarda el estado actual de las asignaciones en un archivo JSON. Asegura que el directorio de resultados 
# exista antes de guardar el archivo y utiliza el formato JSON para escribir los datos.
#
# Uso de recursos:
# - Utiliza el módulo `json` para guardar el estado de las asignaciones en un archivo.
# - Asegura que el directorio de salida exista utilizando `os.makedirs`.
def guardar_estado_asignaciones():
    archivo_estado = "resultados/estado_asignaciones.json"
    os.makedirs("resultados", exist_ok=True)
    with open(archivo_estado, "w", encoding="utf-8") as f:
        json.dump(estado_asignaciones, f, ensure_ascii=False, indent=4)


# Función: procesar_programa
# Parámetros:
#   - programa (dict): Diccionario que contiene información sobre un programa (nombre, salones, laboratorios solicitados).
#   - facultad (str): Nombre de la facultad que solicita los recursos.
#   - semestre (str): El semestre en el que se solicita la asignación de recursos.
#
# Funcionalidad:
# Esta función gestiona la asignación de recursos (salones y laboratorios) a un programa de una facultad en un semestre.
# Verifica si existen recursos disponibles y asigna los salones y laboratorios según las solicitudes. Si no hay recursos 
# disponibles, se muestra un mensaje de error. Los resultados de la asignación se almacenan en un diccionario global.
#
# Uso de recursos:
# - Utiliza un `lock` para garantizar que el acceso a los recursos compartidos (estado de asignaciones y disponibilidad) 
#   sea seguro cuando se procesan múltiples solicitudes en paralelo.
# - Utiliza un diccionario global para almacenar y actualizar el estado de las asignaciones y la disponibilidad de recursos.
# - Usa `time.sleep(1)` al final para simular un retraso en la asignación de recursos (por ejemplo, para no saturar el servidor).
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
        estado['salones_disponibles'] = max(disponibles['salones'], 0)  # Asegurarse que no sea negativo
        estado['laboratorios_disponibles'] = max(disponibles['laboratorios'], 0)  # Asegurarse que no sea negativo

    time.sleep(1)


# Función: guardar_resultados_global
# Parámetros: Ninguno
#
# Funcionalidad:
# Esta función guarda los resultados de las asignaciones de recursos en archivos JSON separados por semestre.
# Agrupa los resultados por semestre y los guarda en la carpeta de resultados, con un archivo por cada semestre.
#
# Uso de recursos:
# - Utiliza el módulo `json` para guardar los resultados de las asignaciones en archivos.
# - Asegura que el directorio de salida exista utilizando `os.makedirs`.
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


# Función: manejar_dti
# Parámetros: Ninguno
#
# Funcionalidad:
# Esta función maneja las solicitudes entrantes del servidor DTI. Escucha las solicitudes y las procesa de manera
# concurrente, creando un hilo por cada programa y manejando la asignación de recursos. Después de procesar la
# solicitud, guarda los resultados y responde al cliente con los resultados completos de la asignación de recursos.
#
# Uso de recursos:
# - Utiliza ZeroMQ para escuchar solicitudes de los clientes y enviar respuestas.
# - Crea un hilo por cada programa que necesita procesar la asignación de recursos.
# - Utiliza un `lock` para proteger el acceso a los datos compartidos entre los hilos.
def manejar_dti():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://10.43.103.197:5556")

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
            resultados_programas = []  # Lista para almacenar los resultados de asignación de cada programa
            for programa in programas:
                hilo = threading.Thread(target=procesar_programa, args=(programa, facultad, semestre))
                hilo.start()
                hilos.append(hilo)

            for hilo in hilos:
                hilo.join()

            # Recopilar resultados por programa
            for programa in programas:
                clave = f"{facultad}_{semestre}"
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

            guardar_resultados_global()
            guardar_estado_asignaciones()

            # Responder con los resultados completos
            socket.send_json({
                "resultado": resultados_programas,
                    "estado": {
                        "salones_disponibles": disponibilidad_por_semestre[semestre]["salones"],
                        "laboratorios_disponibles": disponibilidad_por_semestre[semestre]["laboratorios"]
                    }
            })

        except Exception as e:
            print(f"[DTI] Error: {e}")
            socket.send_json({"status": "error", "mensaje": str(e)})

    socket.close()
    context.term()


# Función: iniciar_dti
# Parámetros: Ninguno
#
# Funcionalidad:
# Esta función inicializa el servidor DTI, cargando el estado de las asignaciones y luego lanzando el servidor 
# en un hilo separado para que pueda escuchar solicitudes concurrentes.
#
# Uso de recursos:
# - Llama a `cargar_estado_asignaciones` para inicializar el estado de las asignaciones.
# - Lanza el servidor DTI en un hilo separado usando `threading.Thread`.
def iniciar_dti():
    cargar_estado_asignaciones()
    dti_thread = threading.Thread(target=manejar_dti)
    dti_thread.start()


if __name__ == "__main__":
    iniciar_dti()
