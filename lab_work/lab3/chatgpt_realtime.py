import websocket
import os
from os.path import join, dirname
from dotenv import load_dotenv
from enum import Enum


class EType(Enum):
    CLIENT_CONNECT = "session.created"
    UPDATE_SESSION = "session.update"
    CLIENT_MSG = "conversation.item.create"
    CLIENT_REQ_RESPONSE = "response.create"
    SERVER_TOK_STREAM = "response.output_text.delta"
    SERVER_RESPONSE_DONE = "response.done"
    ERROR = "error"


class GptWebsocket:
    def __init__(self):
        # environment load
        env_path = os.path.join(dirname(__file__), ".env")
        load_dotenv(env_path)
        OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

        # websocket setup
        MODEL = "gpt-realtime"
        URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"
        HEADERS = [f"Authorization: Bearer {OPENAI_API_KEY}"]

        self.websocket = websocket.WebSocketApp(
            URL,
            header=HEADERS,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

    def on_open(self, ws):
        pass

    def ws_send(self, message):
        pass

    def on_message(self, ws, message):
        event = json.dumps(message)
        event_type = event.get("type")

        match event_type:
            case EType.CLIENT_CONNECT:
                # send update message
                pass
            case EType.CLIENT_MSG:
                # send message then send request response
                pass
            case EType.SERVER_TOK_STREAM:
                # stream to print
                pass
            case EType.ERROR:
                # deal with error
                pass

    def on_error(self, ws):
        pass

    def on_close(self, ws):
        pass


if __name__ == "__main__":
    gpt_websocket = GptWebsocket()
