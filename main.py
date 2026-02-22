import sys
import random
import math
import csv
import os
import json
import time
from datetime import datetime
from collections import deque
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QGridLayout, QFrame, QPushButton,
    QDoubleSpinBox, QComboBox, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont
import pyqtgraph as pg
# config - tweak these as needed
MAX_POINTS = 200 # Amount of points in realtime graph (MAX_POINTS/(1000/UPDATE_RATE_MS)) is timeframe for realtime graph
UPDATE_RATE_MS = 50  # In ms, so 50ms = 20 Hz
CHANNELS = [
    {"name": "P1 - Pressurant",     "unit": "bar", "color": "#00d4ff", "base": 50.0, "noise": 4.3},
    {"name": "P2 - Oxidiser Tank",  "unit": "bar", "color": "#ff6b35", "base": 60.5,  "noise": 7.2},
    {"name": "P3 - Injector",       "unit": "bar", "color": "#7fff6b", "base": 20.2,  "noise": 2.15},
]
VALVES = ["Solenoid Valve 1", "Solenoid Valve 2", "Servo Valve 1"]
VALVE_COLORS = ["#00d4ff", "#ff6b35", "#7fff6b"]
# Data source for graphs
class DataSource:
    def __init__(self):
        self.t = 0.0
    def read_data(self):
        self.t += UPDATE_RATE_MS / 1000.0
        return [
            round(ch["base"] + ch["noise"] * math.sin(self.t * 1.5 + ch["base"])
                  + random.gauss(0, ch["noise"] * 0.3), 3)
            for ch in CHANNELS
        ]
# UI - Toggle switch for the valve controls
class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)
    def __init__(self, color="#00d4ff"):
        super().__init__()
        self.state = False
        self.color = color
        self.setFixedSize(56, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def mousePressEvent(self, e):
        self.state = not self.state
        self.toggled.emit(self.state)
        self.update()
    def paintEvent(self, e):
        from PyQt6.QtGui import QPainter, QColor
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track_color = QColor(self.color) if self.state else QColor("#2a2a2a")
        p.setBrush(track_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 4, 56, 20, 10, 10)
        thumb_x = 30 if self.state else 4
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(thumb_x, 2, 24, 24)
        p.end()
# UI - Custom checkbox for valve activation in sequencer - uses clear unicode box characters instead of the ugly default
class ValveCheckBox(QWidget):
    stateChanged = pyqtSignal(bool)
    def __init__(self, label, color):
        super().__init__()
        self.checked = False
        self.color = color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self.box_lbl = QLabel("☐")
        self.box_lbl.setFont(QFont("Courier New", 14))
        self.box_lbl.setStyleSheet("color: #444;")
        self.box_lbl.setFixedWidth(20)
        self.text_lbl = QLabel(label)
        self.text_lbl.setFont(QFont("Courier New", 9))
        self.text_lbl.setStyleSheet(f"color: {color};")
        h.addWidget(self.box_lbl)
        h.addWidget(self.text_lbl)
    def mousePressEvent(self, e):
        self.checked = not self.checked
        self.stateChanged.emit(self.checked)
        self.box_lbl.setText("☑" if self.checked else "☐")
        self.box_lbl.setStyleSheet(f"color: {self.color};" if self.checked else "color: #444;")
    def isChecked(self):
        return self.checked
    def text(self):
        return self.text_lbl.text()
# Logic - Sequencer Activation - Valve Selection and duration
class SequenceStep(QFrame):
    removed = pyqtSignal(object)
    def __init__(self, step_num):
        super().__init__()
        self.setObjectName("seqStep")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)
        # Valve sequence step header
        top = QHBoxLayout()
        self.num_lbl = QLabel(f"STEP {step_num:02d}")
        self.num_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self.num_lbl.setObjectName("sectionHeader")
        top.addWidget(self.num_lbl)
        top.addStretch()
        btn_del = QPushButton("✕")
        btn_del.setFixedSize(18, 18)
        btn_del.setObjectName("btn_del")
        btn_del.clicked.connect(lambda: self.removed.emit(self))
        top.addWidget(btn_del)
        outer.addLayout(top)
        # Row in the step card for each valve
        self.valve_actions = []
        for i, name in enumerate(VALVES):
            row = QHBoxLayout()
            row.setSpacing(8)
            cb = ValveCheckBox(name, VALVE_COLORS[i])
            action_cb = QComboBox()
            action_cb.addItems(["OPEN", "CLOSE"])
            action_cb.setFixedWidth(80)
            row.addWidget(cb, stretch=1)
            row.addWidget(action_cb)
            outer.addLayout(row)
            self.valve_actions.append((cb, action_cb))
        # Duration of Valve activation
        bot = QHBoxLayout()
        dur_lbl = QLabel("Duration:")
        dur_lbl.setFont(QFont("Courier New", 9))
        dur_lbl.setStyleSheet("color: #555;")
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.05, 9999.0)
        self.duration_spin.setValue(1.0)
        self.duration_spin.setSingleStep(0.1)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setFixedWidth(85)
        self.duration_spin.setSuffix(" s")
        self.inf_btn = QPushButton("∞")
        self.inf_btn.setFixedSize(28, 28)
        self.inf_btn.setObjectName("btn_inf")
        self.inf_btn.setCheckable(True)
        self.inf_btn.setFont(QFont("Courier New", 13))
        self.inf_btn.toggled.connect(self._toggle_inf)
        bot.addWidget(dur_lbl)
        bot.addWidget(self.duration_spin)
        bot.addWidget(self.inf_btn)
        bot.addStretch()
        outer.addLayout(bot)
    def _toggle_inf(self, checked):
        self.duration_spin.setEnabled(not checked)
        self.duration_spin.setStyleSheet("color: #333;" if checked else "")
    def get_step(self):
        actions = [
            {"valve": cb.text(), "action": action_cb.currentText()}
            for cb, action_cb in self.valve_actions if cb.isChecked()
        ]
        return {
            "actions": actions,
            "duration": self.duration_spin.value(),
            "hold": self.inf_btn.isChecked(),
        }
# UI - Main window integrating everything together and program for realtime graph updating
class FlowBench(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowBench")
        self.setMinimumSize(1200, 760)
        self.dark_mode = True
        self.setStyleSheet(self._stylesheet())
        self.source = DataSource()
        self.buffers = [deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS) for _ in CHANNELS]
        self.t_count = 0.0
        self.valve_states = [False] * len(VALVES)
        self.pressure_log_path = None
        self.valve_log_path = None
        self.recording = False
        self.record_start_time = None
        self.seq_steps = []
        self.seq_running = False
        self.seq_index = 0
        self.seq_timer = QTimer()
        self.seq_timer.setSingleShot(True)
        self.seq_timer.timeout.connect(self._seq_next)
        self.sent_sequence = None
        self.sequence_sent = False
        self._build_ui()
        self.data_timer = QTimer()
        self.data_timer.setInterval(UPDATE_RATE_MS)
        self.data_timer.timeout.connect(self._update)
        self.data_timer.start()
    # Builds the main UI layuout - Integrating all elements
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setSpacing(8)
        main.setContentsMargins(12, 12, 12, 12)
        main.addWidget(self._title_bar())
        body = QHBoxLayout()
        body.setSpacing(8)
        body.addLayout(self._graphs_layout(), stretch=3)
        body.addWidget(self._control_panel(), stretch=1)
        main.addLayout(body)
    def _title_bar(self):
        frame = QFrame()
        frame.setObjectName("titleBar")
        frame.setFixedHeight(48)
        h = QHBoxLayout(frame)
        self.btn_theme = QPushButton("LIGHT")
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.setFixedWidth(70)
        self.btn_theme.clicked.connect(self._toggle_theme)
        h.addWidget(self.btn_theme)
        lbl = QLabel("FLOWBENCH")
        lbl.setFont(QFont("Courier New", 20, QFont.Weight.Bold))
        lbl.setObjectName("titleLbl")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(lbl, stretch=1)
        return frame
    def _graphs_layout(self):
        grid = QGridLayout()
        grid.setSpacing(8)
        self.curves = []
        self.val_labels = []
        self.plots = []
        for i, ch in enumerate(CHANNELS):
            container, curve, val_lbl = self._make_graph_box(ch)
            self.curves.append(curve)
            self.val_labels.append(val_lbl)
            grid.addWidget(container, i // 2, i % 2)
        combined = QFrame()
        combined.setObjectName("graphBox")
        vbox = QVBoxLayout(combined)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(4)
        legend = QHBoxLayout()
        lbl_all = QLabel("All Channels")
        lbl_all.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl_all.setStyleSheet("color: #888;")
        legend.addWidget(lbl_all)
        legend.addStretch()
        for ch in CHANNELS:
            dot = QLabel(f"● {ch['name']}")
            dot.setFont(QFont("Courier New", 9))
            dot.setStyleSheet(f"color: {ch['color']};")
            legend.addWidget(dot)
        vbox.addLayout(legend)
        self.combined_plot = pg.PlotWidget()
        self.combined_plot.setBackground("#0d0d0d")
        self.combined_plot.showGrid(x=True, y=True, alpha=0.15)
        self.combined_plot.setLabel("left", "bar")
        self.combined_plot.setLabel("bottom", "time (s)")
        self.combined_plot.getAxis("left").setTextPen(pg.mkPen("#888"))
        self.combined_plot.getAxis("bottom").setTextPen(pg.mkPen("#888"))
        self.combined_plot.enableAutoRange(axis='y')
        self.combined_curves = []
        for ch in CHANNELS:
            c = self.combined_plot.plot(pen=pg.mkPen(color=ch["color"], width=1.8))
            self.combined_curves.append(c)
        vbox.addWidget(self.combined_plot)
        grid.addWidget(combined, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        return grid
    def _make_graph_box(self, ch):
        container = QFrame()
        container.setObjectName("graphBox")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(4)
        top = QHBoxLayout()
        lbl = QLabel(ch["name"])
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {ch['color']};")
        val_lbl = QLabel("— bar")
        val_lbl.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        val_lbl.setStyleSheet(f"color: {ch['color']};")
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        top.addWidget(lbl)
        top.addStretch()
        top.addWidget(val_lbl)
        vbox.addLayout(top)
        plot = pg.PlotWidget()
        plot.setBackground("#0d0d0d")
        plot.showGrid(x=True, y=True, alpha=0.15)
        plot.setLabel("left", ch["unit"])
        plot.setLabel("bottom", "time (s)")
        plot.getAxis("left").setTextPen(pg.mkPen("#888"))
        plot.getAxis("bottom").setTextPen(pg.mkPen("#888"))
        plot.enableAutoRange(axis='y')
        curve = plot.plot(
            pen=pg.mkPen(color=ch["color"], width=1.8),
        )
        vbox.addWidget(plot)
        self.plots.append(plot)
        return container, curve, val_lbl
    # Control panel - Manual Valve actuation + Sequenced actuation
    def _control_panel(self):
        panel = QFrame()
        panel.setObjectName("controlPanel")
        panel.setFixedWidth(300)
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(10)
        # Manual toggle switches for valves
        valve_header = QLabel("VALVE CONTROL")
        valve_header.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        valve_header.setObjectName("sectionHeader")
        vbox.addWidget(valve_header)
        self.valve_switches = []
        self.valve_status_labels = []
        for i, name in enumerate(VALVES):
            row = QFrame()
            row.setObjectName("valveRow")
            h = QHBoxLayout(row)
            h.setContentsMargins(8, 6, 8, 6)
            name_lbl = QLabel(name)
            name_lbl.setFont(QFont("Courier New", 9))
            name_lbl.setObjectName("valveName")
            status_lbl = QLabel("CLOSED")
            status_lbl.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            status_lbl.setStyleSheet("color: #333;")
            status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.valve_status_labels.append(status_lbl)
            toggle = ToggleSwitch(color=VALVE_COLORS[i])
            toggle.toggled.connect(lambda state, x=i: self._valve_toggled(x, state))
            self.valve_switches.append(toggle)
            h.addWidget(name_lbl)
            h.addStretch()
            h.addWidget(status_lbl)
            h.addWidget(toggle)
            vbox.addWidget(row)
        # E-Stop button to shutoff all valves
        btn_panic = QPushButton("⚠  PANIC — CLOSE ALL")
        btn_panic.setObjectName("btn_panic")
        btn_panic.clicked.connect(self._panic)
        vbox.addWidget(btn_panic)
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background: #1e1e1e; max-height: 1px;")
        vbox.addWidget(div)
        # Sequence builder
        seq_header = QLabel("SEQUENCE")
        seq_header.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        seq_header.setObjectName("sectionHeader")
        vbox.addWidget(seq_header)
        self.seq_container = QWidget()
        self.seq_container.setStyleSheet("background: transparent;")
        self.seq_layout = QVBoxLayout(self.seq_container)
        self.seq_layout.setSpacing(6)
        self.seq_layout.setContentsMargins(0, 0, 4, 0)
        self.seq_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidget(self.seq_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMinimumHeight(180)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: #0d0d0d; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #2a2a2a; border-radius: 3px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        vbox.addWidget(scroll, stretch=1)
        btn_add = QPushButton("+ ADD STEP")
        btn_add.setObjectName("btn_add")
        btn_add.clicked.connect(self._add_step)
        vbox.addWidget(btn_add)
        self.btn_send = QPushButton("SEND SEQUENCE")
        self.btn_send.setObjectName("btn_send")
        self.btn_send.clicked.connect(self._seq_send)
        vbox.addWidget(self.btn_send)
        self.btn_run = QPushButton("RUN")
        self.btn_run.setObjectName("btn_run")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._seq_start)
        vbox.addWidget(self.btn_run)
        self.btn_record = QPushButton("RECORD")
        self.btn_record.setObjectName("btn_record")
        self.btn_record.setCheckable(True)
        self.btn_record.clicked.connect(self._toggle_record)
        vbox.addWidget(self.btn_record)
        self.seq_status = QLabel("")
        self.seq_status.setFont(QFont("Courier New", 8))
        self.seq_status.setStyleSheet("color: #555;")
        self.seq_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.seq_status.setWordWrap(True)
        vbox.addWidget(self.seq_status)
        return panel
    # Manual Valve activation toggle logic
    def _valve_toggled(self, idx, state):
        self.valve_states[idx] = state
        lbl = self.valve_status_labels[idx]
        if state:
            lbl.setText("OPEN")
            lbl.setStyleSheet(f"color: {VALVE_COLORS[idx]}; font-weight: bold;")
        else:
            lbl.setText("CLOSED")
            lbl.setStyleSheet("color: #333;")
        # If recording valve state is logged whenever there is a change alongside with the time
        if self.recording and self.valve_log_path:
            elapsed = round(time.perf_counter() - self.record_start_time, 4)
            with open(self.valve_log_path, 'a', newline='') as f:
                csv.writer(f).writerow([
                    elapsed,
                    "OPEN" if self.valve_states[0] else "CLOSED",
                    "OPEN" if self.valve_states[1] else "CLOSED",
                    "OPEN" if self.valve_states[2] else "CLOSED",
                ])
    def _set_valve(self, valve_name, action):
        idx = VALVES.index(valve_name)
        state = (action == "OPEN")
        self.valve_states[idx] = state
        self.valve_switches[idx].state = state
        self.valve_switches[idx].update()
        self._valve_toggled(idx, state)
    def _panic(self):
        self._seq_stop()
        for name in VALVES:
            self._set_valve(name, "CLOSE")
        self.seq_status.setText("PANIC — all valves closed")
        self.seq_status.setStyleSheet("color: #ff3333;")
    def _build_sequence_payload(self):
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
    def _seq_send(self):
        if not self.seq_steps:
            self.seq_status.setText("No steps to send.")
            self.seq_status.setStyleSheet("color: #ff6b35;")
            return
        payload = self._build_sequence_payload()
        if payload["step_count"] == 0:
            self.seq_status.setText("No valves selected in any step.")
            self.seq_status.setStyleSheet("color: #ff6b35;")
            return
        # Wi-Fi send command to ESP32 goes here
        print("Command sent")
        self.sent_sequence = payload
        self.sequence_sent = True
        self.btn_run.setEnabled(True)
        self.btn_send.setStyleSheet("color: #7fff6b; border-color: #7fff6b; background: #7fff6b12;")
        self.seq_status.setText(
            f"Sent {payload['step_count']} step(s) to ESP32.\nPress RUN when ready."
        )
        self.seq_status.setStyleSheet("color: #7fff6b;")
    def _reset_send_state(self):
        self.sequence_sent = False
        self.sent_sequence = None
        self.btn_run.setEnabled(False)
        self.btn_send.setStyleSheet("")
        if self.seq_steps:
            self.seq_status.setText("Sequence edited — resend required.")
            self.seq_status.setStyleSheet("color: #888;")
        else:
            self.seq_status.setText("")
    # Sequenced activation - Adding, removing steps and start sequence
    def _add_step(self):
        step_num = len(self.seq_steps) + 1
        step = SequenceStep(step_num)
        step.removed.connect(self._remove_step)
        self.seq_layout.insertWidget(self.seq_layout.count() - 1, step)
        self.seq_steps.append(step)
        self._reset_send_state()
    def _remove_step(self, step_widget):
        if step_widget in self.seq_steps:
            self.seq_steps.remove(step_widget)
            self.seq_layout.removeWidget(step_widget)
            step_widget.deleteLater()
            for i, s in enumerate(self.seq_steps):
                s.num_lbl.setText(f"STEP {i+1:02d}")
            self._reset_send_state()
    def _seq_start(self):
        if not self.sequence_sent or not self.sent_sequence:
            self.seq_status.setText("Send sequence first.")
            self.seq_status.setStyleSheet("color: #ff6b35;")
            return
        # Wi-Fi send command to ESP32 goes here
        print("Command sent")
        self.seq_running = True
        self.btn_run.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.seq_status.setText(
            f"Running {self.sent_sequence['step_count']} step(s) on ESP32..."
        )
        self.seq_status.setStyleSheet("color: #00d4ff;")
    def _seq_next(self):
        pass
    def _seq_stop(self):
        pass
    def _seq_done(self):
        self.seq_running = False
        self.btn_run.setEnabled(self.sequence_sent)
        self.btn_send.setEnabled(True)
        self.seq_status.setText("Sequence complete.")
        self.seq_status.setStyleSheet("color: #7fff6b;")
    # Recording and logging logic
    def _toggle_record(self, checked):
        self.recording = checked
        if checked:
            self.record_start_time = time.perf_counter()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_dir = os.path.dirname(os.path.abspath(__file__))
            self.pressure_log_path = os.path.join(log_dir, f"pressure_{ts}.csv")
            self.valve_log_path = os.path.join(log_dir, f"valves_{ts}.csv")
            with open(self.pressure_log_path, 'w', newline='') as f:
                csv.writer(f).writerow(["time_elapsed", "P1_Pressurant_bar", "P2_OxidiserTank_bar", "P3_Injector_bar"])
            with open(self.valve_log_path, 'w', newline='') as f:
                csv.writer(f).writerow(["time_elapsed", "Solenoid_Valve_1", "Solenoid_Valve_2", "Servo_Valve_1"])
            self.btn_record.setText("STOP RECORDING")
            self.btn_record.setStyleSheet("color: #ff3333; border-color: #ff3333; background: #ff333318;")
        else:
            self.record_start_time = None
            self.btn_record.setText("RECORD")
            self.btn_record.setStyleSheet("")
    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.setStyleSheet(self._stylesheet())
        self.btn_theme.setText("LIGHT" if self.dark_mode else "DARK")
        bg = "#0d0d0d" if self.dark_mode else "#f5f5f5"
        axis_color = "#888" if self.dark_mode else "#444"
        step_lbl_color = "#fff" if self.dark_mode else "#000"
        for plot in self.plots + [self.combined_plot]:
            plot.setBackground(bg)
            plot.getAxis("left").setTextPen(pg.mkPen(axis_color))
            plot.getAxis("bottom").setTextPen(pg.mkPen(axis_color))
        for step in self.seq_steps:
            step.num_lbl.setStyleSheet(f"color: {step_lbl_color}; letter-spacing: 2px;")
            for cb, _ in step.valve_actions:
                cb.text_lbl.setStyleSheet(f"color: {cb.color};" if self.dark_mode else f"color: #000;")
    # Called every Update Rate to update the graphs
    def _update(self):
        values = self.source.read_data()
        self.t_count += UPDATE_RATE_MS / 1000.0
        x = [self.t_count - MAX_POINTS * UPDATE_RATE_MS / 1000.0 + j * UPDATE_RATE_MS / 1000.0
             for j in range(MAX_POINTS)]
        for i, val in enumerate(values):
            self.buffers[i].append(val)
            self.val_labels[i].setText(f"{val:.2f} bar")
            self.curves[i].setData(x, list(self.buffers[i]))
            self.combined_curves[i].setData(x, list(self.buffers[i]))
        # Write pressures to csv file if recording
        if self.recording and self.pressure_log_path:
            elapsed = round(time.perf_counter() - self.record_start_time, 4)
            with open(self.pressure_log_path, 'a', newline='') as f:
                csv.writer(f).writerow([elapsed] + [f"{v:.4f}" for v in values])
    # Styles
    def _stylesheet(self):
        if self.dark_mode:
            bg_app_base        = "#0a0a0a"   # outermost window / widget background
            bg_panel_surface   = "#0d0d0d"   # card/panel surfaces (title bar, graph boxes, control panel)
            bg_element_raised  = "#111111"   # slightly raised elements within panels (valve rows, seq steps)
            border_subtle      = "#1e1e1e"   # outer panel borders
            border_interactive = "#2a2a2a"   # borders on interactive controls (buttons, inputs, scroll handle)
            text_primary       = "#cccccc"   # main readable text
            text_muted         = "#888888"   # secondary / dimmed text and default button labels
            accent_color       = "#00d4ff"   # brand cyan - titles, active states
            bg_button_default  = "#1a1a1a"   # default button and input field background
        else:
            bg_app_base        = "#f0f0f0"
            bg_panel_surface   = "#ffffff"
            bg_element_raised  = "#e8e8e8"
            border_subtle      = "#d0d0d0"
            border_interactive = "#c0c0c0"
            text_primary       = "#000000"
            text_muted         = "#000000"
            accent_color       = "#0077aa"
            bg_button_default  = "#e8e8e8"
        return f"""
        QMainWindow, QWidget {{
            background-color: {bg_app_base};
            color: {text_primary};
            font-family: 'Courier New', monospace;
            border: none;
        }}
        QLabel {{
            color: {text_primary};
            border: none;
            background: transparent;
        }}
        QFrame {{
            border: none;
        }}
        #titleBar {{
            background: {bg_panel_surface};
            border: 1px solid {border_subtle};
            border-radius: 6px;
        }}
        #titleLbl {{ color: {accent_color}; letter-spacing: 6px; }}
        #graphBox {{
            background: {bg_panel_surface};
            border: 1px solid {border_subtle};
            border-radius: 6px;
        }}
        #controlPanel {{
            background: {bg_panel_surface};
            border: 1px solid {border_subtle};
            border-radius: 6px;
        }}
        QLabel#valveName {{ color: {text_primary}; }}
        QLabel#sectionHeader {{ color: {text_primary}; letter-spacing: 2px; font-weight: bold; }}
        #valveRow {{
            background: {bg_element_raised};
            border: 1px solid {border_subtle};
            border-radius: 4px;
        }}
        #seqStep {{
            background: {bg_element_raised};
            border: 1px solid {border_interactive};
            border-radius: 5px;
        }}
        QComboBox {{
            background: {bg_button_default};
            border: 1px solid {border_interactive};
            border-radius: 3px;
            padding: 3px 6px;
            color: {text_primary};
            font-family: 'Courier New';
            font-size: 10px;
        }}
        QComboBox::drop-down {{ border: none; width: 16px; }}
        QComboBox QAbstractItemView {{
            background: {bg_button_default};
            border: 1px solid {border_subtle};
            selection-background-color: {bg_element_raised};
            color: {text_primary};
            font-family: 'Courier New';
            font-size: 10px;
            outline: none;
        }}
        QDoubleSpinBox {{
            background: {bg_button_default};
            border: 1px solid {border_interactive};
            border-radius: 3px;
            padding: 3px 4px;
            color: {text_primary};
            font-family: 'Courier New';
            font-size: 10px;
        }}
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 14px; }}
        QPushButton {{
            background: {bg_button_default};
            color: {text_muted};
            border: 1px solid {border_interactive};
            border-radius: 4px;
            padding: 6px 12px;
            font-family: 'Courier New';
            font-weight: bold;
            font-size: 10px;
            letter-spacing: 1px;
        }}
        QPushButton:hover {{ background: {bg_element_raised}; color: {text_primary}; border-color: {border_subtle}; }}
        QPushButton:disabled {{ color: {border_interactive}; border-color: {bg_button_default}; }}
        #btn_add {{ color: {text_muted}; border-style: dashed; }}
        #btn_add:hover {{ color: {text_primary}; border-color: {border_subtle}; }}
        #btn_run {{ color: #7fff6b; border-color: #7fff6b; }}
        #btn_run:hover {{ background: #7fff6b15; }}
        #btn_run:disabled {{ color: {border_interactive}; border-color: {bg_button_default}; }}
        #btn_send {{
            color: #00d4ff;
            border: 1px solid #00d4ff;
            border-radius: 4px;
            padding: 7px 12px;
            font-size: 10px;
            letter-spacing: 1px;
        }}
        #btn_send:hover {{ background: #00d4ff15; }}
        #btn_send:disabled {{ color: {border_interactive}; border-color: {bg_button_default}; }}
        #btn_panic {{
            color: #ff3333;
            border: 2px solid #ff3333;
            border-radius: 4px;
            padding: 8px;
            font-size: 11px;
            letter-spacing: 1px;
        }}
        #btn_panic:hover {{ background: #ff333320; }}
        #btn_theme {{
            color: {text_muted};
            border: 1px solid {border_interactive};
            border-radius: 4px;
            font-size: 9px;
            padding: 4px 8px;
        }}
        #btn_theme:hover {{ color: {text_primary}; }}
        #btn_record {{
            color: #ff6b6b;
            border: 1px solid #ff6b6b;
            border-radius: 4px;
            padding: 6px 12px;
            font-size: 10px;
            letter-spacing: 1px;
        }}
        #btn_record:hover {{ background: #ff6b6b18; }}
        #btn_del {{
            background: transparent;
            color: {text_muted};
            border: none;
            padding: 0;
            font-size: 11px;
        }}
        #btn_del:hover {{ color: #ff4444; }}
        #btn_inf {{
            background: {bg_button_default};
            color: {text_muted};
            border: 1px solid {border_interactive};
            border-radius: 4px;
            padding: 0;
        }}
        #btn_inf:hover {{ color: {text_primary}; border-color: {border_subtle}; }}
        #btn_inf:checked {{ color: {accent_color}; border-color: {accent_color}; background: transparent; }}
        QScrollArea {{ background: transparent; border: none; }}
        QScrollBar:vertical {{ background: {bg_panel_surface}; width: 6px; border-radius: 3px; }}
        QScrollBar::handle:vertical {{ background: {border_interactive}; border-radius: 3px; min-height: 20px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("FlowBench")
    window = FlowBench()
    window.show()
    sys.exit(app.exec())