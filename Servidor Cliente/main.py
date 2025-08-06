import threading
import time
import os
from pathlib import Path


# Ejecutar el servidor Flask
def run_server():
    server_path = Path(__file__).parent / 'servidor.py'
    os.system(f'python "{server_path}"')

# Ejecutar el cliente PyQt6
def run_client():
    server_path = Path(__file__).parent / 'cliente.py'
    os.system(f'python "{server_path}"')

if __name__ == "__main__":
    # Crear hilos para ejecutar el servidor y el cliente
    server_thread = threading.Thread(target=run_server)
    client_thread = threading.Thread(target=run_client)

    # Iniciar los hilos
    server_thread.start()
    time.sleep(2)  # Dar tiempo para que el servidor arranque antes de que el cliente se conecte
    client_thread.start()

    # Esperar que ambos hilos terminen (si es necesario)
    server_thread.join()
    client_thread.join()