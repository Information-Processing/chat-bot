import numpy as np
import speech_recognition as sr
import sounddevice as sd
import soundfile as sf
from openai import OpenAI
import os
from os.path import join, dirname
from os import system
from dotenv import load_dotenv
from gtts import gTTS
import tempfile
# from gpt_websocket import GptWebsocket
import sys
from types import ModuleType
import onnxruntime
import openwakeword
from scipy import signal
from scipy.io import wavfile
from numba import jit
import wave
import logging
import threading
import queue
from enum import Enum
import time


"""
Note sound device has been imported ad record function has been created as these are not native functions in python but are on the FPGA itself
this sound device is just a way of simulating the fpgas audio
"""

@jit(nopython=True)
def delta_sigma_numba(upsampled):
    """Fast delta-sigma modulation with Numba."""
    pdm = np.zeros(len(upsampled), dtype=np.uint8)
    error = 0.0
    for i in range(len(upsampled)):
        if upsampled[i] > error:
            pdm[i] = 1
            error = error + 1.0 - upsampled[i]
        else:
            error = error - upsampled[i]
    return pdm

class OpenAiCli:
    def __init__(self):
        env_path = os.path.join(dirname("__file__"), ".env")
        load_dotenv(env_path)
        OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
        self.gpt = OpenAI(api_key=OPENAI_API_KEY)

    def make_request(self, message):
        response = self.gpt.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": message}],
            max_tokens=700,
            temperature=0.7
        )
        
        response_msg = response.choices[0].message.content

        print(f"LLM responded {response_msg}")
        return response_msg


class Audio:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.buffer = None
        self.sample_len = 0

    def load(self, path):
            self.path = path

    def play(self):
        data, fs = sf.read(self.path)
        sd.play(data, fs)
        sd.wait()

    def record(self, seconds):
        frames = int(seconds * self.sample_rate)
        
        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32") as stream:
            recording, _ = stream.read(frames)
        
        self.buffer = recording.flatten()
        self.sample_len = len(self.buffer)
    
    def save_pdm(self, pdm_bits, filepath, pdm_rate=3072000):
        """Save PDM as WAV file (PYNQ .pdm format)."""
        pad = (16 - len(pdm_bits) % 16) % 16
        if pad:
            pdm_bits = np.concatenate([pdm_bits, np.zeros(pad, dtype=np.uint8)])
    
        reshaped = pdm_bits.reshape(-1, 16)
        packed = np.zeros(len(reshaped), dtype=np.uint16)
        for i in range(16):
            packed |= reshaped[:, i].astype(np.uint16) << i
    
        with wave.open(filepath, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(pdm_rate // 16)
            wav.writeframes(packed.tobytes())
    
        logging.info(f"Saved: {filepath}")




    def pcm_to_pdm(self, pcm_samples, pcm_rate, pdm_rate=3072000):
        """Convert PCM audio to PDM format for PYNQ playback."""
        pcm = pcm_samples.astype(np.float64)
        if pcm_samples.dtype == np.int16:
            pcm = pcm / 32768.0
        pcm = (pcm - pcm.min()) / (pcm.max() - pcm.min() + 1e-10)

        ratio = pdm_rate // pcm_rate
        upsampled = signal.resample_poly(pcm, ratio, 1)

        pdm = delta_sigma_numba(upsampled)

        return pdm


    def normalized_pcm(self):
        # crudely downsample to 16kHz
        fs = 16000

        # AA and then sample to 16kHZ
        audio_data = signal.resample_poly(self.buffer.flatten(), fs, self.sample_rate)
        audio_data = audio_data.astype(np.float32)
        # Remove DC offset
        audio_data -= np.mean(audio_data)

        # Compute RMS volume for later
        volume = np.sqrt(np.var(audio_data))

        # Normalize volume
        audio_data /= max(1e-7, np.max(np.abs(audio_data)))  # don't divide-by-zero
        audio_data *= 0.99 * np.iinfo(np.int16).max

        # Convert to int16
        return volume, audio_data.astype(np.int16)

class GttsCli:
    
    def __init__(self, audio):
        self.audio = audio

    def say(self, text):
        tts = gTTS(text)

        # set up temporary files for conversion
        mp3 = tempfile.NamedTemporaryFile(suffix=".mp3")
        wav = tempfile.NamedTemporaryFile(suffix=".wav")
        pdm = tempfile.NamedTemporaryFile(suffix=".pdm")

        tts.write_to_fp(mp3)
        
        # convert MP3 to PCM
        system(f"ffmpeg -loglevel error -y -i {mp3.name} -c:a pcm_s16le -ac 1 {wav.name}")

        os.system(f"afplay {wav.name}") 
        """
        # PDM IS ONLY ON PYNQ BOARD
        # convert PCM to PDM
        rate, pcm = wavfile.read(wav.name)
        pdm_data = self.audio.pcm_to_pdm(pcm, rate)
        self.audio.save_pdm(pdm_data, pdm.name)

        # playback
        self.audio.load(pdm.name)
        self.audio.play()
        """

class OpenWakeWord:
    def __init__(self):

        oww_model_name = "hey_jarvis_v0.1"
        openwakeword.utils.download_models([oww_model_name])
        self.oww_model = openwakeword.model.Model(
            wakeword_models=[oww_model_name],
            inference_framework="tflite",
        )

        self.audio_chunk_size = 1  # size of chunks used as input to openwakeword (multiples of 80ms)
        self.detection_thresh = 0.8  # 0-1

    def oww_predict(self, chunk):
        self.oww_model.predict(chunk)
        return list(self.oww_model.prediction_buffer.values())[0][-1]

    def predict_in_recording(self, recording):
        self.oww_model.reset()
        
        for chunk in np.split(recording, np.arange(self.audio_chunk_size * 1280, len(recording), self.audio_chunk_size * 1280)):
            if self.oww_predict(chunk) > self.detection_thresh:
                print("Wakeword detected!")
                return True

        return False


class State(str, Enum):
    WAITING = "waiting"
    LISTENING = "listening"


class Engine:
    def __init__(self, audio, openai_cli, gtts_cli, open_wake_word):
        self.audio = audio
        self.openai_cli = openai_cli
        self.gtts_cli = gtts_cli
        self.open_wake_word = open_wake_word

        self.audio_queue = queue.Queue(maxsize=200)
        self.speaking = False
        self.speaking_lock = threading.Lock()
        self.state = State.WAITING

    
    def run_record_thread(self):
        t = threading.Thread(target=self.record_thread, daemon=True)
        t.start()
        print("Recording thread started...")

    def record_thread(self):
        print("Record thread running...")
        while 1:
            # if bot is speaking pause recording
            try:
                with self.speaking_lock:
                    if self.speaking:
                        time.sleep(0.02)
                        continue 
            
                self.audio.record(0.08)
                volume, recording = self.audio.normalized_pcm()
                print(f"Recorded chunk, volume={volume:.4f}")

                # drop frames if ahead:
                try:
                    self.audio_queue.put_nowait((volume, recording))
                except queue.Full:
                    pass
            except Exception as e:
                import traceback
                print("[ERROR]")
                traceback.print_exc()
                time.sleep(1)

    def play_on_wake(self):
        command_frames = []
        quiet_frames = 0
        NOISE_THRESH = 0.01
        LISTEN_QUIET_SECONDS = 1.2
        CHUNK_SECONDS = 0.08

        recognizer = sr.Recognizer()
        print("Listening for wakeword...")
        while 1:
            volume, frame = self.audio_queue.get()
            if volume < NOISE_THRESH:
                quiet_frames += 1
            else:
                quiet_frames = 0

            if self.state == State.WAITING:
                if self.open_wake_word.oww_predict(frame) > self.open_wake_word.detection_thresh:
                    print("Wakeword detected")
                    self.state = State.LISTENING
                    command_frames = []
                    quiet_frames = 0

            elif self.state ==  State.LISTENING:
                command_frames.append(frame)
                if quiet_frames > int(LISTEN_QUIET_SECONDS / CHUNK_SECONDS):
                    command = np.concatenate(command_frames)

                    try:
                        text = recognizer.recognize_google(sr.AudioData(command.tobytes(), 16000, 2))
                    except sr.UnknownValueError:
                        print("cant understand you")
                        self.state = State.WAITING
                        continue

                print(f"You said: {text}")

                response = self.openai_cli.make_request(text)
                with self.speaking_lock:
                    self.speaking = True
                    self.gtts_cli.say(response)
                with self.speaking_lock:
                    self.speaking = False

                self.state = State.WAITING


                while not self.audio_queue.empty():
                    try: 
                        self.audio_queue.get_nowait()
                    except queue.Empty: 
                        break



if __name__ == "__main__":

    audio = Audio()
    openai_cli = OpenAiCli()
    gtts_cli = GttsCli(audio)
    open_wake_word = OpenWakeWord()
        
    engine = Engine(audio, openai_cli, gtts_cli, open_wake_word)

    engine.run_record_thread()
    engine.play_on_wake()


    print("Terminating program...")


