
import json
import threading
import uuid
from datetime import timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv
from livekit import api

# Project folders
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = Path(__file__).resolve().parent / "web"

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")


def create_connection_info():
    """Create a LiveKit room and a token for the desktop user."""

    import os

    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not livekit_url or not api_key or not api_secret:
        raise ValueError(
            "Missing LiveKit credentials. Check your .env file."
        )

    # Generate a unique room for this conversation
    room_name = f"aika-room-{uuid.uuid4().hex[:12]}"

    # Generate a temporary access token
    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity("desktop-user")
        .with_name("You")
        .with_ttl(timedelta(hours=1))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name="aika-assistant"
                    )
                ]
            )
        )
        .to_jwt()
    )

    return {
        "url": livekit_url,
        "token": token,
        "room": room_name,
    }


class ChatRequestHandler(SimpleHTTPRequestHandler):

    def do_GET(self):

        # Return a new LiveKit token when the chat requests one
        if self.path.split("?")[0] == "/token":

            try:
                connection_info = create_connection_info()

                response = json.dumps(connection_info).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()

                self.wfile.write(response)

            except Exception as error:

                response = json.dumps({
                    "error": str(error)
                }).encode("utf-8")

                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()

                self.wfile.write(response)

            return

        # Otherwise, serve the HTML and JavaScript files
        super().do_GET()

    def log_message(self, format, *args):
        # Keep local server requests out of the terminal output
        pass


def start_chat_server():

    # Only allow connections from this computer
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: ChatRequestHandler(
            *args,
            directory=str(WEB_DIR),
            **kwargs
        )
    )

    # Run the server in the background
    server_thread = threading.Thread(
        target=server.serve_forever,
        daemon=True
    )

    server_thread.start()

    chat_url = f"http://127.0.0.1:{server.server_port}/chat.html"

    return server, chat_url
