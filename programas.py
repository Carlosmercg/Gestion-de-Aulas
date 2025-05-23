import zmq
import json
import multiprocessing

# Función: enviar_a_facultad
# Parámetros:
#   - programa (str): Nombre del programa a enviar.
#   - semestre (str): El semestre correspondiente al programa.
#   - facultad (str): El nombre de la facultad a la que se enviará el programa.
#   - puerto (int): El puerto de la facultad para la comunicación.
#
# Funcionalidad:
# Esta función se encarga de enviar los datos de un programa a una facultad a través de un socket ZeroMQ.
# Utiliza un contexto de ZeroMQ para crear un socket de tipo REQ (request) y realiza una conexión al puerto
# correspondiente a la facultad. Los datos del programa (semestre, facultad, y nombre del programa) se envían
# en formato JSON. Se espera una respuesta del servidor de la facultad, que se imprime en consola.
#
# Uso de recursos:
# - Utiliza un socket ZeroMQ para la comunicación.
# - El contexto y socket son cerrados adecuadamente para liberar recursos al finalizar.
def enviar_a_facultad(programa, semestre, facultad, puerto):
    try:
        context = zmq.Context()  # Crear contexto ZeroMQ
        socket = context.socket(zmq.REQ)  # Crear socket de tipo REQ (Request)
        socket.connect(f"tcp://10.43.103.102:{puerto}")  # Conectar al puerto correspondiente

        # Preparar los datos para enviar
        data = {
            "semestre": semestre,
            "facultad": facultad,
            "programa": programa
        }

        socket.send_json(data)  # Enviar los datos al servidor
        respuesta = socket.recv_json()  # Esperar y recibir la respuesta

        # Imprimir la respuesta recibida
        print(f"Respuesta de {facultad}: {respuesta['mensaje']}")

    except Exception as e:
        print(f"Error al enviar datos a la facultad en el puerto {puerto}: {e}")
    finally:
        socket.close()  # Cerrar el socket
        context.term()  # Terminar el contexto de ZeroMQ

# Función: procesar_envio_programas
# Parámetros:
#   - facultad_info (dict): Diccionario con la información de la facultad (nombre y programas).
#   - semestre (str): El semestre correspondiente a los programas.
#   - puerto (int): El puerto asignado a la facultad para la comunicación.
#
# Funcionalidad:
# Esta función crea un proceso independiente para enviar cada programa de la facultad.
# Se crean procesos hijos utilizando la librería `multiprocessing` para evitar bloquear el hilo principal,
# permitiendo el envío paralelo de múltiples programas.
#
# Uso de recursos:
# - Usa `multiprocessing.Process` para crear procesos independientes.
# - Cada proceso ejecuta la función `enviar_a_facultad` para enviar los datos del programa.
def procesar_envio_programas(facultad_info, semestre, puerto):
    facultad = facultad_info["nombre"]  # Extraer el nombre de la facultad
    programas = facultad_info["programas"]  # Obtener la lista de programas

    # Lista para almacenar los procesos creados
    procesos = []
    for programa in programas:
        # Crear un proceso por cada programa a enviar
        p = multiprocessing.Process(target=enviar_a_facultad, args=(programa, semestre, facultad, puerto))
        p.start()  # Iniciar el proceso
        procesos.append(p)  # Almacenar el proceso en la lista

    # Esperar que todos los procesos terminen antes de continuar
    for p in procesos:
        p.join()

# Función principal: main
#
# Funcionalidad:
# La función principal que se encarga de leer los datos de un archivo JSON que contiene la información de
# los programas y facultades, y luego enviar esta información a cada facultad a través de la función
# `procesar_envio_programas`. Además, gestiona la asignación de puertos y maneja excepciones relacionadas
# con la apertura y lectura del archivo JSON.
#
# Uso de recursos:
# - Lee el archivo `solicitudes.json` para obtener los datos de los programas.
# - Itera sobre las facultades y les asigna un puerto correspondiente.
# - Llama a `procesar_envio_programas` para cada facultad con sus programas.
def main():
    try:
        # Abre el archivo JSON que contiene los datos de los programas
        with open('solicitudes.json', 'r', encoding='utf-8') as f:
            programas_data = json.load(f)  # Cargar datos JSON desde el archivo

        semestre = programas_data["semestre"]  # Extraer el semestre de los datos

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
            facultad = facultad_info["nombre"]  # Nombre de la facultad
            puerto = FACULTADES.get(facultad)  # Obtener el puerto correspondiente
            if puerto:
                procesar_envio_programas(facultad_info, semestre, puerto)  # Enviar los programas
            else:
                print(f"Advertencia: No se encontró puerto para la facultad '{facultad}'")

    except FileNotFoundError:
        print("Error: No se encontró el archivo 'solicitudes.json'")  # Manejar archivo no encontrado
    except json.JSONDecodeError:
        print("Error: El archivo 'solicitudes.json' no tiene un formato JSON válido")  # Manejar error de formato JSON
    except Exception as e:
        print(f"Error inesperado: {e}")  # Manejar cualquier otro error inesperado

if __name__ == "__main__":
    main()  # Ejecutar la función principal
