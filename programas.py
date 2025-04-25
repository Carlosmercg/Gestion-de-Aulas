import zmq
import json
import multiprocessing
import signal
import sys
from queue import Queue

# Enviar un solo programa a la facultad
def enviar_a_facultad(queue):
    while True:
        programa, semestre, facultad, puerto = queue.get()
        if programa is None:
            break
        try:
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.connect(f"tcp://10.43.103.102:{puerto}")

            data = {
                "semestre": semestre,
                "facultad": facultad,
                "programa": programa
            }

            socket.send_json(data)
            respuesta = socket.recv_json()
            print(f"Respuesta de {facultad}: {respuesta['mensaje']}")

        except Exception as e:
            print(f"Error al enviar datos a la facultad en el puerto {puerto}: {e}")
        finally:
            socket.close()
            context.term()

# Función principal: leer JSON y despachar programas a las facultades
def main():
    procesos_facultades = []
    queue = Queue()

    def cerrar_todo(sig, frame):
        print("\n[Cliente JSON] Interrupción recibida. Terminando procesos...")
        # Detener los trabajadores
        for _ in range(multiprocessing.cpu_count()):
            queue.put((None, None, None, None))
        for p in procesos_facultades:
            p.join()
        sys.exit(0)

    # Registrar señales para Ctrl+C y otros cierres
    signal.signal(signal.SIGINT, cerrar_todo)
    signal.signal(signal.SIGTERM, cerrar_todo)

    try:
        with open('solicitudes.json', 'r', encoding='utf-8') as f:
            programas_data = json.load(f)

        semestre = programas_data["semestre"]

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

        # Iniciar el número de trabajadores igual al número de CPUs disponibles
        for _ in range(multiprocessing.cpu_count()):
            p = multiprocessing.Process(target=enviar_a_facultad, args=(queue,))
            p.start()
            procesos_facultades.append(p)

        # Procesar cada facultad y sus programas
        for facultad_info in programas_data["facultades"]:
            facultad = facultad_info["nombre"]
            puerto = FACULTADES.get(facultad)
            if puerto:
                for programa in facultad_info["programas"]:
                    # Enviar cada programa a la cola para que lo procese un trabajador
                    queue.put((programa, semestre, facultad, puerto))
            else:
                print(f"Advertencia: No se encontró puerto para la facultad '{facultad}'")

        # Esperar a que todos los procesos terminen
        for p in procesos_facultades:
            p.join()

    except FileNotFoundError:
        print("Error: No se encontró el archivo 'solicitudes.json'")
    except json.JSONDecodeError:
        print("Error: El archivo 'solicitudes.json' no tiene un formato JSON válido")
    except Exception as e:
        print(f"Error inesperado: {e}")

if __name__ == "__main__":
    main()
