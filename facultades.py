import zmq
import multiprocessing
import signal
import sys

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
def enviar_a_dti(data):
    servidores = [
        "tcp://10.43.103.197:5556",  # Servidor principal
        "tcp://10.43.96.74:5556",  # Servidor auxiliar
    ]

    ctx = zmq.Context()
    for servidor in servidores:
        try:
            sock = ctx.socket(zmq.REQ)
            sock.connect(servidor)
            sock.RCVTIMEO = 3000      # 3 s de espera recepción
            sock.SNDTIMEO = 3000      # 3 s de espera envío

            sock.send_json(data)
            respuesta = sock.recv_json()

            # — imprime respuesta —
            print(f"\n[{data['facultad']}] Respuesta de {servidor}:")
            for r in respuesta.get("resultado", []):
                print(f"  → {r['programa']}: "
                      f"{r['salones_asignados']}/{r['salones_solicitados']} salones, "
                      f"{r['laboratorios_asignados']}/{r['laboratorios_solicitados']} labs")

            sock.close()
            return                         # ⬅️ éxito: salimos de la función
        except Exception as e:
            print(f"[Facultad {data['facultad']}] Error al enviar a {servidor}: {e}")
            try:
                sock.close()
            except:
                pass

    # Si llegamos aquí, ningún servidor respondió
    print(f"[Facultad {data['facultad']}] No se pudo conectar a ningún servidor DTI.")
    ctx.term()


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
                p = multiprocessing.Process(target=enviar_a_dti, args=(data,))  # Crear proceso para enviar a DTI
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

    def cerrar_todo(sig, frame):
        print("\n[Cliente] Señal de interrupción recibida. Finalizando procesos...")
        parar_evento.set()  # Activar evento de parada
        for p in procesos:
            p.join()  # Esperar que todos los procesos terminen
        print("[Cliente] Todos los procesos han terminado. Saliendo.")
        sys.exit(0)  # Finalizar el programa

    signal.signal(signal.SIGINT, cerrar_todo)  # Manejar interrupciones
    signal.signal(signal.SIGTERM, cerrar_todo)  # Manejar terminaciones

    # Crear un proceso para cada facultad
    for facultad, puerto in FACULTADES.items():
        p = multiprocessing.Process(target=manejar_programas_facultad, args=(facultad, puerto, parar_evento))
        p.start()  # Iniciar el proceso
        procesos.append(p)  # Agregar el proceso a la lista

    # Esperar que todos los procesos terminen
    for p in procesos:
        p.join()


if __name__ == "__main__":
    main()  # Ejecutar la función principal