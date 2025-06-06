#!/usr/bin/env python3
import zmq, threading

IP          = "10.43.96.74"
FRONT_PORT  = 5555          # ROUTER  (clientes / facultades)
BACK_PORT   = 5560          # DEALER  (DTI workers)
HB_PORT     = 5570          # REP     (heartbeat)

def broker():
    ctx = zmq.Context()

    # ---------- sockets principales ----------
    front = ctx.socket(zmq.ROUTER)
    front.bind(f"tcp://{IP}:{FRONT_PORT}")

    back  = ctx.socket(zmq.DEALER)
    back.bind(f"tcp://{IP}:{BACK_PORT}")

    # ---------- captura tráfico --------------
    capture = ctx.socket(zmq.PUB)
    capture.bind("inproc://capture")

    # ---------- heartbeat REP ----------------
    hb = ctx.socket(zmq.REP)
    hb.bind(f"tcp://{IP}:{HB_PORT}")

    def capturador():
        subs = ctx.socket(zmq.SUB)
        subs.connect("inproc://capture")
        subs.setsockopt(zmq.SUBSCRIBE, b"")
        n = 1
        while True:
            frames = subs.recv_multipart()
            if len(frames) >= 2:
                origen = frames[0].hex()[:6]
                print(f"[Primario] Solicitud #{n} de {origen}")
                n += 1

    def heartbeater():
        while True:
            try:
                hb.recv()           # bloqueante
                hb.send(b"PONG")
            except zmq.ContextTerminated:
                break

    threading.Thread(target=capturador, daemon=True).start()
    threading.Thread(target=heartbeater, daemon=True).start()

    print(f"[Primario] Proxy ROUTER⇆DEALER activo en {IP} "
          f"(front:{FRONT_PORT} back:{BACK_PORT} HB:{HB_PORT})")

    try:
        zmq.proxy(front, back, capture)
    except zmq.ContextTerminated:
        pass
    finally:
        front.close(); back.close(); capture.close(); hb.close(); ctx.term()

if __name__ == "__main__":
    broker()
