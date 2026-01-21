import websocket
import os
from os.path import join, dirname
from dotenv import load_dotenv
from enum import Enum
import json
import base64
import threading
import sounddevice as sd


class Logger:
    def __init__(self):
        self.log_en = False

    def LOG(self, msg):
        if self.log_en:
            print(f"[DEBUG] {msg}")


class EType(str, Enum):
    CLIENT_CONNECT = "session.created"
    UPDATE_SESSION = "session.update"

    CLIENT_MSG = "conversation.item.create"
    CLIENT_REQ_RESPONSE = "response.create"

    SERVER_TOK_STREAM = "response.output_text.delta"
    SERVER_AUDIO_STREAM = "input_audio_buffer.append"
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
        json_msg = json.dumps(message)
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
                                     "output_modalities": ["text", "audio"],
                                     "audio": {
                                         "input": {
                                             "format": {"type": "audio/pcm", "rate": 24000},
                                             "turn_detection": {"type": "semantic_vad"}
                                         }
                                         "output": {
                                             "format": {"type": "audio/pcm"},
                                             "voice": "marin"
                                         }
                                     }
                                     "instructions": "Be consise."
                                 }
                             }
                             )

                self.LOG("\nSession updated: type, output and instructions set\n")
            case EType.CLIENT_MSG:
                # send message then send request response
                pass

            case EType.SERVER_TOK_STREAM:
                # stream "delta" (message from gpt) to std::cout
                print(event.get("delta", ""), end="", flush=True)

            case EType.SERVER_RESPONSE_DONE:
                print("\n ~Mr Gippity \n\n")

            case EType.ERROR:
                # deal with error
                print("Error")

        self.LOG(f"event on websocket: {event}")
        self.LOG(f"event type: {event_type}")

    def on_error(self, ws, error):
        print(f"Error: {error}")

    def on_close(self, ws, code, reason):
        print("Websocket closed:")
        print(f"Code: {code}")
        print(f"Reason: {reason}")

    def send_message(self):
        while (1):
            message = input()
            self.ws_send(self.ws,
                         {
                             "type": EType.CLIENT_MSG,
                             "item": {
                                 "type": "message",
                                 "role": "user",
                                 "content": [{"type": "input_text", "text": message}]
                             }
                         }
                         )
            self.ws_send(self.ws, {"type":  EType.CLIENT_REQ_RESPONSE})

    def mic_callback(self, indata, frames, time, status):
        if status:
            print(status)

        chunk_bytes = indata.tobytes()
        b64 = base64.b64encode(chunk_bytes).decode("ascii")

        self.ws_send(self.ws, {
            "type": EType.SERVER_AUDIO_STREAM,
            "audio": b64
        })

    def send_audio(self):
        stream = sd.InputStream(
            samplerate=24000,
            channels=1,
            dtype="int16",
            blocksize=int(24000*20/1000),
            callback=self.mic_callback
        )
        stream.start()
        input("Recording... press any button to stop.")
        while (1):
            mic.


if __name__ == "__main__":
    gpt_websocket = GptWebsocket()
    t = threading.Thread(target=gpt_websocket.ws.run_forever, daemon=True)
    t.start()
    gpt_websocket.send_message()
