import asyncio
import sys

from websockets import connect
from websockets.exceptions import ConnectionClosed

PROMPT="> "

def print_prompt() -> None:
    sys.stdout.write(PROMPT)
    sys.stdout.flush()

async def recv_loop(ws) -> None:
    try:
        while True:
            message = await ws.recv()
            sys.stdout.write("\r\033[K")
            sys.stdout.write(message + "\n")
            print_prompt()
    except ConnectionClosed:
        print("Connection closed", file=sys.stderr)

async def send_loop(ws) -> None:
    loop = asyncio.get_running_loop()
    while True:
        text = await loop.run_in_executor(None, input)
        if text.strip():
            await ws.send(text)

        print_prompt()

async def main() -> None:
    chat_name = input("Enter the chat's name: ").strip()
    if not chat_name:
        print("Room name is invalid", file=sys.stderr)
        sys.exit(1)

    uri = f"ws://127.0.0.1:8000/chat/{chat_name}"

    async with connect(uri) as ws:
        print_prompt()
        await asyncio.gather(recv_loop(ws), send_loop(ws))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutdown requested")
        sys.exit(0)