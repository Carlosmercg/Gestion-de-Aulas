import zmq
import json
import multiprocessing

# Función que maneja la comunicación con las facultades
def enviar_a_facultad(programa, semestre, facultad, puerto):
    try:
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(f"tcp://localhost:{puerto}")

        # Enviar un solo programa a la facultad
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

# Función para enviar cada programa en un proceso independiente
def procesar_envio_programas(facultad_info, semestre, puerto):
    facultad = facultad_info["nombre"]
    programas = facultad_info["programas"]

    # Enviar cada programa en un proceso separado
    procesos = []
    for programa in programas:
        p = multiprocessing.Process(target=enviar_a_facultad, args=(programa, semestre, facultad, puerto))
        p.start()
        procesos.append(p)

    for p in procesos:
        p.join()

# Función principal para leer el JSON y enviar los datos a las facultades
def main():
    try:
        # Abre el archivo JSON que contiene los datos de los programas
        with open('solicitudes.json', 'r', encoding='utf-8') as f:
            programas_data = json.load(f)

        semestre = programas_data["semestre"]

        # Definir puertos de las facultades (de 6000 a 6090)
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

        # Iterar sobre las facultades y enviar los programas
        for facultad_info in programas_data["facultades"]:
            facultad = facultad_info["nombre"]
            puerto = FACULTADES.get(facultad)
            if puerto:
                procesar_envio_programas(facultad_info, semestre, puerto)
            else:
                print(f"Advertencia: No se encontró puerto para la facultad '{facultad}'")

    except FileNotFoundError:
        print("Error: No se encontró el archivo 'solicitudes.json'")
    except json.JSONDecodeError:
        print("Error: El archivo 'solicitudes.json' no tiene un formato JSON válido")
    except Exception as e:
        print(f"Error inesperado: {e}")

if __name__ == "__main__":
    main()
