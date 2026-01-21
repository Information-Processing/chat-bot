import websocket
import os
from os.path import join, dirname
from dotenv import load_dotenv
from enum import Enum


class EType(Enum):
    CLIENT_CONNECT = "session.created"
    UPDATE_SESSION = "session.update"
    CLIENT_MSG = "conversation.item.create"
    CLIENT_SEND = ""
    SERVER_TOK_STREAM = "response.output_text.delta"
    SERVER_RESPONSE_DONE = "response.done"
    ERROR = "error"


class GptWebsocket:

    def __init__(self):
        # global environment load
        env_path = os.path.join(dirname(__file__), ".env")
        load_dotenv(env_path)
        OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

        MODEL = "gpt-realtime"
        URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"
