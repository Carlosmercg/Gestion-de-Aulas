import zmq
import multiprocessing
import signal
import sys

# Señal de parada global para procesos hijos
parar_evento = multiprocessing.Event()

def enviar_a_dti(data):
    try:
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://10.43.103.197:5556")
        socket.send_json(data)
        respuesta = socket.recv_json()
        
        print(f"\n[Facultad {data['facultad']}] Respuesta de DTI:")
        print(f"  - Estado: {respuesta.get('status')}")
        print(f"  - Mensaje: {respuesta.get('mensaje')}")

        if "resultados" in respuesta:
            for r in respuesta["resultados"]:
                print(f"  -> Programa: {r['programa']}")
                print(f"     Salones solicitados: {r['salones_solicitados']}")
                print(f"     Salones asignados: {r['salones_asignados']}")
                print(f"     Laboratorios solicitados: {r['laboratorios_solicitados']}")
                print(f"     Laboratorios asignados: {r['laboratorios_asignados']}")
                if "salones_como_laboratorios" in r:
                    print(f"     Salones usados como laboratorios: {r['salones_como_laboratorios']}")
                print()
    except Exception as e:
        print(f"[Facultad {data['facultad']}] Error al enviar al DTI: {e}")
    finally:
        socket.close()
        context.term()


def manejar_programas_facultad(facultad, puerto, evento_parar):
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://*:{puerto}")

    print(f"[{facultad}] Esperando solicitudes en puerto {puerto}...")

    try:
        while not evento_parar.is_set():
            if socket.poll(timeout=1000):  # Espera de 1 segundo
                mensaje = socket.recv_json()
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

                data = {
                    "programas": [programa],
                    "facultad": facultad,
                    "semestre": semestre
                }
                p = multiprocessing.Process(target=enviar_a_dti, args=(data,))
                p.start()
    except Exception as e:
        print(f"[{facultad}] Error en el servidor: {e}")
    finally:
        socket.close()
        context.term()


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

    procesos = []

    def cerrar_todo(sig, frame):
        print("\n[Cliente] Señal de interrupción recibida. Finalizando procesos...")
        parar_evento.set()
        for p in procesos:
            p.join()
        print("[Cliente] Todos los procesos han terminado. Saliendo.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cerrar_todo)
    signal.signal(signal.SIGTERM, cerrar_todo)

    for facultad, puerto in FACULTADES.items():
        p = multiprocessing.Process(target=manejar_programas_facultad, args=(facultad, puerto, parar_evento))
        p.start()
        procesos.append(p)

    for p in procesos:
        p.join()


if __name__ == "__main__":
    main()
