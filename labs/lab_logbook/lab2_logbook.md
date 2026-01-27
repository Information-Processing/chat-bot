# Lab 2 Logbook: Audio Processing

---
  - Note that I haven't done parts 2.2 (Software) and 2.3 tasks 2E, 2F (I have left these for you guys to do / further test later)
  - This is a rough draft, feel free to make additions / changes

---

## 2.3 Audio Processing (Hardware)

In this section, we looked at the audio components on the PYNQ-Z1 base overlay, understanding how 
drivers interact wtth hardware components and using this to create hardware blocks for PDM-to-PCM conversion.

### Audio module in the base overlay

In this module, a PDM-to-PWM bypass is used taking a 1-bit signal from the microphone in the PYNQ 
board, and sends this signal to the PWM output for the speakers. This process is extremely fast given that 
both signals are only 1-bit wide, however, these signals are difficult to manipluate mathematically in terms
of processing and cleanning the audio. PCM audio is multi-bit (in the case of these labs 32-bits) which allow
for multiple adaptations to the audio signal including:
- Filtering out white noise
- Adjusting the volume of the signal
