#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RS485 Serial Communication Tool with CRC16-Modbus (PyQt版)

- 使用 PyQt5 取代 Tkinter
- 使用 QTimer 輪詢串列埠，避免背景 thread
"""

import sys
import time

from typing import Optional, List

import serial
import serial.tools.list_ports

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QComboBox,
    QFileDialog,
    QPlainTextEdit,
    QMessageBox,
)


class CRC16Modbus:
    """CRC16-Modbus calculator with polynomial 0xA001 and initial value 0xFFFF"""

    @staticmethod
    def calculate(data: bytes) -> int:
        crc = 0xFFFF
        polynomial = 0xA001

        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ polynomial
                else:
                    crc >>= 1

        return crc

    @staticmethod
    def to_bytes_le(crc: int) -> bytes:
        # little-endian (low byte first)
        return crc.to_bytes(2, byteorder="little")


class RS485SerialToolWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("RS485 Serial Communication Tool (PyQt)")
        self.resize(900, 900)

        # Serial communication attributes
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected: bool = False

        # Polling timer
        self.polling_interval = 100  # ms
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_serial_data)

        # File / segment attributes
        self.file_segments: List[str] = []
        self.current_segment_index: int = 0
        self.waiting_for_reply: bool = False
        self.reply_received: bool = False
        self.validation_failed: bool = False
        self.auto_send_running: bool = False

        # Reply timeout（用 singleShot）
        # 單次排程就好，不需要一直開 timer

        self._build_ui()
        self.refresh_ports()

    # ------------------------------------------------------------------
    # UI 建構
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 1. Connection
        conn_group = self._create_connection_group()
        main_layout.addWidget(conn_group)

        # 2. Quick Test
        quick_group = self._create_quick_test_group()
        main_layout.addWidget(quick_group)

        # 3. File loading
        file_group = self._create_file_group()
        main_layout.addWidget(file_group)

        # 4. HEX Input / Segments
        input_group = self._create_input_group()
        main_layout.addWidget(input_group, 1)  # 這個區塊可以多吃一點空間

        # 5. Log
        log_group = self._create_log_group()
        main_layout.addWidget(log_group, 2)

    # --------------------- Connection Group ----------------------------
    def _create_connection_group(self) -> QGroupBox:
        group = QGroupBox("Connection Settings", self)
        layout = QGridLayout(group)
        layout.setSpacing(6)

        # Port
        layout.addWidget(QLabel("Port:"), 0, 0)
        self.port_combo = QComboBox()
        layout.addWidget(self.port_combo, 0, 1)

        # Baudrate
        layout.addWidget(QLabel("Baudrate:"), 0, 2)
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baudrate_combo.setCurrentText("9600")
        layout.addWidget(self.baudrate_combo, 0, 3)

        # Data Bits
        layout.addWidget(QLabel("Data Bits:"), 1, 0)
        self.databits_combo = QComboBox()
        self.databits_combo.addItems(["7", "8"])
        self.databits_combo.setCurrentText("8")
        layout.addWidget(self.databits_combo, 1, 1)

        # Parity
        layout.addWidget(QLabel("Parity:"), 1, 2)
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["N (None)", "E (Even)", "O (Odd)"])
        self.parity_combo.setCurrentText("N (None)")
        layout.addWidget(self.parity_combo, 1, 3)

        # Stop Bits
        layout.addWidget(QLabel("Stop Bits:"), 1, 4)
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems(["1", "2"])
        self.stopbits_combo.setCurrentText("1")
        layout.addWidget(self.stopbits_combo, 1, 5)

        # Buttons
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_serial)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.clicked.connect(self.disconnect_serial)

        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedWidth(30)
        self.refresh_btn.clicked.connect(self.refresh_ports)

        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.disconnect_btn)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout, 2, 0, 1, 6)

        return group

    # --------------------- Quick Test Group ----------------------------
    def _create_quick_test_group(self) -> QGroupBox:
        group = QGroupBox("Quick Test (for application testing)", self)
        vbox = QVBoxLayout(group)

        vbox.addWidget(QLabel("Test Data:"))

        self.quick_test_input = QTextEdit()
        self.quick_test_input.setPlaceholderText("輸入 HEX 或 ASCII 測試資料")
        vbox.addWidget(self.quick_test_input)

        btn_layout = QHBoxLayout()
        self.hex_btn = QPushButton("Hex")
        self.hex_btn.clicked.connect(lambda: self.quick_test_send("hex"))

        self.hex_crc_btn = QPushButton("Hex+CRC")
        self.hex_crc_btn.clicked.connect(lambda: self.quick_test_send("hex_crc"))

        self.ascii_btn = QPushButton("ASCII")
        self.ascii_btn.clicked.connect(lambda: self.quick_test_send("ascii"))

        self.ascii_crc_btn = QPushButton("ASCII+CRC")
        self.ascii_crc_btn.clicked.connect(lambda: self.quick_test_send("ascii_crc"))

        self.clear_quick_btn = QPushButton("Clear")
        self.clear_quick_btn.clicked.connect(self.clear_quick_test)

        for b in [
            self.hex_btn,
            self.hex_crc_btn,
            self.ascii_btn,
            self.ascii_crc_btn,
            self.clear_quick_btn,
        ]:
            btn_layout.addWidget(b)

        btn_layout.addStretch()
        vbox.addLayout(btn_layout)

        return group

    # --------------------- File Group ----------------------------------
    def _create_file_group(self) -> QGroupBox:
        group = QGroupBox("File Loading (Optional - for large data)", self)
        layout = QGridLayout(group)

        # File path
        layout.addWidget(QLabel("File:"), 0, 0)
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        layout.addWidget(self.file_path_edit, 0, 1)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_file)
        layout.addWidget(self.browse_btn, 0, 2)

        # Chunk size
        layout.addWidget(QLabel("Chunk Size (chars):"), 1, 0)
        self.chunk_size_edit = QLineEdit("100")
        layout.addWidget(self.chunk_size_edit, 1, 1)

        self.load_file_btn = QPushButton("Load & Split")
        self.load_file_btn.clicked.connect(self.load_and_split_file)
        layout.addWidget(self.load_file_btn, 1, 2)

        # Status
        self.file_status_label = QLabel("No file loaded")
        self.file_status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.file_status_label, 2, 0, 1, 3)

        return group

    # --------------------- Input Group ---------------------------------
    def _create_input_group(self) -> QGroupBox:
        group = QGroupBox("HEX Input (0-9, A-F only)", self)
        layout = QGridLayout(group)
        layout.setRowStretch(0, 1)
        layout.setColumnStretch(3, 1)

        # Prefix
        prefix_label = QLabel("Prefix:")
        self.prefix_edit = QTextEdit()
        self.prefix_edit.setFixedHeight(80)
        layout.addWidget(prefix_label, 0, 0)
        layout.addWidget(self.prefix_edit, 1, 0)

        # Block #
        block_label = QLabel("Block #:")
        self.block_display = QLineEdit()
        self.block_display.setReadOnly(True)
        self.block_display.setFixedHeight(30)
        self.block_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(block_label, 0, 1)
        layout.addWidget(self.block_display, 1, 1)

        # Length
        length_label = QLabel("Length:")
        self.length_display = QLineEdit()
        self.length_display.setReadOnly(True)
        self.length_display.setFixedHeight(30)
        layout.addWidget(length_label, 0, 2)
        layout.addWidget(self.length_display, 1, 2)

        # Segment data
        data_label = QLabel("Data / Current Segment:")
        self.segment_edit = QTextEdit()
        self.segment_edit.setPlaceholderText("目前段資料或手動輸入 HEX")
        self.segment_edit.setFixedHeight(100)
        self.segment_edit.textChanged.connect(self.update_block_length_display)

        layout.addWidget(data_label, 0, 3)
        layout.addWidget(self.segment_edit, 1, 3)

        # Buttons row
        btn_layout = QHBoxLayout()

        self.send_btn = QPushButton("Send with CRC16")
        self.send_btn.clicked.connect(self.send_with_crc)

        self.step_send_btn = QPushButton("Step Send")
        self.step_send_btn.clicked.connect(self.step_send)

        self.auto_send_btn = QPushButton("Auto Send All")
        self.auto_send_btn.clicked.connect(self.auto_send)

        self.stop_auto_btn = QPushButton("Stop")
        self.stop_auto_btn.setEnabled(False)
        self.stop_auto_btn.clicked.connect(self.stop_auto_send)

        self.clear_input_btn = QPushButton("Clear All")
        self.clear_input_btn.clicked.connect(self.clear_input)

        btn_layout.addWidget(self.send_btn)
        btn_layout.addWidget(self.step_send_btn)
        btn_layout.addWidget(self.auto_send_btn)
        btn_layout.addWidget(self.stop_auto_btn)
        btn_layout.addWidget(self.clear_input_btn)

        btn_layout.addStretch()

        self.progress_label = QLabel("")
        btn_layout.addWidget(self.progress_label)

        layout.addLayout(btn_layout, 2, 0, 1, 4)

        self.update_block_length_display()

        return group

    # --------------------- Log Group -----------------------------------
    def _create_log_group(self) -> QGroupBox:
        group = QGroupBox("Communication Log", self)
        vbox = QVBoxLayout(group)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        vbox.addWidget(self.log_edit)

        btn_layout = QHBoxLayout()
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)

        btn_layout.addWidget(self.clear_log_btn)
        btn_layout.addStretch()

        vbox.addLayout(btn_layout)

        return group

    # ------------------------------------------------------------------
    # Connection & Serial
    # ------------------------------------------------------------------
    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        current = self.port_combo.currentText()
        self.port_combo.clear()
        for p in ports:
            self.port_combo.addItem(p.device)

        if current and current in [p.device for p in ports]:
            self.port_combo.setCurrentText(current)
        elif ports:
            self.port_combo.setCurrentIndex(0)

        self.log_message(f"Found {len(ports)} port(s)", "info")

    def connect_serial(self):
        port = self.port_combo.currentText()
        if not port:
            QMessageBox.warning(self, "No Port Selected", "Please select a serial port.")
            return

        try:
            baudrate = int(self.baudrate_combo.currentText())
        except ValueError:
            QMessageBox.warning(self, "Baudrate Error", "Invalid baudrate.")
            return

        databits = int(self.databits_combo.currentText())
        if databits == 7:
            bytesize = serial.SEVENBITS
        else:
            bytesize = serial.EIGHTBITS

        parity_str = self.parity_combo.currentText()[0]
        if parity_str == "N":
            parity = serial.PARITY_NONE
        elif parity_str == "E":
            parity = serial.PARITY_EVEN
        else:
            parity = serial.PARITY_ODD

        stopbits_val = float(self.stopbits_combo.currentText())
        if stopbits_val == 1:
            stopbits = serial.STOPBITS_ONE
        else:
            stopbits = serial.STOPBITS_TWO

        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=1,
            )
            self.is_connected = True

            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.port_combo.setEnabled(False)
            self.baudrate_combo.setEnabled(False)
            self.databits_combo.setEnabled(False)
            self.parity_combo.setEnabled(False)
            self.stopbits_combo.setEnabled(False)
            self.refresh_btn.setEnabled(False)

            self.poll_timer.start(self.polling_interval)

            config_str = f"{port} @ {baudrate} baud, {databits}{parity_str}{stopbits_val}"
            self.log_message(f"Connected to {config_str}", "info")

        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))
            self.log_message(f"Connection failed: {e}", "error")

    def disconnect_serial(self):
        self.is_connected = False
        self.poll_timer.stop()

        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
                self.log_message("Disconnected", "info")
            except Exception as e:
                self.log_message(f"Error closing port: {e}", "error")

        self.serial_port = None

        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.port_combo.setEnabled(True)
        self.baudrate_combo.setEnabled(True)
        self.databits_combo.setEnabled(True)
        self.parity_combo.setEnabled(True)
        self.stopbits_combo.setEnabled(True)
        self.refresh_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Quick Test
    # ------------------------------------------------------------------
    def clear_quick_test(self):
        self.quick_test_input.clear()

    def quick_test_send(self, mode: str):
        if not self.is_connected or not self.serial_port:
            QMessageBox.warning(self, "Not Connected", "Please connect to a serial port first.")
            return

        text = self.quick_test_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty Input", "Please enter test data.")
            return

        try:
            if mode in ("hex", "hex_crc"):
                hex_str = text.replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")
                if not all(c in "0123456789ABCDEFabcdef" for c in hex_str):
                    QMessageBox.critical(self, "Invalid HEX", "Input must contain only HEX characters (0-9, A-F).")
                    return
                if len(hex_str) % 2 != 0:
                    QMessageBox.critical(self, "Invalid HEX", "HEX string must have even number of characters.")
                    return

                data_bytes = bytes.fromhex(hex_str)

                if mode == "hex_crc":
                    crc = CRC16Modbus.calculate(data_bytes)
                    crc_bytes = CRC16Modbus.to_bytes_le(crc)
                    data_bytes = data_bytes + crc_bytes

                self.serial_port.write(data_bytes)
                self.log_message(f"TX: {data_bytes.hex().upper()}", "tx")

            elif mode in ("ascii", "ascii_crc"):
                ascii_bytes = text.encode("ascii")

                if mode == "ascii_crc":
                    crc = CRC16Modbus.calculate(ascii_bytes)
                    crc_bytes = CRC16Modbus.to_bytes_le(crc)
                    ascii_bytes = ascii_bytes + crc_bytes

                self.serial_port.write(ascii_bytes)
                self.log_message(f"TX: {ascii_bytes.hex().upper()} [{text}]", "tx")

        except UnicodeEncodeError:
            QMessageBox.critical(self, "ASCII Error", "Input contains non-ASCII characters.")
        except Exception as e:
            QMessageBox.critical(self, "Send Error", str(e))
            self.log_message(f"Send error: {e}", "error")

    # ------------------------------------------------------------------
    # File loading & segments
    # ------------------------------------------------------------------
    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select HEX Data File",
            "",
            "Text files (*.txt);;HEX files (*.hex);;All files (*.*)",
        )
        if path:
            self.file_path_edit.setText(path)

    def load_and_split_file(self):
        path = self.file_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "No File", "Please select a file first.")
            return

        try:
            chunk_size = int(self.chunk_size_edit.text())
            if chunk_size <= 0:
                raise ValueError("Chunk size must be positive")
        except Exception as e:
            QMessageBox.critical(self, "Invalid Chunk Size", str(e))
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            cleaned = (
                content.replace(" ", "")
                .replace("\t", "")
                .replace("\n", "")
                .replace("\r", "")
            )

            if cleaned and not all(c in "0123456789ABCDEFabcdef" for c in cleaned):
                QMessageBox.critical(self, "Invalid Data", "File contains non-HEX characters.")
                return

            self.file_segments = []
            for i in range(0, len(cleaned), chunk_size):
                seg = cleaned[i : i + chunk_size]
                self.file_segments.append(seg)

            self.current_segment_index = 0

            if self.file_segments:
                self.segment_edit.setPlainText(self.file_segments[0])
                total_segments = len(self.file_segments)
                total_chars = len(cleaned)
                self.file_status_label.setText(
                    f"Loaded: {total_segments} segments, {total_chars} chars total"
                )
                self.progress_label.setText(f"Segment 1 / {total_segments}")
                self.update_block_length_display()
                self.log_message(
                    f"File loaded: {total_segments} segments of {chunk_size} chars each",
                    "info",
                )
            else:
                self.file_status_label.setText("File is empty")

        except FileNotFoundError:
            QMessageBox.critical(self, "File Error", "File not found.")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    # ------------------------------------------------------------------
    # HEX input / send
    # ------------------------------------------------------------------
    def clear_input(self):
        self.prefix_edit.clear()
        self.segment_edit.clear()
        self.current_segment_index = 0
        self.update_block_length_display()
        self.progress_label.clear()

    def update_block_length_display(self):
        # 目前 segment 用來算 length
        segment_text = self.segment_edit.toPlainText().strip()
        segment_clean = (
            segment_text.replace(" ", "")
            .replace("\t", "")
            .replace("\n", "")
            .replace("\r", "")
        )

        if segment_clean and all(c in "0123456789ABCDEFabcdef" for c in segment_clean):
            length_bytes = len(segment_clean) // 2
        else:
            length_bytes = 0

        block_hex = f"{self.current_segment_index:04X}"
        length_hex = f"{length_bytes:04X}"

        self.block_display.setText(block_hex)
        self.length_display.setText(length_hex)

    def send_with_crc(self):
        if not self.is_connected or not self.serial_port:
            QMessageBox.warning(self, "Not Connected", "Please connect to a serial port first.")
            return

        prefix = self.prefix_edit.toPlainText().strip()
        segment = self.segment_edit.toPlainText().strip()

        hex_str = (prefix + segment).replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")
        if not hex_str:
            QMessageBox.warning(self, "Empty Input", "Please enter HEX data to send.")
            return

        if not all(c in "0123456789ABCDEFabcdef" for c in hex_str):
            QMessageBox.critical(self, "Invalid HEX", "Input must contain only HEX characters (0-9, A-F).")
            return

        if len(hex_str) % 2 != 0:
            QMessageBox.critical(self, "Invalid HEX", "HEX string must have an even number of characters.")
            return

        try:
            data_bytes = bytes.fromhex(hex_str)
            crc = CRC16Modbus.calculate(data_bytes)
            crc_bytes = CRC16Modbus.to_bytes_le(crc)
            final_data = data_bytes + crc_bytes

            self.serial_port.write(final_data)
            self.log_message(f"TX: {final_data.hex().upper()}", "tx")

        except Exception as e:
            QMessageBox.critical(self, "Send Error", str(e))
            self.log_message(f"Send error: {e}", "error")

    # --------------------- Step / Auto send ----------------------------
    def step_send(self):
        if not self.file_segments:
            QMessageBox.information(self, "No Segments", "Please load a file first.")
            return
        if not self.is_connected or not self.serial_port:
            QMessageBox.warning(self, "Not Connected", "Please connect to a serial port first.")
            return
        if self.current_segment_index >= len(self.file_segments):
            QMessageBox.information(self, "Complete", "All segments have been sent.")
            return

        success = self.send_current_segment()
        if success:
            self.waiting_for_reply = True
            self.reply_received = False
            self.validation_failed = False
            self.step_send_btn.setEnabled(False)

            QTimer.singleShot(2000, lambda: self.check_reply_timeout(is_step=True))

    def auto_send(self):
        if not self.file_segments:
            QMessageBox.information(self, "No Segments", "Please load a file first.")
            return
        if not self.is_connected or not self.serial_port:
            QMessageBox.warning(self, "Not Connected", "Please connect to a serial port first.")
            return
        if self.current_segment_index >= len(self.file_segments):
            QMessageBox.information(self, "Complete", "All segments have already been sent.")
            return

        self.auto_send_running = True
        self.auto_send_btn.setEnabled(False)
        self.step_send_btn.setEnabled(False)
        self.stop_auto_btn.setEnabled(True)
        self.log_message("Auto send started", "info")
        self.send_next_in_auto_mode()

    def send_next_in_auto_mode(self):
        if not self.auto_send_running:
            return

        if self.current_segment_index >= len(self.file_segments):
            self.auto_send_complete()
            return

        success = self.send_current_segment()
        if success:
            self.waiting_for_reply = True
            self.reply_received = False
            self.validation_failed = False
            QTimer.singleShot(2000, lambda: self.check_reply_timeout(is_step=False))
        else:
            self.stop_auto_send()

    def send_current_segment(self) -> bool:
        try:
            prefix = self.prefix_edit.toPlainText().strip()
            segment = self.file_segments[self.current_segment_index]

            prefix_clean = (
                prefix.replace(" ", "")
                .replace("\t", "")
                .replace("\n", "")
                .replace("\r", "")
            )

            if prefix_clean:
                if not all(c in "0123456789ABCDEFabcdef" for c in prefix_clean):
                    QMessageBox.critical(self, "Invalid HEX", "Prefix contains non-HEX characters.")
                    return False
                if len(prefix_clean) % 2 != 0:
                    QMessageBox.critical(self, "Invalid HEX", "Prefix has odd length.")
                    return False
                prefix_bytes = bytes.fromhex(prefix_clean)
            else:
                prefix_bytes = b""

            if not all(c in "0123456789ABCDEFabcdef" for c in segment):
                QMessageBox.critical(self, "Invalid HEX", "Segment contains non-HEX characters.")
                return False
            if len(segment) % 2 != 0:
                QMessageBox.critical(self, "Invalid HEX", "Segment has odd length.")
                return False

            data_bytes = bytes.fromhex(segment)

            block_number = self.current_segment_index
            block_bytes = block_number.to_bytes(2, byteorder="big")

            length_bytes = len(data_bytes).to_bytes(2, byteorder="big")

            packet_without_crc = prefix_bytes + block_bytes + length_bytes + data_bytes

            crc = CRC16Modbus.calculate(packet_without_crc)
            crc_bytes = CRC16Modbus.to_bytes_le(crc)

            final_packet = packet_without_crc + crc_bytes

            self.serial_port.write(final_packet)
            self.log_message(f"TX: {final_packet.hex().upper()}", "tx")

            return True

        except Exception as e:
            self.log_message(f"Send error: {e}", "error")
            return False

    def check_reply_timeout(self, is_step: bool):
        if self.reply_received:
            # 成功收到 / 驗證 OK
            self.current_segment_index += 1

            if self.current_segment_index < len(self.file_segments):
                self.segment_edit.setPlainText(self.file_segments[self.current_segment_index])
                total = len(self.file_segments)
                self.progress_label.setText(
                    f"Segment {self.current_segment_index + 1} / {total}"
                )
                self.update_block_length_display()

                if not is_step:
                    QTimer.singleShot(100, self.send_next_in_auto_mode)
                else:
                    self.step_send_btn.setEnabled(True)
            else:
                total = len(self.file_segments)
                self.progress_label.setText(f"Complete: {total} / {total}")
                if not is_step:
                    self.auto_send_complete()
                else:
                    self.log_message("All segments sent successfully", "info")
                    self.step_send_btn.setEnabled(True)

        elif self.validation_failed:
            # 驗證失敗，stop auto 已在 display_received_data 處理
            if is_step:
                self.step_send_btn.setEnabled(True)

        else:
            # timeout
            self.log_message(
                f"Timeout: No response for block {self.current_segment_index + 1}",
                "error",
            )
            if not is_step:
                self.stop_auto_send()
            else:
                self.step_send_btn.setEnabled(True)

        self.waiting_for_reply = False
        self.validation_failed = False

    def auto_send_complete(self):
        self.auto_send_running = False
        self.auto_send_btn.setEnabled(True)
        self.step_send_btn.setEnabled(True)
        self.stop_auto_btn.setEnabled(False)
        self.log_message("Auto send completed successfully", "info")

    def stop_auto_send(self):
        self.auto_send_running = False
        self.waiting_for_reply = False
        self.reply_received = False
        self.validation_failed = False
        self.auto_send_btn.setEnabled(True)
        self.step_send_btn.setEnabled(True)
        self.stop_auto_btn.setEnabled(False)
        self.log_message("Auto send stopped", "info")

    # ------------------------------------------------------------------
    # Serial polling / RX / Validation
    # ------------------------------------------------------------------
    def poll_serial_data(self):
        if not self.is_connected or not self.serial_port:
            return

        try:
            if self.serial_port.in_waiting > 0:
                data = self.serial_port.read(self.serial_port.in_waiting)
                if data:
                    self.display_received_data(data)
        except Exception as e:
            self.log_message(f"Read error: {e}", "error")

    def display_received_data(self, data: bytes):
        hex_str = data.hex().upper()
        self.log_message(f"RX: {hex_str}", "rx")

        if self.waiting_for_reply:
            valid, error_msg = self.validate_response(data)

            if valid:
                self.reply_received = True
                self.validation_failed = False
            else:
                self.reply_received = False
                self.validation_failed = True
                self.log_message(f"Response error: {error_msg}", "error")
                if self.auto_send_running:
                    self.stop_auto_send()

    def validate_response(self, data: bytes):
        """
        Response format: [Slave ID][Function Code][Block Number][State][CRC]
        Total: 7 bytes
        """
        if len(data) < 7:
            return False, f"Response too short: {len(data)} bytes (expected 7)"

        slave_id = data[0]
        function_code = data[1]
        block_number_bytes = data[2:4]
        state = data[4]
        received_crc_bytes = data[5:7]

        data_without_crc = data[0:5]
        calculated_crc = CRC16Modbus.calculate(data_without_crc)
        calculated_crc_bytes = CRC16Modbus.to_bytes_le(calculated_crc)

        if received_crc_bytes != calculated_crc_bytes:
            r_crc = received_crc_bytes.hex().upper()
            c_crc = calculated_crc_bytes.hex().upper()
            return False, f"CRC mismatch (received={r_crc}, calculated={c_crc})"

        if state != 0xAC:
            return False, f"State != 0xAC (received State=0x{state:02X})"

        return True, ""

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def clear_log(self):
        self.log_edit.clear()

    def log_message(self, message: str, tag: str = "info"):
        timestamp = time.strftime("%H:%M:%S")

        if message.startswith("TX: ") or message.startswith("RX: "):
            direction = message[:2]
            content = message[4:]
            line = f"[{timestamp}][{direction}]: {content}"
        else:
            line = f"[{timestamp}] {message}"

        self.log_edit.appendPlainText(line)
        self.log_edit.moveCursor(self.log_edit.textCursor().End)

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        # 停 auto send / timer / serial
        if self.auto_send_running:
            self.stop_auto_send()

        self.poll_timer.stop()

        if self.is_connected:
            self.disconnect_serial()

        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = RS485SerialToolWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
