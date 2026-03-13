import json
import requests
from PyQt6.QtCore import QThread, pyqtSignal

ESP32_BASE_URL = "http://192.168.4.1"
TIMEOUT_S = 3


class SendWorker(QThread):
    succeeded = pyqtSignal()
    failed    = pyqtSignal(str)

    def __init__(self, payload: dict):
        super().__init__()
        self.payload = payload

    def run(self):
        url = f"{ESP32_BASE_URL}/sequence"
        try:
            resp = requests.post(url, json=self.payload, timeout=TIMEOUT_S)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "ok":
                self.succeeded.emit()
            else:
                self.failed.emit(f"Unexpected response: {data}")
        except requests.exceptions.ConnectionError:
            self.failed.emit("No connection to ESP32.")
        except requests.exceptions.Timeout:
            self.failed.emit("Timed out — try again.")
        except requests.exceptions.HTTPError as e:
            self.failed.emit(f"HTTP {e.response.status_code} — try again.")
        except Exception as e:
            self.failed.emit(f"Error: {e}")


class Comms:
    def _send(self, endpoint: str, payload: dict) -> dict | None:
        url = f"{ESP32_BASE_URL}{endpoint}"
        try:
            resp = requests.post(url, json=payload, timeout=TIMEOUT_S)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            print(f"[Comms] ERROR: Could not connect to ESP32 at {ESP32_BASE_URL}")
            return None
        except requests.exceptions.Timeout:
            print(f"[Comms] ERROR: Request timed out after {TIMEOUT_S}s")
            return None
        except requests.exceptions.HTTPError as e:
            print(f"[Comms] ERROR: HTTP {e.response.status_code} from ESP32")
            return None
        except Exception as e:
            print(f"[Comms] ERROR: {e}")
            return None

    def read_pressures(self) -> list[float] | None:
        # GET /pressures. ESP32 returns a JSON array of 4 pressure values
        url = f"{ESP32_BASE_URL}/pressures"
        try:
            resp = requests.get(url, timeout=TIMEOUT_S)
            resp.raise_for_status()
            data = resp.json()
            if "pressures" in data:
                return data["pressures"]
            return None
        except Exception:
            return None

    def send_valve_command(self, valve_name: str, action: str) -> bool:
        result = self._send("/valve", {"cmd": "SET_VALVE", "valve": valve_name, "action": action})
        return result is not None and result.get("status") == "ok"

    def send_panic(self) -> bool:
        result = self._send("/panic", {"cmd": "PANIC"})
        return result is not None and result.get("status") == "ok"

    def run_sequence(self) -> bool:
        result = self._send("/run", {"cmd": "RUN_SEQUENCE"})
        return result is not None and result.get("status") == "ok"
