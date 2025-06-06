"""
Envia un `{"tipo":"ping"}` al broker cada N segundos.
El broker lo reenvía a algún DTI-worker, el worker responde
`{"status":"ok"}` y health_check muestra el tiempo de ida y vuelta.
"""

import zmq, time, json

BROKER_IP     = "10.43.96.74"
FRONTEND_PORT = 5555          # mismo puerto que usan las facultades
INTERVAL      = 3             # segundos entre pings

def main():
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.connect(f"tcp://{BROKER_IP}:{FRONTEND_PORT}")
    print("[HC] Enviando pings cada", INTERVAL, "s … Ctrl+C para salir")

    while True:
        t0 = time.time()
        sock.send_json({"tipo": "ping"})
        try:
            rep = sock.recv_json(flags=0, timeout=INTERVAL * 1000)
            dt  = time.time() - t0
            print(f"[HC] PONG recibido en {dt:.3f}s → {json.dumps(rep)}")
        except zmq.error.Again:
            print("[HC] ‼  timeout  ‼  el broker o los workers no respondieron")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
