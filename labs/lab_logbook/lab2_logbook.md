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

Given the speed of the signal transfer, the AXI peripheral, i.e. `d_axi_pdm_v1_2_S_AXI`, provides a FIFO buffer
which holds onto output bits from the hardware when the CPU is unable to process these bits fast enough and is
busy.

### Task 2B: Creating an Audio Frontend (PDM-to-PCM Converter)

In this task, we will be using a simolified version of tbe BaseOverlay using the `lab2-skeleton.tcl` skeleton
file. In this overlay, we are requird to update blocks `pdm_microphone_0` and `audio_direct_0` in the final
schematic shown below:

<p align="center"> <img src="../../images/lab2-final-design.jpg" /> </p>

In this section we use a CIC compiler. A CIC compiler acts a digital filter to handle signals with multiple bits
which also allows for changing the sampling frequency of data. In this case, we use the filter for decimation
(takes a high speed PDM stream and converts it to a lower-speed PCM stream). This is used for efficiency, given that
the CIC filters only use adders and delay lines (and other filters often require multipliers), and anti-aliasing, 
ensuring a smoothed out signal preventing noise produced when lowering sample rate.

We connect the CIC compiler to the `pdm_mic.v` file given to us (ensuring decimation of the 1-bit PDM input). The
following adjustments are made to the CIC compiler in Vivado as such:
- **No. stages = 5-** This is larger than usual (often 3-4) allowing for sharper audio
- **Initial Sample Frequency = 2.4Mhz-** Microphone frequency of the PYNQ-Z1 board (from PDM signal frequency)
- **Clock Frequency = 50MHz-** Clock input of the PYNQ-Z1 board

### Task 2C:


