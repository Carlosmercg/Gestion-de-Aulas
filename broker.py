import zmq
import threading

def broker():
    context = zmq.Context()

    # Socket para recibir mensajes de las facultades
    frontend = context.socket(zmq.ROUTER)
    frontend.bind("tcp://10.43.96.74:5555")  # REQ de facultades

    # Socket para comunicarse con el DTI
    backend = context.socket(zmq.DEALER)
    backend.bind("tcp://10.43.96.74:5560")   # REP de DTI-workers

    print("[Broker] Iniciando broker entre facultades y DTI...")

    # Proxy que reenvía mensajes entre ROUTER y DEALER
    try:
        zmq.proxy(frontend, backend)
    except zmq.ContextTerminated:
        print("[Broker] Contexto terminado")
    finally:
        frontend.close()
        backend.close()
        context.term()

if __name__ == "__main__":
    broker_thread = threading.Thread(target=broker)
    broker_thread.start()
