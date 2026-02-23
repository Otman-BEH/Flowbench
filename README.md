# Flowbench
Ground support software for feed system cold flow testing. A real-time pressure monitoring and valve sequencing application built for University of Bath's Rocket Team.

## Overview
FlowBench is a PyQt6-based desktop GUI designed to interface with an ESP32-controlled oxidiser test bench. It provides live pressure telemetry from up to three transducers, manual valve control and a sequence builder that compiles and uploads timed valve actuation sequences to the ESP32 over Wi-Fi. The ESP32 gets all safety-critical timing before executing. FlowBench handles monitoring, commanding, and data logging.

Built by me for Bath Rocket Team to do a cold flow test of our oxidiser feed system. Currently using random values as placeholder, eventually will be using pressures acquired over Wi-Fi from microcontroller.

## Running the program

Requires Python 3.10+. Install dependencies:
```
pip install PyQt6 pyqtgraph numpy matplotlib
```

Place all files (`main.py`, `gui.py`, `control.py`, `comms.py`, `logger.py`) in the same folder, then run main.py

## Features

- **Real-time pressure monitoring**: Three pressure channels (Pressurant, Oxidiser Tank, Injector) displayed as live scrolling graphs and a combined graph with all pressure channels at once.
- **Manual valve control**: Toggle switches for two solenoid valves and one servo valve with live OPEN/CLOSED status indicators
- **Sequence builder**: Build multi-step valve actuation sequences with configurable durations or indefinite hold; steps can be added and removed
- **ESP32 sequence upload**: Compiles the sequence to a JSON and sends it to the ESP32 over Wi-Fi; RUN can only enabled after a confirmed send, making the microcontroller do valve timing
- **Panic button**: Immediately closes all valves
- **CSV data logging**: Pressure and valve state logged to separate CSV files; time column starts from the moment RECORD is pressed
- **Dark/light theme toggle**: Self-Explanatory
- **Configurable sample rate and realtime graph timeframe**: Done via changing constants (UPDATE_RATE_MS, MAX_POINTS) at top of the file.

## Configuration

There is some configuration and customisability. At top of `main.py`:

```python
MAX_POINTS = 200        # Number of data points shown in the rolling realtime graph window
UPDATE_RATE_MS = 50     # Graph and logging update interval in ms (50 ms = 20 Hz)

#(MAX_POINTS/(1000/UPDATE_RATE_MS)) is timeframe for realtime graph. With current values, it is 10 seconds.

CHANNELS = [...]        # Pressure channel names and colours
VALVES = [...]          # Valve names shown in the UI and logged to CSV file
VALVE_COLORS = [...]    # Colours for each different valve
```

## Communication with ESP32

FlowBench communicates with the ESP32 over Wi-Fi using HTTP. Right now there is only `# Wi-Fi send command to ESP32 goes here` and a print statement to show command was sent

## JSON Sequence Payload Format

Sequence is compiled into a JSON file and sent in full before being ran to ensure more accurate valve timing through having it run on the microcontroller than having a delay and inaccurate timing from sending it through Wi-Fi and the Python app doing graph updates, logging, and UI simultaneously.


```json
{
  "sequence": [
    {
      "actions": [{"valve": "Solenoid Valve 1", "action": "OPEN"}],
      "duration_ms": 3000,
      "hold": false
    },
    {
      "actions": [{"valve": "Solenoid Valve 1", "action": "CLOSE"}],
      "duration_ms": null,
      "hold": true
    }
  ],
  "step_count": 2
}
```

## Data Logging

When recording is active, two CSV files are written to the same directory as `main.py`, using timestamp of when it was created to not overwrite files when doing multiple tests:

| time_elapsed | P1_Pressurant_bar | P2_OxidiserTank_bar | P3_Injector_bar |
|--------|-------------------|---------------------|-----------------|
| 0.0000 | 46.0312 | 61.4921 | 23.1845 |
| 0.0500 | 45.0287 | 60.5103 | 23.2011 |

| time_elapsed | Solenoid_Valve_1 | Solenoid_Valve_2 | Servo_Valve_1 |
|--------|------------------|------------------|---------------|
| 1.3240 | OPEN | CLOSED | CLOSED |
| 4.1150 | OPEN | OPEN | CLOSED |

`time_elapsed` is elapsed seconds from the moment RECORD is pressed. The valve log only writes a row when a valve state changes, not on every update tick.

## Known Issues / Further Work

### Inefficient logging implementation
During recording, CSV files are currently opened and closed on every sample write. At 20 Hz this works without obvious issues, but it is inefficient and could cause unnecessary performance issues at higher sample rates.

This will be improved by keeping file handles open for the duration of recording and flushing periodically instead of reopening the file every update cycle.

### Sequence completion detection
The GUI does not know when the microcontroller has finished executing a sequence. `_seq_done()` exists in the code but is never called because the PC has no feedback from the ESP32. This will be fixed when the ESP32 code is written

### Time steps are not constant time apart
Time steps have approximately a variance of up to 40ms. This is because the sampling and timing is still happening in Python with the sample random data and should be fixed when moved to microcontroller with hardware timers, a similar approach to the valve sequence compiling logic so that the data is accurately and precisely measured at the right time nad sent a bit after as that is not as important.

## Fixed issues
### Valve timing Logic
When running valve sequences on the PC via QTimer there was up to 20ms jitter per step due to the non-real-time nature of desktop OS scheduling. This was found through the csv file by looking at the timestamps. Solved by compiling entire sequence into a JSON and sending to the microcontroller which will be much more precise with timing.
