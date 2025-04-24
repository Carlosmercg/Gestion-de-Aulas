import zmq
import multiprocessing
import time

# Función que maneja el envío de TODOS los programas de una facultad al DTI
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


# Función que maneja los programas de una facultad
def manejar_programas_facultad(facultad, puerto):
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://*:{puerto}")

    print(f"[Facultad {facultad}] Esperando solicitudes en puerto {puerto}...")

    while True:
        try:
            mensaje = socket.recv_json()
            semestre = mensaje.get('semestre')
            programa = mensaje.get('programa')

            if not semestre or not programa:
                respuesta = {"status": "error", "mensaje": "Datos incompletos"}
                socket.send_json(respuesta)
                continue

            print(f"[Facultad {facultad}] Recibido programa '{programa.get('nombre')}' para el semestre {semestre}.")

            # Responder a Programas
            socket.send_json({
                "status": "ok",
                "mensaje": f"Programa '{programa.get('nombre')}' procesado en {facultad}"
            })

            # Enviar el programa al DTI (en un solo mensaje)
            data = {
                "programas": [programa],  # Enviamos como lista para mantener compatibilidad
                "facultad": facultad,
                "semestre": semestre
            }
            p = multiprocessing.Process(target=enviar_a_dti, args=(data,))
            p.start()

        except Exception as e:
            print(f"[Facultad {facultad}] Error: {e}")
            break

    socket.close()
    context.term()

# Función principal
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
    for facultad, puerto in FACULTADES.items():
        p = multiprocessing.Process(target=manejar_programas_facultad, args=(facultad, puerto))
        p.start()
        procesos.append(p)

    for p in procesos:
        p.join()

if __name__ == "__main__":
    main()
