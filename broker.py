import zmq, threading, time

BROKER_IP      = "10.43.96.74"
FRONTEND_PORT  = 5555      # facultades  / health-check
BACKEND_PORT   = 5560      # DTI-workers
CAPTURE_EP     = "inproc://capture"
PING_TIMEOUT   = 10        # segundos sin noticias → worker “down”

def broker():
    ctx = zmq.Context.instance()

    frontend = ctx.socket(zmq.ROUTER)
    frontend.bind(f"tcp://{BROKER_IP}:{FRONTEND_PORT}")

    backend  = ctx.socket(zmq.DEALER)
    backend.bind(f"tcp://{BROKER_IP}:{BACKEND_PORT}")

    # proxy capture
    capture  = ctx.socket(zmq.PUB)
    capture.bind(CAPTURE_EP)

    print("[Broker] Proxy ROUTER ⇆ DEALER iniciado …")

    # ----------------------------------------- #
    # tabla de workers vivos (id → timestamp)
    workers_alive = {}
    alive_lock    = threading.Lock()

    # hilo 1: escucha cada frame que pasa por el proxy
    def capturador():
        sub = ctx.socket(zmq.SUB)
        sub.connect(CAPTURE_EP)
        sub.setsockopt(zmq.SUBSCRIBE, b"")     # todo

        while True:
            frames = sub.recv_multipart()      # frames crudos
            if not frames:
                continue

            src_id = frames[0]                 # primera parte = identidad
            with alive_lock:
                workers_alive[src_id] = time.time()

    # hilo 2: imprime tabla de workers cada 5 s
    def reporter():
        while True:
            time.sleep(5)
            now = time.time()
            with alive_lock:
                vivos = {k: now - v for k, v in workers_alive.items()}
            print("\n[Broker] Estado de workers:")
            if not vivos:
                print("  (ningún worker ha respondido todavía)")
            for wid, dt in vivos.items():
                estado = "OK" if dt < PING_TIMEOUT else "TIMEOUT"
                print(f"  • id={wid.hex()}  último={dt:4.1f}s  ⇒ {estado}")
            print()

    # lanzar hilos
    threading.Thread(target=capturador, daemon=True).start()
    threading.Thread(target=reporter,   daemon=True).start()

    # proxy bloqueante
    try:
        zmq.proxy(frontend, backend, capture)
    except zmq.ContextTerminated:
        pass
    finally:
        frontend.close(); backend.close(); capture.close(); ctx.term()

if __name__ == "__main__":
    broker()
