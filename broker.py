import zmq, threading, time

BROKER_IP        = "10.43.96.74"
FRONT_PORT       = 5555
BACK_PORT        = 5560
CAPTURE_EP       = "inproc://capture"
TIMEOUT_WORKER   = 15        # s sin tráfico ⇒ TIMEOUT

def broker():
    ctx = zmq.Context.instance()

    front = ctx.socket(zmq.ROUTER)
    front.bind(f"tcp://{BROKER_IP}:{FRONT_PORT}")

    back  = ctx.socket(zmq.DEALER)
    back.bind(f"tcp://{BROKER_IP}:{BACK_PORT}")

    cap   = ctx.socket(zmq.PUB)
    cap.bind(CAPTURE_EP)

    workers = {}          # id (bytes) → último timestamp
    w_lock  = threading.Lock()

    # ----- hilo 1: captura tráfico y marca workers vivos ---------
    def capturador():
        sub = ctx.socket(zmq.SUB)
        sub.connect(CAPTURE_EP)
        sub.setsockopt(zmq.SUBSCRIBE, b"")
        while True:
            frames = sub.recv_multipart()
            if frames:
                wid = frames[0]            # identidad que envía
                with w_lock:
                    workers[wid] = time.time()

    # ----- hilo 2: imprime tabla cada 5 s ------------------------
    def reporter():
        while True:
            time.sleep(5)
            now   = time.time()
            with w_lock:
                status = {wid: now - ts for wid, ts in workers.items()}
            print("\n[Broker] Workers registrados:")
            if not status:
                print("  (ninguno)")
            for wid, dt in status.items():
                state = "OK" if dt < TIMEOUT_WORKER else "TIMEOUT"
                print(f"  • {wid.decode()[:6]}  último {dt:4.1f}s → {state}")
            print()

    threading.Thread(target=capturador, daemon=True).start()
    threading.Thread(target=reporter,   daemon=True).start()

    print("[Broker] Proxy ROUTER⇆DEALER ejecutándose …")
    try:
        zmq.proxy(front, back, cap)
    except zmq.ContextTerminated:
        pass

if __name__ == "__main__":
    broker()
