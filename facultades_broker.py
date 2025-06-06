import zmq
import multiprocessing
import signal
import sys
from filelock import FileLock
import os, json
import time  

# Señal de parada global para procesos hijos
parar_evento = multiprocessing.Event()

# Función: enviar_a_dti
# Parámetros:
#   - data (dict): Datos a enviar al DTI, que incluyen el semestre, facultad y los programas.
#
# Funcionalidad:
# Esta función se encarga de enviar los datos de la facultad al servidor DTI. Utiliza ZeroMQ para la comunicación
# con el servidor DTI y espera recibir una respuesta con los resultados de la asignación de recursos.
# Imprime la respuesta de DTI en consola y si los resultados están disponibles, los imprime detalladamente.
#
# Uso de recursos:
# - Utiliza ZeroMQ para enviar y recibir mensajes con el servidor DTI.
# - Maneja errores de comunicación y cierra el socket y contexto al finalizar.

ESTADO_FILE   = "resultados/estado_asignaciones.json"
RESULTADOS_GLOB = "resultados/asignacion_completa_{semestre}.json"

HEALTH_SERVICE_EP = "tcp://10.43.96.74:6000"

BROKERS_FRONT = [
    "tcp://10.43.96.74:5555",   # primario
    "tcp://10.43.103.30:5556",  # secundario
]

# Estructuras en memoria (se rellenan por cada respuesta del DTI)
estado_asignaciones = {}          # { semestre: {salones_disponibles, ...} }
resultados_asignacion = {}        # { f"{facultad}_{semestre}": [resultados...] }

# ──────────────── variables compartidas para el cronómetro ─────────────
start_time = multiprocessing.Value('d', 0.0)   # 1ª respuesta exitosa (epoch)
end_time   = multiprocessing.Value('d', 0.0)   # Última respuesta exitosa
time_lock  = multiprocessing.Lock()
# ───────────────────────────────────────────────────────────────────────────────
parar_evento = multiprocessing.Event()


def _ensure_dir():
    os.makedirs("resultados", exist_ok=True)

def guardar_estado_asignaciones() -> None:
    _ensure_dir()
    with FileLock("resultados/lock"):
        if os.path.exists(ESTADO_FILE):
            with open(ESTADO_FILE, "r", encoding="utf-8") as f:
                acumulado = json.load(f)
        else:
            acumulado = {}

        # merge por semestre
        for sem, estado in estado_asignaciones.items():
            acumulado[sem] = estado   # reemplaza / actualiza

        with open(ESTADO_FILE, "w", encoding="utf-8") as f:
            json.dump(acumulado, f, ensure_ascii=False, indent=4)


def guardar_resultados_global(semestre: str) -> None:
    _ensure_dir()
    # aplanar lo que esta FACULTAD acaba de recibir
    nuevos = []
    for clave, items in resultados_asignacion.items():
        fac, sem = clave.rsplit("_", 1)
        if sem == semestre:
            nuevos.extend([{**r, "facultad": fac} for r in items])

    fname = RESULTADOS_GLOB.format(semestre=semestre)

    with FileLock("resultados/lock"):
        # 1️⃣ cargar lo que ya existe
        if os.path.exists(fname):
            with open(fname, "r", encoding="utf-8") as f:
                acumulado = json.load(f)
        else:
            acumulado = []

        # 2️⃣ concatenar y quitar duplicados (clave: facultad+programa)
        by_key = { (r["facultad"], r["programa"]) : r for r in acumulado }
        for r in nuevos:
            by_key[(r["facultad"], r["programa"])] = r

        # 3️⃣ escribir todo junto
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(list(by_key.values()), f, ensure_ascii=False, indent=4)

def _obtener_broker_front(ctx: zmq.Context) -> list[str]:
    """
    Devuelve una lista de endpoints front.
    • Consulta al health-service: el que responda ‘vivo’ va primero.
    • Si el health-service no contesta (timeout) se usa la lista fija.
    """
    hs = ctx.socket(zmq.REQ)
    hs.setsockopt(zmq.RCVTIMEO, 1500)   # 1,5 s
    hs.setsockopt(zmq.SNDTIMEO,  500)
    hs.connect(HEALTH_SERVICE_EP)

    try:
        hs.send_string("front")
        activo = hs.recv_string()            # puede lanzar zmq.error.Again
        # prioriza el que reportó el health-service
        return [activo] + [ep for ep in BROKERS_FRONT if ep != activo]
    except zmq.error.Again:
        return BROKERS_FRONT[:]              # copia de seguridad
    finally:
        hs.close()


def enviar_a_dti(data, start_time, end_time, time_lock):
    """
    Envía la solicitud al DTI por *todos* los brokers disponibles.
    Reintenta dos veces si nadie responde dentro del RCVTIMEO.
    """
    ctx = zmq.Context.instance()
    respuesta_dti = None

    for intento in (1, 2):                           # intento + reintento
        broker_eps = _obtener_broker_front(ctx)      # ahora es LISTA

        sock = ctx.socket(zmq.REQ)
        sock.setsockopt(zmq.LINGER,    0)            # cierra sin bloquear
        sock.setsockopt(zmq.IMMEDIATE, 1)            # falla rápido si no hay peer
        sock.setsockopt(zmq.RCVTIMEO, 30000)         # 30 s espera respuesta DTI
        sock.setsockopt(zmq.SNDTIMEO,  3000)         # 3 s envío

        for ep in broker_eps:                        # 🔗 conecta a TODOS
            sock.connect(ep)

        try:
            sock.send_json(data)
            respuesta_dti = sock.recv_json()         # puede lanzar Again

            # ─ cronómetro ───────────────────────────────────────────────
            with time_lock:
                now = time.time()
                if start_time.value == 0.0:
                    start_time.value = now
                end_time.value = now
            # ────────────────────────────────────────────────────────────
            break                                    # ✅ éxito

        except zmq.error.Again:
            print(f"[Facultad {data['facultad']}] "
                  f"Ningún broker respondió (intento {intento}).")
        finally:
            sock.close()

    if respuesta_dti is None:                        # los dos intentos fallaron
        print(f"[Facultad {data['facultad']}] "
              f"No se obtuvo respuesta de ningún broker.")
        return                              # o raise, según convenga

    # --------------- actualizar estructuras -----------------
    semestre = data["semestre"]
    clave    = f"{data['facultad']}_{semestre}"
    resultados_asignacion.setdefault(clave, []).extend(respuesta_dti["resultado"])
    estado_asignaciones[semestre] = respuesta_dti["estado"]
    guardar_resultados_global(semestre)

    respuesta_transformada = {
            "status": "ok",
            "mensaje": f"Asignación completada para {data['facultad']} - Semestre {data['semestre']}",
            "resultados": respuesta_dti.get("resultado", []),
            "estado": respuesta_dti.get("estado", {})
        }


    for r in respuesta_transformada["resultados"]:
        print(f"  -> Programa: {r['programa']}")
        print(f"     Salones solicitados: {r['salones_solicitados']}")
        print(f"     Salones asignados: {r['salones_asignados']}")
        print(f"     Laboratorios solicitados: {r['laboratorios_solicitados']}")
        print(f"     Laboratorios asignados: {r['laboratorios_asignados']}")
        if "salones_como_laboratorios" in r:
            print(f"     Salones usados como laboratorios: {r['salones_como_laboratorios']}")
        print()



# Función: manejar_programas_facultad
# Parámetros:
#   - facultad (str): El nombre de la facultad.
#   - puerto (int): El puerto asignado a la facultad para la comunicación.
#   - evento_parar (multiprocessing.Event): Evento que se utiliza para parar los procesos hijos.
#
# Funcionalidad:
# Esta función se encarga de manejar las solicitudes que llegan a la facultad en el puerto especificado. 
# Recibe los datos de los programas a través de un socket de tipo REP (reply) y procesa cada programa.
# Si los datos del programa son válidos, envía la solicitud a DTI usando `enviar_a_dti` en un proceso hijo.
# La función se ejecuta en un bucle hasta que se reciba una señal de parada.
#
# Uso de recursos:
# - Utiliza un socket de tipo REP para recibir las solicitudes.
# - Cada solicitud procesada genera un nuevo proceso para llamar a `enviar_a_dti`.
def manejar_programas_facultad(facultad, puerto, evento_parar):
    context = zmq.Context()  # Crear contexto de ZeroMQ
    socket = context.socket(zmq.REP)  # Crear socket de tipo REP
    socket.bind(f"tcp://*:{puerto}")  # Vincular el socket al puerto

    print(f"[{facultad}] Esperando solicitudes en puerto {puerto}...")

    try:
        while not evento_parar.is_set():  # Mientras el evento de parada no esté activado
            if socket.poll(timeout=1000):  # Esperar 1 segundo para nuevas solicitudes
                mensaje = socket.recv_json()  # Recibir mensaje de la facultad
                semestre = mensaje.get('semestre')
                programa = mensaje.get('programa')

                if not semestre or not programa:
                    socket.send_json({"status": "error", "mensaje": "Datos incompletos"})
                    continue

                print(f"[{facultad}] Recibido programa '{programa.get('nombre')}' para el semestre {semestre}.")
                socket.send_json({
                    "status": "ok",
                    "mensaje": f"Programa '{programa.get('nombre')}' procesado en {facultad}"
                })

                # Preparar los datos para enviar a DTI
                data = {
                    "programas": [programa],
                    "facultad": facultad,
                    "semestre": semestre
                }
                p = multiprocessing.Process(
                    target=enviar_a_dti,
                    args=(data, start_time, end_time, time_lock)
                )
                p.start()
    except Exception as e:
        print(f"[{facultad}] Error en el servidor: {e}")
    finally:
        socket.close()  # Cerrar el socket
        context.term()  # Terminar el contexto de ZeroMQ


# Función principal: main
#
# Funcionalidad:
# La función principal que configura y arranca un servidor para cada facultad, con un puerto asignado. 
# Maneja las señales de interrupción (SIGINT y SIGTERM) para permitir la finalización ordenada de los procesos.
# La función también inicializa el proceso de manejar programas de cada facultad en paralelo utilizando `multiprocessing`.
#
# Uso de recursos:
# - Configura la lista de facultades y sus puertos.
# - Gestiona las señales de terminación para finalizar todos los procesos cuando se interrumpe la ejecución.
def main():
    FACULTADES = {
        "Facultad de Ciencias Sociales": 6000,
        "Facultad de Ciencias Naturales": 6010,
        "Facultad de Ingeniería": 6020,
        "Facultad de Medicina": 6030,
        "Facultad de Derecho": 6040,
        "Facultad de Artes": 6050,
        "Facultad de Educación": 6060,
        "Facultad de Ciencias Económicas": 6070,
        "Facultad de Arquitectura": 6080,
        "Facultad de Tecnología": 6090,
    }

    procesos = []  # Lista de procesos que se van a ejecutar

    def cerrar_todo(sig, _):
        parar_evento.set()
        for p in procesos: p.join()
        # ─── Mostrar duración total ─────────────────────────────────────────
        dur = end_time.value - start_time.value
        if start_time.value and dur >= 0:
            print(f"\n[Cliente] Tiempo total entre 1ª y última solicitud: {dur:.2f}s")
        else:
            print("\n[Cliente] No se registraron solicitudes exitosas.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cerrar_todo)
    signal.signal(signal.SIGTERM, cerrar_todo)

    for fac, port in FACULTADES.items():
        p = multiprocessing.Process(target=manejar_programas_facultad,
                                    args=(fac, port, parar_evento))
        p.start(); procesos.append(p)

    for p in procesos: p.join()


if __name__ == "__main__":
    main()  # Ejecutar la función principal
