import numpy as np
import speech_recognition as sr
import sounddevice as sd
import os
from os.path import dirname, join
from dotenv import load_dotenv
from openai import OpenAI

class Audio:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.buffer = None
        self.sample_len = 0

    def record(self, seconds):
        data = sd.rec(
            frames=int(seconds * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32"
        )

        sd.wait()
        self.buffer = data.flatten()
        self.sample_len = len(self.buffer)

    def normalized_pcm(self):
        # crudely downsample to 16kHz
        fs = 16000
        samples = int(np.round(self.sample_len * fs / self.sample_rate))
        fractional_sample_indices = np.arange(samples) * (self.sample_rate / fs)
        sample_indices = np.clip(np.round(fractional_sample_indices).astype(int), 0, self.sample_len - 1)
        audio_data = self.buffer[sample_indices].astype(np.float32)

        # Remove DC offset
        audio_data -= np.mean(audio_data)

        # Compute RMS volume for later
        volume = np.sqrt(np.var(audio_data))

        # Normalize volume
        audio_data /= max(1e-7, np.max(np.abs(audio_data)))  # don't divide-by-zero
        audio_data *= 0.99 * np.iinfo(np.int16).max

        # Convert to int16
        return volume, audio_data.astype(np.int16)

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

if __name__ == "__main__":
    openai_cli = OpenAiCli()
    audio = Audio()
    audio.record(5)
    _, recording = audio.normalized_pcm()

    recognizer = sr.Recognizer()
    text = recognizer.recognize_google(sr.AudioData(recording, 16000, 2))

    print(f"You said: {text}")

    openai_response_msg = openai_cli.make_request(text)

    print(openai_response_msg)

