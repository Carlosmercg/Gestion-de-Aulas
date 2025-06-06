import zmq, time

BROKER_ADDR = "tcp://10.43.96.74:5555"
INTERVAL    = 3  # s

ctx  = zmq.Context()
sock = ctx.socket(zmq.REQ)
sock.connect(BROKER_ADDR)
poll = zmq.Poller(); poll.register(sock, zmq.POLLIN)

print("[HC] Pings cada 3 s … Ctrl+C para salir")
while True:
    try:
        sock.send_json({"tipo": "ping"})
        if poll.poll(INTERVAL * 1000):
            print("[HC] OK:", sock.recv_json())
        else:
            print("[HC] ❌ sin respuesta en", INTERVAL, "s")
        time.sleep(INTERVAL)
    except KeyboardInterrupt:
        break
