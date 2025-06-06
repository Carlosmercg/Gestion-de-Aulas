import zmq
import threading

def broker():
    context = zmq.Context()

    frontend = context.socket(zmq.ROUTER)
    frontend.bind("tcp://10.43.96.74:5555")

    backend = context.socket(zmq.DEALER)
    backend.bind("tcp://10.43.96.74:5560")

    # Socket para capturar los mensajes del proxy
    capture = context.socket(zmq.PUB)
    capture.bind("inproc://capture")

    print("[Broker] Iniciando broker entre facultades y DTI...")

    def capturador():
        ctx = zmq.Context()
        subs = ctx.socket(zmq.SUB)
        subs.connect("inproc://capture")
        subs.setsockopt(zmq.SUBSCRIBE, b"")

        solicitud_counter = 1

        while True:
            msg = subs.recv_multipart()

            if len(msg) >= 2:
                # Solo mostramos lo básico, no todo el contenido
                origen = msg[0]  # Identidad del cliente (ej. facultad)
                print(f"[Broker] Solicitud #{solicitud_counter} enviada desde [{origen.decode(errors='ignore')}]")
                solicitud_counter += 1
            else:
                print(f"[Broker] Mensaje capturado sin formato esperado: {msg}")

    # Lanzar el hilo capturador
    threading.Thread(target=capturador, daemon=True).start()

    # Lanzar el proxy principal
    try:
        zmq.proxy(frontend, backend, capture)
    except zmq.ContextTerminated:
        print("[Broker] Contexto terminado")
    finally:
        frontend.close()
        backend.close()
        capture.close()
        context.term()

if __name__ == "__main__":
    broker_thread = threading.Thread(target=broker)
    broker_thread.start()
