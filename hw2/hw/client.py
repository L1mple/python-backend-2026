from threading import Thread

from websocket import create_connection

chat_name = input("Room: ")

ws = create_connection(
    f"ws://localhost:8000/chat/{chat_name}"
)

def receive_messages():
    while True:
        message = ws.recv()
        print(f"\n{message}")

Thread(target=receive_messages, daemon=True).start()

while True:
    message = input()
    ws.send(message)