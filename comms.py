import json


class Comms:
    def _send(self, payload):
        print(f"[Comms] {json.dumps(payload)}")
        return {"status": "ok"}

    def read_pressures(self):
        response = self._send({"cmd": "READ_PRESSURES"})
        if response and "pressures" in response:
            return response["pressures"]
        print("[Comms] Failed to read pressures or malformed response.")
        return None

    def send_valve_command(self, valve_name, action):
        self._send({"cmd": "SET_VALVE", "valve": valve_name, "action": action})

    def send_panic(self):
        self._send({"cmd": "PANIC"})

    def send_sequence(self, payload):
        payload["cmd"] = "LOAD_SEQUENCE"
        self._send(payload)

    def run_sequence(self):
        self._send({"cmd": "RUN_SEQUENCE"})