from threading import Event, Thread
from urllib.parse import quote
from websocket import WebSocket, WebSocketException, create_connection


def receive_messages(ws: WebSocket, stopped: Event) -> None:
    try:
        while not stopped.is_set():
            message = ws.recv()
            if message == "" and not ws.connected:
                break
            print(f"\n{message}")
    except (WebSocketException, OSError) as e:
        if not stopped.is_set():
            print(f"Connection Interrupted: {e}")
    finally:
        if not stopped.is_set():
            print("Connection is closed. Press Enter to exit.")
        stopped.set()


def send_message(ws: WebSocket, stopped: Event) -> None:
    try:
        while not stopped.is_set():
            message = input()
            if stopped.is_set():
                break
            if message.lower() == "/exit":
                stopped.set()
                break
            elif message.strip() == "":
                continue
            ws.send(message)
    except (WebSocketException, OSError) as e:
        if not stopped.is_set():
            print(f"Connection Interrupted: {e}")
    finally:
        stopped.set()


def main() -> None:
    ws = None
    receiver = None
    stopped = Event()

    try:
        room = input("Enter Chat Name: ").strip()
        if not room:
            print("Chat Name cannot be empty.")
            return
        if "/" in room:
            print("Chat Name cannot contain a slash.")
            return

        url = f"ws://127.0.0.1:8000/chat/{quote(room, safe='')}"
        ws = create_connection(url, timeout=5, enable_multithread=True)

        ws.settimeout(None)
        print(f"Chat {room}. To quit type /exit or press Ctrl+C.")

        receiver = Thread(
            target=receive_messages, args=(ws, stopped), daemon=True
        )
        receiver.start()
        send_message(ws, stopped)
    except (KeyboardInterrupt, EOFError) as e:
        print("Exiting...")
    except (WebSocketException, OSError) as e:
        print(f"Connection Error: {e}")
    finally:
        stopped.set()
        if ws is not None:
            ws.shutdown()
        if receiver is not None:
            receiver.join(timeout=2)


if __name__ == "__main__":
    main()
