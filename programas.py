import zmq
import json
import multiprocessing
import signal
import sys

# Enviar un solo programa a la facultad
def enviar_a_facultad(programa, semestre, facultad, puerto):
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

# Enviar todos los programas de una facultad, cada uno en su propio proceso
def procesar_envio_programas(facultad_info, semestre, puerto):
    facultad = facultad_info["nombre"]
    programas = facultad_info["programas"]

    procesos = []
    for programa in programas:
        p = multiprocessing.Process(target=enviar_a_facultad, args=(programa, semestre, facultad, puerto))
        p.start()
        procesos.append(p)

    for p in procesos:
        p.join()

# Función principal: leer JSON y despachar programas a las facultades
def main():
    procesos_facultades = []

    def cerrar_todo(sig, frame):
        print("\n[Cliente JSON] Interrupción recibida. Terminando procesos...")
        for p in procesos_facultades:
            p.terminate()
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

        for facultad_info in programas_data["facultades"]:
            facultad = facultad_info["nombre"]
            puerto = FACULTADES.get(facultad)
            if puerto:
                p = multiprocessing.Process(target=procesar_envio_programas, args=(facultad_info, semestre, puerto))
                p.start()
                procesos_facultades.append(p)
            else:
                print(f"Advertencia: No se encontró puerto para la facultad '{facultad}'")

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
