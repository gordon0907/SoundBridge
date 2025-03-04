# SoundBridge

A lightweight application that enables your macOS speaker and microphone to function as audio input and output devices
on Windows. It achieves low-latency UDP transmission using `pyaudio` and `VB-Audio`.

## Why SoundBridge?

As an AirPods Pro enthusiast who frequently switches between macOS and Windows, I found that the Bluetooth experience on
Windows is far from seamless. Since AirPods are optimized for Apple’s ecosystem, switching between devices is often
frustrating. This led me to the idea of porting both input and output audio from Windows to macOS, effectively using the
Mac as a speaker and microphone for the Windows machine.

Despite searching extensively, I couldn't find a simple open-source solution. So, I decided to build one myself—and here
it is!

## Terminology

- **Server**: The device that functions as the physical speaker and microphone (macOS).
- **Client**: The device that uses the server as a speaker and microphone (Windows).

## Installation

### Prerequisites

- **Client** (Windows) requires:
    - `VB-Cable` for audio routing.
    - `pyaudiowpatch` (for WASAPI loopback support).
- **Server** (macOS) requires:
    - `pyaudio`.

### Setup

#### Server (macOS)

1. Install Python dependencies:
   ```sh
   pip install pyaudio
   ```
2. Run the server script:
   ```sh
   python server.py
   ```

#### Client (Windows)

1. Install `VB-Cable` and set `VB-Cable Output` as the default **microphone**.
    - **Do not** set `VB-Cable Input` as the default speaker.
    - Instead, set another input device that supports WASAPI loopback.
2. Install Python dependencies:
   ```sh
   pip install pyaudiowpatch
   ```
3. Run the client script:
   ```sh
   python client.py
   ```
4. Configure server IP and port in `server.py` and `client.py` if necessary.

## Controls

- **Toggle microphone usage on the client**: Type `m` and press `Enter` in the console (useful for saving AirPods
  battery).
- **Terminate client**: Press `Enter` in the console.
- **Stop the server**: Press `Enter` in the console.

## Notes

- The application assumes that the client's input/output audio devices remain unchanged during streaming. If changed,
  restart the client.
- The server’s default input/output devices can be changed at any time (e.g., putting on or removing AirPods).
- If audio glitches occur, restart the client. If issues persist, restart the server as well.

## Known Issue

- **Audio Delay After Toggling AirPods Microphone**: When using AirPods, toggling the microphone in the client may cause
  a delay in the server's audio output. This issue likely occurs due to a shift in the AirPods' output sample rate when
  the microphone is activated, dropping from 48 kHz to 24 kHz. The current workaround is to restart the client to
  resynchronize the audio stream.

## TODO

- Implement a GUI for the client.

---

Feel free to contribute or suggest improvements!
