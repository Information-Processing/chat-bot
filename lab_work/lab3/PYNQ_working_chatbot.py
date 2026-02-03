# ============================================================================
# BLOCK 1 : IMPORTS
# ============================================================================

import numpy as np
import speech_recognition as sr
from openai import OpenAI
import os
from os import system
from gtts import gTTS
import tempfile
import sys
from types import ModuleType

sys.modules["onnxruntime"] = ModuleType("onnxruntime")

from openwakeword.model import Model
from scipy import signal
from scipy.io import wavfile
import wave
import logging
import threading
import queue
from enum import Enum
import time

from multiprocessing import Value, Lock

from pynq import Overlay

# ============================================================================
# BLOCK 2: LOGGING
# ============================================================================

# Configure logging - only show our messages, not library debug
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('gtts').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


# ============================================================================
# BLOCK 3: PYNQ INIT
# ============================================================================
overlay = Overlay('base.bit')
pynq_audio = overlay.audio_direct_0
audio_lock = Lock()
audio_lock_priority = Value('c', b'i')
# ============================================================================
# BLOCK 4: FUCNTIONS THAT WILL BE IMPLEMENTED IN HARDWARE STACK
# ============================================================================
def popcount_lut():
    """Create lookup table for counting bits in a byte."""
    return np.array([bin(i).count('1') for i in range(256)], dtype=np.uint8)

# Pre-compute lookup table at module load
POPCOUNT_LUT = popcount_lut()

def pdm_to_pcm(buffer, target_sr=16000):
    """
    Convert PYNQ PDM buffer to PCM audio.
    Each int32 contains 32 PDM bits - we count them to get amplitude.
    Uses fast vectorized bit counting.
    """
    # View as bytes for fast bit counting using lookup table
    buf_bytes = buffer.view(np.uint8)
    
    # Count bits using lookup table (FAST - vectorized)
    byte_counts = POPCOUNT_LUT[buf_bytes]
    
    # Sum every 4 bytes to get count per int32
    bit_counts = byte_counts.reshape(-1, 4).sum(axis=1).astype(np.float64)
    
    # Center around 0 (16 bits = silence in 32-bit word)
    audio = bit_counts - 16.0
    
    # Decimate with reshape and mean (FAST - vectorized)
    pdm_rate = 192000
    decimation = pdm_rate // target_sr  # 12
    
    # Trim to multiple of decimation
    n_full = (len(audio) // decimation) * decimation
    audio = audio[:n_full]
    
    # Fast decimation using reshape
    audio_dec = audio.reshape(-1, decimation).mean(axis=1)
    
    # Remove DC offset
    audio_dec = audio_dec - np.mean(audio_dec)
    
    # Normalize to int16 range
    peak = np.max(np.abs(audio_dec))
    if peak > 0.01:
        audio_16 = (audio_dec / peak * 30000).astype(np.int16)
    else:
        audio_16 = np.zeros(len(audio_dec), dtype=np.int16)
    
    return audio_16



def pcm_to_pdm_high_snr(pcm):
    """
    2nd-order Sigma-Delta with improved SNR through noise shaping.
    
    This is implemented in hardware but for now we can try any pcm to pdm conversion.
    Note that we need a high snr
    """
    # 1. Normalize and apply Soft-Clipping to reduce static 'shatter'
    pcm = pcm.astype(np.float32) / 32768.0
    pcm = np.tanh(pcm * 1.5) / 1.5 # Soft-limit peaks
    
    # 2. Add high-frequency dither (shoves hiss out of audible range)
    dither = (np.random.rand(len(pcm)) - 0.5) * 0.001
    pcm += dither

    # 3. Fade Out and Pad
    # Using 192k for better clock alignment
    sr = 192000
    padding = np.zeros(int(sr * 0.2), dtype=np.float32)
    pcm = np.concatenate([pcm, padding])
    
    # Align to DMA chunk
    if len(pcm) % 128 != 0:
        pcm = np.concatenate([pcm, np.zeros(128 - (len(pcm) % 128), dtype=np.float32)])

    n = len(pcm)
    pdm = np.zeros(n, dtype=np.int16)
    
    # 4. 2nd-Order Modulator
    i1, i2, feedback = 0.0, 0.0, 0.0
    for i in range(n):
        i1 += pcm[i] - feedback
        i2 += i1 - feedback
        
        # Quantizer
        val = 32767 if i2 >= 0 else -32768
        pdm[i] = val
        feedback = 1.0 if val > 0 else -1.0
    
    # 5. Zero-fill the very end to kill the high-pitch squeak
    pdm[-1024:] = np.tile([32767, -32768], 512)
            
    return pdm
# ============================================================================
# HYBRID IMPLEMENTATION
# ============================================================================

class GttsCli:
    """Text to Speech using GTTS"""

    def say(self, text):
        """
        Uses GTTS to convert text to audio which is then played through audio out on the pynq board
        """
        logger.info(f"Speaking: {text}")
        with tempfile.NamedTemporaryFile(suffix=".mp3") as mp3, \
             tempfile.NamedTemporaryFile(suffix=".wav") as wav_pcm, \
             tempfile.NamedTemporaryFile(suffix=".wav") as wav_pdm:

            try:
                #gtts outputs an mp3 file
                tts = gTTS(text)
                tts.write_to_fp(mp3)
                mp3.flush()

                # We are tuning the .mp3 file and converting it to a .wav file
                # This can be implemented within hardware. Specs as follows:
                # -ar 192000: board sample rate
                # highpass=f=150: highpass filter at 150Hz
                # volume=0.8: Fine tuned
                cmd = (
                    f"ffmpeg -loglevel error -y -i {mp3.name} "
                    f"-c:a pcm_s16le -ac 1 -ar 192000 "
                    f"-af 'highpass=f=150,volume=0.8' {wav_pcm.name}"
                )
                system(cmd)

                #read metadata from wav file
                rate, pcm = wavfile.read(wav_pcm.name)

                #convert pcm to pdm file
                pdm_data = pcm_to_pdm_high_snr(pcm)
                
                wavfile.write(wav_pdm.name, rate, pdm_data)

                #obtain lock, write
                audio_lock_priority.value = b'o'
                with audio_lock:
                    audio_lock_priority.value = b'i'
                    audio.load(wav_pdm.name)
                    audio.play()
                    time.sleep(len(pdm_data) / rate)
                    
            except Exception as e:
                logger.error(f"Error: {e}")


# ============================================================================
# PURE SOFTWARE IMPLEMENTATION
# ============================================================================
class OpenAiCli:
    """OpenAI GPT client with conversation history."""
    
    def __init__(self):
        OPENAI_API_KEY = "INSERT_OPENAI_API_KEY_HERE"
        self.gpt = OpenAI(api_key=OPENAI_API_KEY)
        self.conversation_history = []
        self.max_history = 6
        self.system_prompt = "Be concise. Reply in 1-2 sentences."

    def make_request(self, message):
        self.conversation_history.append({"role": "user", "content": message})
        
        messages = [{"role": "system", "content": self.system_prompt}]
        messages += self.conversation_history[-self.max_history:]

        response = self.gpt.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=200,
            temperature=0.7
        )
        
        reply = response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": reply})
        logger.info(f"GPT: {reply}")
        return reply


class OpenWakeWord:
    """Wake word detector using OpenWakeWord."""
    
    def __init__(self, model_path="hey_jarvis_v0.1.tflite", threshold=0.2):
        logger.info(f"Loading wake word model: {model_path}")
        self.model = Model(wakeword_models=[model_path], inference_framework="tflite")
        self.threshold = threshold
        logger.info(f"Wake word threshold: {threshold}")
    
    def detect(self, audio_16k):
        """Check if wake word is in audio. Returns True if detected."""
        self.model.reset()
        
        # Process in 80ms chunks (1280 samples at 16kHz)
        chunk_size = 1280
        max_score = 0.0
        
        # Process ALL chunks - model needs continuous input for state
        for i in range(0, len(audio_16k) - chunk_size, chunk_size):
            chunk = audio_16k[i:i+chunk_size]
            self.model.predict(chunk)
            score = list(self.model.prediction_buffer.values())[0][-1]
            max_score = max(max_score, score)
            
            if score > self.threshold:
                logger.info(f"*** WAKE WORD DETECTED! Score: {score:.3f} ***")
                return True
        
        logger.info(f"Score: {max_score:.3f}")
        return False


class State(str, Enum):
    WAITING = "waiting"
    LISTENING = "listening"


class VoiceAssistant:
    """Main voice assistant engine."""
    
    def __init__(self):
        self.openai = OpenAiCli()
        self.tts = GttsCli()
        self.wakeword = OpenWakeWord(threshold=0.2)
        self.recognizer = sr.Recognizer()
        
        self.state = State.WAITING
        self.running = False
        
        # Audio settings
        self.sample_rate = 16000
        self.record_seconds = 2  # Record 2 seconds at a time
    
    def record_audio(self, seconds):
        """Record audio and convert PDM to PCM."""
        t0 = time.time()
        pynq_audio.record(seconds)
        time.sleep(seconds + 0.2)  # Reduced wait time
        t1 = time.time()
        
        # Get buffer and convert PDM to PCM
        audio_16k = pdm_to_pcm(pynq_audio.buffer, self.sample_rate)
        t2 = time.time()
        
        logger.info(f"[Timing] Record: {t1-t0:.1f}s, Process: {t2-t1:.1f}s, Samples: {len(audio_16k)}")
        return audio_16k
    
    def get_volume(self, audio):
        """Calculate RMS volume."""
        return np.sqrt(np.mean(audio.astype(np.float64)**2))
    
    def run(self):
        """Main loop."""
        logger.info("=" * 50)
        logger.info("Voice Assistant Started")
        logger.info("Say 'Hey Jarvis' to activate")
        logger.info("=" * 50)
        
        self.running = True
        audio_buffer = []
        
        try:
            while self.running:
                # Record audio
                audio = self.record_audio(self.record_seconds)
                volume = self.get_volume(audio)
                
                if self.state == State.WAITING:
                    # Keep rolling buffer of last 3 seconds
                    audio_buffer.append(audio)
                    if len(audio_buffer) > 3:
                        audio_buffer.pop(0)
                    
                    combined = np.concatenate(audio_buffer)
                    logger.info(f"Volume: {volume:.0f}")
                    
                    if self.wakeword.detect(combined):
                        self.state = State.LISTENING
                        audio_buffer = []
                        logger.info(">>> Listening for command...")
                
                elif self.state == State.LISTENING:
                    logger.info("Recording command (3 seconds)...")
                    command_audio = self.record_audio(3)
                    
                    try:
                        audio_data = sr.AudioData(command_audio.tobytes(), self.sample_rate, 2)
                        text = self.recognizer.recognize_google(audio_data)
                        logger.info(f"You said: {text}")
                        
                        response = self.openai.make_request(text)
                        self.tts.say(response)
                        
                    except sr.UnknownValueError:
                        logger.warning("Could not understand audio")
                    except Exception as e:
                        logger.error(f"Error: {e}")
                    
                    self.state = State.WAITING
                    audio_buffer = []
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        
        logger.info("Voice Assistant Stopped")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info("Initializing Voice Assistant...")
    
    assistant = VoiceAssistant()
    assistant.run()
