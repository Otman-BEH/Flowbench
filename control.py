import numpy as np
from PyQt6.QtCore import QTimer

PROFILE_STEPS = 100

class ValveController:
    def __init__(self, valve_names, on_valve_state_changed=None, on_seq_status_changed=None, logger=None):
        self.valve_names = valve_names
        self.valve_states = [False] * len(valve_names)
        self.logger = logger
        self.on_valve_state_changed = on_valve_state_changed
        self.on_seq_status_changed = on_seq_status_changed
        self.seq_steps = []
        self.seq_running = False
        self.sent_sequence = None
        self.sequence_sent = False
        self.seq_index = 0
        self.seq_timer = QTimer()
        self.seq_timer.setSingleShot(True)
        self.seq_timer.timeout.connect(self._seq_next)

    # Manual Valve activation toggle logic
    def toggle_valve(self, idx, state):
        self.valve_states[idx] = state
        if self.on_valve_state_changed:
            self.on_valve_state_changed(idx, state)
        if self.logger:
            self.logger.log_valve_state(self.valve_states)

    def set_valve(self, valve_name, action):
        idx = self.valve_names.index(valve_name)
        state = (action == "OPEN")
        self.valve_states[idx] = state
        if self.on_valve_state_changed:
            self.on_valve_state_changed(idx, state)
        if self.logger:
            self.logger.log_valve_state(self.valve_states)

    def panic(self):
        self._seq_stop()
        for name in self.valve_names:
            self.set_valve(name, "CLOSE")
        if self.on_seq_status_changed:
            self.on_seq_status_changed("PANIC — all valves closed", "#ff3333")

    # Servo motion profile pre-computation
    def compute_profile_points(self, profile, steps=PROFILE_STEPS):
        """Pre-computes normalised position points (0.0 -> 1.0) for the given motion profile.
        The ESP32 scales these to actual servo angle and steps through them at interval_ms ticks."""
        t = np.linspace(0.0, 1.0, steps)
        if profile == "Linear":
            # Mathematical function goes here
            points = t
        elif profile == "Stepped":
            # Mathematical function goes here
            points = t
        elif profile == "Instant":
            # Mathematical function goes here
            points = t
        elif profile == "Exponential":
            # Mathematical function goes here
            points = t
        elif profile == "Logarithmic":
            # Mathematical function goes here
            points = t
        else:
            points = t
        return points.tolist()

    # Sequenced activation - Adding, removing steps and start sequence
    def set_steps(self, seq_steps):
        self.seq_steps = seq_steps
        self._reset_send_state()

    def build_sequence_payload(self):
        steps = []
        for s in self.seq_steps:
            step = s.get_step()
            if not step["actions"]:
                continue
            steps.append({
                "actions": step["actions"],
                "duration_ms": None if step["hold"] else int(step["duration"] * 1000),
                "hold": step["hold"],
            })
        return {"sequence": steps, "step_count": len(steps)}

    def send_sequence(self):
        if not self.seq_steps:
            if self.on_seq_status_changed:
                self.on_seq_status_changed("No steps to send.", "#ff6b35")
            return False
        payload = self.build_sequence_payload()
        if payload["step_count"] == 0:
            if self.on_seq_status_changed:
                self.on_seq_status_changed("No valves selected in any step.", "#ff6b35")
            return False
        self.sent_sequence = payload
        self.sequence_sent = True
        if self.on_seq_status_changed:
            self.on_seq_status_changed(
                f"Sent {payload['step_count']} step(s) to ESP32.\nPress RUN when ready.",
                "#7fff6b"
            )
        return True

    def run_sequence(self):
        if not self.sequence_sent or not self.sent_sequence:
            if self.on_seq_status_changed:
                self.on_seq_status_changed("Send sequence first.", "#ff6b35")
            return False
        self.seq_running = True
        self.seq_index = 0
        if self.on_seq_status_changed:
            self.on_seq_status_changed(
                f"Running {self.sent_sequence['step_count']} step(s) on ESP32...",
                "#00d4ff"
            )
        return True

    def _seq_next(self):
        pass

    def _seq_stop(self):
        self.seq_running = False
        self.seq_timer.stop()

    def _seq_done(self):
        self.seq_running = False
        if self.on_seq_status_changed:
            self.on_seq_status_changed("Sequence complete.", "#7fff6b")

    def _reset_send_state(self):
        self.sequence_sent = False
        self.sent_sequence = None
        if self.on_seq_status_changed:
            if self.seq_steps:
                self.on_seq_status_changed("Sequence edited — resend required.", "#888")
            else:
                self.on_seq_status_changed("", "#888")