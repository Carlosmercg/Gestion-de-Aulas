#!/usr/bin/env python3
"""
Devuelve la dirección del broker activo.
   • recibe   "front"  → responde ep ROUTER  (clientes)
   • recibe   "back"   → responde ep DEALER  (workers DTI)
"""

import zmq, time

# --- direcciones fijas -------------------------------------------------------
PRIMARY_HB   = "tcp://10.43.96.74:5570"   # puerto heartbeat broker primario
PRIMARY_FRT  = "tcp://10.43.96.74:5555"
PRIMARY_BCK  = "tcp://10.43.96.74:5560"

SECONDARY_HB = "tcp://10.43.103.30:5571"  # puerto heartbeat broker respaldo
SECONDARY_FRT= "tcp://10.43.103.30:5556"
SECONDARY_BCK= "tcp://10.43.103.30:5561"

# --- helper: ping ------------------------------------------------------------
def vivo(addr: str, timeout_ms: int = 1000) -> bool:
    ctx = zmq.Context.instance()
    s   = ctx.socket(zmq.REQ)
    s.setsockopt(zmq.LINGER,   0)
    s.setsockopt(zmq.RCVTIMEO, timeout_ms)
    s.setsockopt(zmq.SNDTIMEO, timeout_ms)
    try:
        s.connect(addr)
        s.send(b"PING")
        return s.recv() == b"PONG"
    except zmq.ZMQError:
        return False
    finally:
        s.close()

# --- bucle REP ---------------------------------------------------------------
ctx  = zmq.Context()
rep  = ctx.socket(zmq.REP)
rep.bind("tcp://*:6000")
print("[Health] Servicio activo en tcp://*:6000")

while True:
    what = rep.recv_string()          # «front» o «back»
    primary_ok = vivo(PRIMARY_HB)
    if primary_ok:
        front, back = PRIMARY_FRT, PRIMARY_BCK
    else:
        front, back = SECONDARY_FRT, SECONDARY_BCK
    rep.send_string(front if what == "front" else back)
