import zmq
import time

def health_check():
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://10.43.103.197:5556") 

    while True:
        try:
            socket.send_json({"ping": True})
            mensaje = socket.recv_json()
            if mensaje.get("pong") == True:
                print("[HealthChecker] Servidor DTI está vivo")
            else:
                print("[HealthChecker] Respuesta inesperada:", mensaje)
        except Exception as e:
            print("[HealthChecker] Error conectando al servidor:", e)

        time.sleep(5)  # cada 5 segundos

if __name__ == "__main__":
    health_check()