import websocket
import os
from os.path import join, dirname
from dotenv import load_dotenv
from enum import Enum
import json


class Logger:
    def __init__(self):
        self.log_en = True

    def LOG(self, msg):
        if self.log_en:
            print(f"[DEBUG] {msg}")


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
        # logger for debugging
        logger = Logger()
        self.LOG = logger.LOG

        # environment load
        env_path = os.path.join(dirname(__file__), ".env")
        load_dotenv(env_path)
        OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

        # websocket setup
        MODEL = "gpt-realtime"
        URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"
        HEADERS = [f"Authorization: Bearer {OPENAI_API_KEY}"]

        self.ws = websocket.WebSocketApp(
            URL,
            header=HEADERS,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

    def on_open(self, ws):
        print("Connected to ChatGPT Websocket")

    def ws_send(self, ws, message):
        json_msg = json.dumps(messaga)
        ws.send(json_msg)

    def on_message(self, ws, message):
        event = json.loads(message)
        event_type = event.get("type")

        match event_type:
            case EType.CLIENT_CONNECT:
                # send update message
                self.ws_send(ws,
                             {
                                 "type": EType.UPDATE_SESSION,
                                 "session": {
                                     "type": "realtime",
                                     "output_modalities": ["text"],
                                     "instructions": "Be consise."
                                 }
                             }
                             )
                self.LOG("\nSession updated: type, output and instructions set\n")
            case EType.CLIENT_MSG:
                # send message then send request response
                pass
            case EType.SERVER_TOK_STREAM:
                # stream to print
                pass
            case EType.ERROR:
                # deal with error
                print("Error")
                pass

        self.LOG(f"event on websocket: {event}")

    def on_error(self, ws, error):
        print(f"Error: {error}")

    def on_close(self, ws, code, reason):
        print("Websocket closed:")
        print(f"Code: {code}")
        print(f"Reason: {reason}")


if __name__ == "__main__":
    gpt_websocket = GptWebsocket()
    gpt_websocket.ws.run_forever()
