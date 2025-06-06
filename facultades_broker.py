import zmq, multiprocessing, signal, sys, json, os, time
from filelock import FileLock

# ──────────────── NUEVO: variables compartidas para el cronómetro ─────────────
start_time = multiprocessing.Value('d', 0.0)   # 1ª respuesta exitosa (epoch)
end_time   = multiprocessing.Value('d', 0.0)   # Última respuesta exitosa
time_lock  = multiprocessing.Lock()
# ───────────────────────────────────────────────────────────────────────────────

parar_evento = multiprocessing.Event()

# ----------------------------------------------------------------------------- #
#                               UTILIDADES                                      #
# ----------------------------------------------------------------------------- #
ESTADO_FILE   = "resultados/estado_asignaciones.json"
RESULTADOS_GLOB = "resultados/asignacion_completa_{semestre}.json"
HEALTH_SERVICE_EP = "tcp://10.43.96.74:6000"

estado_asignaciones = {}
resultados_asignacion = {}

# … (funciones _ensure_dir, guardar_estado_asignaciones, guardar_resultados_global)
# … (sin cambios)

def _obtener_broker_front(ctx: zmq.Context) -> str | None:
    hs = ctx.socket(zmq.REQ)
    hs.setsockopt(zmq.RCVTIMEO, 2000)
    hs.setsockopt(zmq.SNDTIMEO, 2000)
    hs.connect(HEALTH_SERVICE_EP)
    try:
        hs.send_string("front")
        return hs.recv_string()
    except zmq.error.Again:
        return None
    finally:
        hs.close()

# ----------------------------------------------------------------------------- #
#                           ENVÍO AL DTI  (CRONÓMETRO)                          #
# ----------------------------------------------------------------------------- #
def enviar_a_dti(data, start_time, end_time, time_lock):
    ctx = zmq.Context.instance()
    respuesta_dti = None

    for intento in (1, 2):
        broker_addr = _obtener_broker_front(ctx)
        if not broker_addr:                          # health service no respondió
            continue
        sock = ctx.socket(zmq.REQ)
        sock.setsockopt(zmq.RCVTIMEO, 5000)
        sock.setsockopt(zmq.SNDTIMEO, 5000)
        try:
            sock.connect(broker_addr)
            sock.send_json(data)
            respuesta_dti = sock.recv_json()
            # ─── CRONÓMETRO ────────────────────────────────────────────────
            with time_lock:
                now = time.time()
                if start_time.value == 0.0:
                    start_time.value = now          # primera respuesta
                end_time.value = now                # última respuesta
            # ────────────────────────────────────────────────────────────────
            break
        except zmq.error.Again:
            print(f"[Facultad {data['facultad']}] "
                  f"Broker {broker_addr} no respondió (intento {intento}).")
        finally:
            sock.close()

    if respuesta_dti is None:
        print(f"[Facultad {data['facultad']}] No se obtuvo respuesta del broker.")
        return

    # … (actualizar estructuras y prints; sin cambios) …

# ----------------------------------------------------------------------------- #
def manejar_programas_facultad(facultad, puerto, evento_parar):
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://*:{puerto}")
    print(f"[{facultad}] Esperando solicitudes en puerto {puerto}…")

    try:
        while not evento_parar.is_set():
            if socket.poll(timeout=1000):
                msg = socket.recv_json()
                semestre = msg.get('semestre')
                programa = msg.get('programa')
                if not semestre or not programa:
                    socket.send_json({"status": "error", "mensaje": "Datos incompletos"})
                    continue
                socket.send_json({"status": "ok",
                                  "mensaje": f"Programa '{programa['nombre']}' procesado."})
                data = {"programas":[programa], "facultad":facultad, "semestre":semestre}
                multiprocessing.Process(
                    target=enviar_a_dti,
                    args=(data, start_time, end_time, time_lock)
                ).start()
    finally:
        socket.close(); context.term()

# ----------------------------------------------------------------------------- #
def main():
    FACULTADES = { "Facultad de Ciencias Sociales": 6000, "Facultad de Tecnología": 6090 }
    procesos = []

    def cerrar_todo(sig, _):
        parar_evento.set()
        for p in procesos: p.join()
        # ─── Mostrar duración total ─────────────────────────────────────────
        dur = end_time.value - start_time.value
        if start_time.value and dur >= 0:
            print(f"\n[Cliente] Tiempo total entre 1ª y última solicitud: {dur:.2f}s")
        else:
            print("\n[Cliente] No se registraron solicitudes exitosas.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cerrar_todo)
    signal.signal(signal.SIGTERM, cerrar_todo)

    for fac, port in FACULTADES.items():
        p = multiprocessing.Process(target=manejar_programas_facultad,
                                    args=(fac, port, parar_evento))
        p.start(); procesos.append(p)

    for p in procesos: p.join()

if __name__ == "__main__":
    main()
