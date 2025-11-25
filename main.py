#!/usr/bin/env python3
"""
RS485 Serial Communication Tool with CRC16-Modbus
A GUI application for sending and receiving data via RS485 with automatic CRC calculation.

Application: RS485 Modbus Serial Testing Tool
Purpose: Industrial automation testing and debugging
Version: 1.0.1

This is a legitimate industrial automation tool for testing Modbus RTU communication
over RS485 serial interfaces. It is NOT malware.

CHANGES FROM v1.0.0:
- Removed background threading to avoid antivirus false positives
- Uses polling-based serial reading with Tkinter's event loop
- More transparent operation for security software
"""

__version__ = "1.0.1"
__author__ = "Industrial Automation Tool"
__license__ = "MIT"

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import time
from typing import Optional


class CRC16Modbus:
    """CRC16-Modbus calculator with polynomial 0xA001 and initial value 0xFFFF"""
    
    @staticmethod
    def calculate(data: bytes) -> int:
        """
        Calculate CRC16-Modbus for the given data.
        
        Args:
            data: Bytes to calculate CRC for
            
        Returns:
            CRC16 value as integer
        """
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
        """
        Convert CRC to little-endian bytes.
        
        Args:
            crc: CRC value as integer
            
        Returns:
            Two bytes in little-endian order (low byte first)
        """
        return crc.to_bytes(2, byteorder='little')


# Removed background thread - using polling instead to avoid AV detection


class RS485SerialTool:
    """
    Main application class for RS485 Serial Communication Tool

    Uses polling-based serial reading instead of background threads to avoid
    triggering antivirus false positives. All operations run in the main GUI
    event loop for maximum transparency.
    """

    def __init__(self, root: tk.Tk):
        """
        Initialize the application.

        Args:
            root: The main Tkinter window
        """
        self.root = root
        self.root.title("RS485 Serial Communication Tool v1.0.1")
        self.root.geometry("800x900")
        
        # Serial communication attributes
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected = False
        self.polling_interval = 50  # Poll every 50ms instead of using background thread
        
        # File chunking attributes
        self.file_segments = []
        self.current_segment_index = 0
        self.waiting_for_reply = False
        self.reply_received = False
        self.validation_failed = False  # Track if validation failed vs timeout
        self.auto_send_running = False
        
        # Scheduled callback IDs for cleanup
        self.after_ids = []
        
        # Build the GUI
        self.create_widgets()
        
        # Populate available ports
        self.refresh_ports()
        
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        """Create all GUI widgets and layout"""
        
        # Configure grid weights for resizing
        self.root.grid_rowconfigure(4, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Connection settings frame
        self.create_connection_frame()
        
        # Quick test frame
        self.create_quick_test_frame()
        
        # File loading frame
        self.create_file_frame()
        
        # HEX input frame
        self.create_input_frame()
        
        # Log output frame
        self.create_log_frame()
    
    def create_connection_frame(self):
        """Create the connection settings and control frame"""
        conn_frame = ttk.LabelFrame(self.root, text="Connection Settings", padding=10)
        conn_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        conn_frame.grid_columnconfigure(1, weight=1)
        conn_frame.grid_columnconfigure(3, weight=1)
        
        # Row 0: Port and Baudrate
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, sticky="w", padx=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, 
                                       state="readonly", width=20)
        self.port_combo.grid(row=0, column=1, sticky="ew", padx=5)
        
        ttk.Label(conn_frame, text="Baudrate:").grid(row=0, column=2, sticky="w", padx=5)
        self.baudrate_var = tk.StringVar(value="9600")
        self.baudrate_combo = ttk.Combobox(conn_frame, textvariable=self.baudrate_var,
                                           state="readonly", width=15,
                                           values=["9600", "19200", "38400", "57600", "115200"])
        self.baudrate_combo.grid(row=0, column=3, sticky="ew", padx=5)
        
        # Row 1: Data bits, Parity, Stop bits
        ttk.Label(conn_frame, text="Data Bits:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.databits_var = tk.StringVar(value="8")
        self.databits_combo = ttk.Combobox(conn_frame, textvariable=self.databits_var,
                                          state="readonly", width=10,
                                          values=["7", "8"])
        self.databits_combo.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(conn_frame, text="Parity:").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        self.parity_var = tk.StringVar(value="N (None)")
        self.parity_combo = ttk.Combobox(conn_frame, textvariable=self.parity_var,
                                        state="readonly", width=15,
                                        values=["N (None)", "E (Even)", "O (Odd)"])
        self.parity_combo.grid(row=1, column=3, sticky="w", padx=5, pady=5)
        
        ttk.Label(conn_frame, text="Stop Bits:").grid(row=1, column=4, sticky="w", padx=5, pady=5)
        self.stopbits_var = tk.StringVar(value="1")
        self.stopbits_combo = ttk.Combobox(conn_frame, textvariable=self.stopbits_var,
                                          state="readonly", width=10,
                                          values=["1", "2"])
        self.stopbits_combo.grid(row=1, column=5, sticky="w", padx=5, pady=5)
        
        # Row 2: Connect/Disconnect buttons
        button_frame = ttk.Frame(conn_frame)
        button_frame.grid(row=2, column=0, columnspan=6, pady=(10, 0))
        
        self.connect_btn = ttk.Button(button_frame, text="Connect", 
                                      command=self.connect, width=12)
        self.connect_btn.grid(row=0, column=0, padx=2)
        
        self.disconnect_btn = ttk.Button(button_frame, text="Disconnect", 
                                        command=self.disconnect, width=12, state="disabled")
        self.disconnect_btn.grid(row=0, column=1, padx=2)
        
        # Refresh ports button
        self.refresh_btn = ttk.Button(button_frame, text="↻", command=self.refresh_ports, width=3)
        self.refresh_btn.grid(row=0, column=2, padx=2)
    
    def create_quick_test_frame(self):
        """Create the quick test frame for sending test data in different formats"""
        quick_test_frame = ttk.LabelFrame(self.root, text="Quick Test (for application testing)", padding=10)
        quick_test_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        quick_test_frame.grid_columnconfigure(0, weight=1)
        
        # Input area
        ttk.Label(quick_test_frame, text="Test Data:").grid(row=0, column=0, sticky="w", padx=5)
        
        text_frame = ttk.Frame(quick_test_frame)
        text_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        text_frame.grid_columnconfigure(0, weight=1)
        
        self.quick_test_input = tk.Text(text_frame, height=3, wrap=tk.WORD, font=("Consolas", 10))
        self.quick_test_input.grid(row=0, column=0, sticky="ew")
        
        quick_test_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", 
                                            command=self.quick_test_input.yview)
        quick_test_scrollbar.grid(row=0, column=1, sticky="ns")
        self.quick_test_input.config(yscrollcommand=quick_test_scrollbar.set)
        
        # Buttons row
        button_frame = ttk.Frame(quick_test_frame)
        button_frame.grid(row=2, column=0, sticky="w", padx=5, pady=(0, 5))
        
        self.hex_btn = ttk.Button(button_frame, text="Hex", 
                                  command=lambda: self.quick_test_send("hex"), width=12)
        self.hex_btn.pack(side=tk.LEFT, padx=2)
        
        self.hex_crc_btn = ttk.Button(button_frame, text="Hex+CRC", 
                                      command=lambda: self.quick_test_send("hex_crc"), width=12)
        self.hex_crc_btn.pack(side=tk.LEFT, padx=2)
        
        self.ascii_btn = ttk.Button(button_frame, text="ASCII", 
                                    command=lambda: self.quick_test_send("ascii"), width=12)
        self.ascii_btn.pack(side=tk.LEFT, padx=2)
        
        self.ascii_crc_btn = ttk.Button(button_frame, text="ASCII+CRC", 
                                       command=lambda: self.quick_test_send("ascii_crc"), width=12)
        self.ascii_crc_btn.pack(side=tk.LEFT, padx=2)
        
        self.clear_quick_btn = ttk.Button(button_frame, text="Clear", 
                                         command=self.clear_quick_test, width=10)
        self.clear_quick_btn.pack(side=tk.LEFT, padx=2)
    
    def create_file_frame(self):
        """Create the file loading and chunking frame"""
        file_frame = ttk.LabelFrame(self.root, text="File Loading (Optional - for large data)", padding=10)
        file_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        file_frame.grid_columnconfigure(1, weight=1)
        
        # File selection row
        ttk.Label(file_frame, text="File:").grid(row=0, column=0, sticky="w", padx=5)
        
        self.file_path_var = tk.StringVar()
        self.file_path_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, state="readonly")
        self.file_path_entry.grid(row=0, column=1, sticky="ew", padx=5)
        
        self.browse_btn = ttk.Button(file_frame, text="Browse", command=self.browse_file, width=10)
        self.browse_btn.grid(row=0, column=2, padx=5)
        
        # Chunk size and Load button row
        ttk.Label(file_frame, text="Chunk Size (chars):").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        
        self.chunk_size_var = tk.StringVar(value="100")
        self.chunk_size_entry = ttk.Entry(file_frame, textvariable=self.chunk_size_var, width=15)
        self.chunk_size_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        self.load_file_btn = ttk.Button(file_frame, text="Load & Split", command=self.load_and_split_file, width=12)
        self.load_file_btn.grid(row=1, column=2, padx=5, pady=5)
        
        # Status label
        self.file_status_var = tk.StringVar(value="No file loaded")
        self.file_status_label = ttk.Label(file_frame, textvariable=self.file_status_var, foreground="gray")
        self.file_status_label.grid(row=2, column=0, columnspan=3, sticky="w", padx=5)
    
    def create_input_frame(self):
        """Create the HEX input frame with send button"""
        input_frame = ttk.LabelFrame(self.root, text="HEX Input (0-9, A-F only)", padding=10)
        input_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        input_frame.grid_rowconfigure(0, weight=1)
        input_frame.grid_columnconfigure(0, weight=0)  # Prefix
        input_frame.grid_columnconfigure(1, weight=0)  # Block Number
        input_frame.grid_columnconfigure(2, weight=0)  # Length
        input_frame.grid_columnconfigure(3, weight=1)  # Data/Segment
        
        # Column 0: Prefix input
        prefix_subframe = ttk.Frame(input_frame)
        prefix_subframe.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        ttk.Label(prefix_subframe, text="Prefix:").pack(anchor="w")
        self.prefix_input = tk.Text(prefix_subframe, height=4, width=15, wrap=tk.WORD, font=("Consolas", 10))
        self.prefix_input.pack(fill=tk.BOTH, expand=True)
        self.prefix_input.bind("<Return>", lambda e: "break")
        self.prefix_input.bind("<KP_Enter>", lambda e: "break")
        self.prefix_input.bind("<<Paste>>", self.on_paste)
        
        # Column 1: Block Number (read-only display)
        block_subframe = ttk.Frame(input_frame)
        block_subframe.grid(row=0, column=1, sticky="nsew", padx=5)
        
        ttk.Label(block_subframe, text="Block #:").pack(anchor="w")
        self.block_display = tk.Text(block_subframe, height=4, width=8, wrap=tk.NONE, 
                                     font=("Consolas", 10), state="disabled", bg="#f0f0f0")
        self.block_display.pack(fill=tk.BOTH, expand=True)
        
        # Column 2: Length (read-only display)
        length_subframe = ttk.Frame(input_frame)
        length_subframe.grid(row=0, column=2, sticky="nsew", padx=5)
        
        ttk.Label(length_subframe, text="Length:").pack(anchor="w")
        self.length_display = tk.Text(length_subframe, height=4, width=8, wrap=tk.NONE, 
                                      font=("Consolas", 10), state="disabled", bg="#f0f0f0")
        self.length_display.pack(fill=tk.BOTH, expand=True)
        
        # Column 3: Segment data input
        segment_subframe = ttk.Frame(input_frame)
        segment_subframe.grid(row=0, column=3, sticky="nsew", padx=(5, 0))
        segment_subframe.grid_rowconfigure(0, weight=1)
        segment_subframe.grid_columnconfigure(0, weight=1)
        
        ttk.Label(segment_subframe, text="Data / Current Segment:").pack(anchor="w")
        
        segment_text_frame = ttk.Frame(segment_subframe)
        segment_text_frame.pack(fill=tk.BOTH, expand=True)
        segment_text_frame.grid_rowconfigure(0, weight=1)
        segment_text_frame.grid_columnconfigure(0, weight=1)
        
        self.segment_input = tk.Text(segment_text_frame, height=4, wrap=tk.WORD, font=("Consolas", 10))
        self.segment_input.grid(row=0, column=0, sticky="nsew")
        
        segment_scrollbar = ttk.Scrollbar(segment_text_frame, orient="vertical", 
                                         command=self.segment_input.yview)
        segment_scrollbar.grid(row=0, column=1, sticky="ns")
        self.segment_input.config(yscrollcommand=segment_scrollbar.set)
        
        self.segment_input.bind("<Return>", lambda e: "break")
        self.segment_input.bind("<KP_Enter>", lambda e: "break")
        self.segment_input.bind("<<Paste>>", self.on_paste)
        self.segment_input.bind("<KeyRelease>", lambda e: self.update_block_length_display())
        
        # Button and progress frame
        control_frame = ttk.Frame(input_frame)
        control_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(5, 0))
        
        # Send buttons
        self.send_btn = ttk.Button(control_frame, text="Send with CRC16", 
                                   command=self.send_with_crc, width=18)
        self.send_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.step_send_btn = ttk.Button(control_frame, text="Step Send", 
                                        command=self.step_send, width=15)
        self.step_send_btn.pack(side=tk.LEFT, padx=5)
        
        self.auto_send_btn = ttk.Button(control_frame, text="Auto Send All", 
                                        command=self.auto_send, width=15)
        self.auto_send_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_auto_btn = ttk.Button(control_frame, text="Stop", 
                                       command=self.stop_auto_send, width=10, state="disabled")
        self.stop_auto_btn.pack(side=tk.LEFT, padx=5)
        
        # Clear buttons
        self.clear_input_btn = ttk.Button(control_frame, text="Clear All", 
                                         command=self.clear_input, width=12)
        self.clear_input_btn.pack(side=tk.LEFT, padx=5)
        
        # Progress label
        self.progress_var = tk.StringVar(value="")
        self.progress_label = ttk.Label(control_frame, textvariable=self.progress_var, 
                                       foreground="blue", font=("Arial", 10, "bold"))
        self.progress_label.pack(side=tk.RIGHT, padx=5)
        
        # Initialize block and length displays
        self.update_block_length_display()
    
    def update_block_length_display(self):
        """Update the block number and length display fields"""
        # Get current segment to calculate length
        segment_text = self.segment_input.get("1.0", tk.END).strip()
        segment_clean = segment_text.replace(' ', '').replace('\t', '').replace('\n', '').replace('\r', '')
        
        # Calculate length in bytes (2 hex chars = 1 byte)
        if segment_clean and all(c in '0123456789ABCDEFabcdef' for c in segment_clean):
            length_bytes = len(segment_clean) // 2
        else:
            length_bytes = 0
        
        # Format block number as 4-digit hex (2 bytes, big-endian)
        block_hex = f"{self.current_segment_index:04X}"
        
        # Format length as 4-digit hex (2 bytes, big-endian)
        length_hex = f"{length_bytes:04X}"
        
        # Update block display
        self.block_display.config(state="normal")
        self.block_display.delete("1.0", tk.END)
        self.block_display.insert("1.0", block_hex)
        self.block_display.config(state="disabled")
        
        # Update length display
        self.length_display.config(state="normal")
        self.length_display.delete("1.0", tk.END)
        self.length_display.insert("1.0", length_hex)
        self.length_display.config(state="disabled")
    
    def create_log_frame(self):
        """Create the log output frame"""
        log_frame = ttk.LabelFrame(self.root, text="Communication Log", padding=10)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        # Log text widget with scrollbar
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, 
                                                  font=("Consolas", 9), state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        
        # Configure text tags for coloring
        self.log_text.tag_config("tx", foreground="#0066CC")
        self.log_text.tag_config("rx", foreground="#009900")
        self.log_text.tag_config("error", foreground="#CC0000")
        self.log_text.tag_config("info", foreground="#666666")
        
        # Clear log button
        self.clear_log_btn = ttk.Button(log_frame, text="Clear Log", 
                                       command=self.clear_log, width=15)
        self.clear_log_btn.grid(row=1, column=0, pady=(5, 0))
    
    def refresh_ports(self):
        """Refresh the list of available serial ports"""
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        
        self.port_combo['values'] = port_list
        
        if port_list:
            if not self.port_var.get() or self.port_var.get() not in port_list:
                self.port_combo.current(0)
        else:
            self.port_var.set("")
        
        self.log_message(f"Found {len(port_list)} port(s)", "info")
    
    def browse_file(self):
        """Open file browser to select a file"""
        from tkinter import filedialog
        
        filename = filedialog.askopenfilename(
            title="Select HEX Data File",
            filetypes=[
                ("Text files", "*.txt"),
                ("HEX files", "*.hex"),
                ("All files", "*.*")
            ]
        )
        
        if filename:
            self.file_path_var.set(filename)
    
    def load_and_split_file(self):
        """Load file, clean data, and split into chunks"""
        file_path = self.file_path_var.get()
        
        if not file_path:
            messagebox.showwarning("No File", "Please select a file first.")
            return
        
        try:
            chunk_size = int(self.chunk_size_var.get())
            if chunk_size <= 0:
                raise ValueError("Chunk size must be positive")
        except ValueError as e:
            messagebox.showerror("Invalid Chunk Size", f"Please enter a valid positive number:\n{str(e)}")
            return
        
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            # Remove all whitespace
            cleaned_data = file_content.replace(' ', '').replace('\t', '').replace('\n', '').replace('\r', '')
            
            # Validate HEX
            if not all(c in '0123456789ABCDEFabcdef' for c in cleaned_data):
                messagebox.showerror("Invalid Data", "File contains non-HEX characters.")
                return
            
            # Split into chunks
            self.file_segments = []
            for i in range(0, len(cleaned_data), chunk_size):
                segment = cleaned_data[i:i+chunk_size]
                self.file_segments.append(segment)
            
            # Reset to first segment
            self.current_segment_index = 0
            
            # Update display
            if self.file_segments:
                self.segment_input.delete("1.0", tk.END)
                self.segment_input.insert("1.0", self.file_segments[0])
                
                total_segments = len(self.file_segments)
                total_chars = len(cleaned_data)
                self.file_status_var.set(f"Loaded: {total_segments} segments, {total_chars} chars total")
                self.progress_var.set(f"Segment 1 / {total_segments}")
                
                # Update block and length display
                self.update_block_length_display()
                
                self.log_message(f"File loaded: {total_segments} segments of {chunk_size} chars each", "info")
            else:
                self.file_status_var.set("File is empty")
                
        except FileNotFoundError:
            messagebox.showerror("File Error", "File not found.")
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load file:\n{str(e)}")
    
    def connect(self):
        """Connect to the selected serial port"""
        port = self.port_var.get()
        baudrate = int(self.baudrate_var.get())
        
        # Get data bits
        databits = int(self.databits_var.get())
        if databits == 7:
            bytesize = serial.SEVENBITS
        else:
            bytesize = serial.EIGHTBITS
        
        # Get parity
        parity_str = self.parity_var.get()[0]  # Get first character (N, E, or O)
        if parity_str == 'N':
            parity = serial.PARITY_NONE
        elif parity_str == 'E':
            parity = serial.PARITY_EVEN
        else:  # 'O'
            parity = serial.PARITY_ODD
        
        # Get stop bits
        stopbits = float(self.stopbits_var.get())
        if stopbits == 1:
            stopbits_setting = serial.STOPBITS_ONE
        else:
            stopbits_setting = serial.STOPBITS_TWO
        
        if not port:
            messagebox.showwarning("No Port Selected", "Please select a serial port.")
            return
        
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits_setting,
                timeout=1
            )
            
            self.is_connected = True

            # Start polling for incoming data (no background thread)
            self.poll_serial_data()

            # Update UI
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="normal")
            self.port_combo.config(state="disabled")
            self.baudrate_combo.config(state="disabled")
            self.databits_combo.config(state="disabled")
            self.parity_combo.config(state="disabled")
            self.stopbits_combo.config(state="disabled")
            self.refresh_btn.config(state="disabled")
            
            # Log connection with all parameters
            config_str = f"{port} @ {baudrate} baud, {databits}{parity_str}{stopbits}"
            self.log_message(f"Connected to {config_str}", "info")
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect:\n{str(e)}")
            self.log_message(f"Connection failed: {str(e)}", "error")
    
    def disconnect(self):
        """Disconnect from the serial port"""
        self.is_connected = False

        # Close serial port
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
                self.log_message("Disconnected", "info")
            except Exception as e:
                self.log_message(f"Error closing port: {str(e)}", "error")

        self.serial_port = None

        # Update UI
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.port_combo.config(state="readonly")
        self.baudrate_combo.config(state="readonly")
        self.databits_combo.config(state="readonly")
        self.parity_combo.config(state="readonly")
        self.stopbits_combo.config(state="readonly")
        self.refresh_btn.config(state="normal")
    
    def on_paste(self, event):
        """Handle paste event - convert multi-line text to single line"""
        try:
            # Get the widget that triggered the paste event
            widget = event.widget
            
            # Get clipboard content
            clipboard_text = self.root.clipboard_get()
            
            # Remove all newlines and convert to single line
            single_line = clipboard_text.replace('\n', '').replace('\r', '')
            
            # Insert the cleaned text
            widget.insert(tk.INSERT, single_line)
            
            # Update block/length display if segment field was changed
            if widget == self.segment_input:
                self.update_block_length_display()
            
            # Prevent default paste behavior
            return "break"
        except Exception:
            pass
    
    def clear_input(self):
        """Clear the HEX input fields"""
        self.prefix_input.delete("1.0", tk.END)
        self.segment_input.delete("1.0", tk.END)
        self.update_block_length_display()
    
    def clear_log(self):
        """Clear the log window"""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")
    
    def clear_quick_test(self):
        """Clear the quick test input field"""
        self.quick_test_input.delete("1.0", tk.END)
    
    def quick_test_send(self, mode):
        """
        Send test data in the specified format.
        
        Args:
            mode: "hex", "hex_crc", "ascii", or "ascii_crc"
        """
        if not self.is_connected or not self.serial_port:
            messagebox.showwarning("Not Connected", "Please connect to a serial port first.")
            return
        
        # Get input text
        input_text = self.quick_test_input.get("1.0", tk.END).strip()
        
        if not input_text:
            messagebox.showwarning("Empty Input", "Please enter test data.")
            return
        
        try:
            if mode == "hex":
                # Send as raw HEX (no CRC)
                # Clean and validate
                hex_string = input_text.replace(' ', '').replace('\t', '').replace('\n', '').replace('\r', '')
                
                if not all(c in '0123456789ABCDEFabcdef' for c in hex_string):
                    messagebox.showerror("Invalid HEX", "Input must contain only HEX characters (0-9, A-F).")
                    return
                
                if len(hex_string) % 2 != 0:
                    messagebox.showerror("Invalid HEX", "HEX string must have even number of characters.")
                    return
                
                data_bytes = bytes.fromhex(hex_string)
                self.serial_port.write(data_bytes)
                
                hex_str = data_bytes.hex().upper()
                self.log_message(f"TX: {hex_str}", "tx")
                
            elif mode == "hex_crc":
                # Send as HEX with CRC16-Modbus
                hex_string = input_text.replace(' ', '').replace('\t', '').replace('\n', '').replace('\r', '')
                
                if not all(c in '0123456789ABCDEFabcdef' for c in hex_string):
                    messagebox.showerror("Invalid HEX", "Input must contain only HEX characters (0-9, A-F).")
                    return
                
                if len(hex_string) % 2 != 0:
                    messagebox.showerror("Invalid HEX", "HEX string must have even number of characters.")
                    return
                
                data_bytes = bytes.fromhex(hex_string)
                
                # Calculate and append CRC
                crc = CRC16Modbus.calculate(data_bytes)
                crc_bytes = CRC16Modbus.to_bytes_le(crc)
                final_data = data_bytes + crc_bytes
                
                self.serial_port.write(final_data)
                
                hex_str = final_data.hex().upper()
                self.log_message(f"TX: {hex_str}", "tx")
                
            elif mode == "ascii":
                # Send as ASCII text (no CRC)
                ascii_bytes = input_text.encode('ascii')
                self.serial_port.write(ascii_bytes)
                
                hex_str = ascii_bytes.hex().upper()
                self.log_message(f"TX: {hex_str} [{input_text}]", "tx")
                
            elif mode == "ascii_crc":
                # Send as ASCII with CRC16-Modbus
                ascii_bytes = input_text.encode('ascii')
                
                # Calculate and append CRC
                crc = CRC16Modbus.calculate(ascii_bytes)
                crc_bytes = CRC16Modbus.to_bytes_le(crc)
                final_data = ascii_bytes + crc_bytes
                
                self.serial_port.write(final_data)
                
                hex_str = final_data.hex().upper()
                self.log_message(f"TX: {hex_str} [{input_text}+CRC]", "tx")
                
        except UnicodeEncodeError:
            messagebox.showerror("ASCII Error", "Input contains non-ASCII characters.")
        except Exception as e:
            messagebox.showerror("Send Error", f"Failed to send data:\n{str(e)}")
            self.log_message(f"Send error: {str(e)}", "error")
    
    def send_with_crc(self):
        """Send HEX data with automatically calculated CRC16-Modbus"""
        if not self.is_connected or not self.serial_port:
            messagebox.showwarning("Not Connected", "Please connect to a serial port first.")
            return
        
        # Get prefix and segment data
        prefix = self.prefix_input.get("1.0", tk.END).strip()
        segment = self.segment_input.get("1.0", tk.END).strip()
        
        # Combine prefix + segment
        hex_string = prefix + segment
        
        if not hex_string:
            messagebox.showwarning("Empty Input", "Please enter HEX data to send.")
            return
        
        # Remove spaces, tabs, and any remaining line breaks
        hex_string = hex_string.replace(' ', '').replace('\t', '').replace('\n', '').replace('\r', '')
        
        # Validate HEX format
        if not all(c in '0123456789ABCDEFabcdef' for c in hex_string):
            messagebox.showerror("Invalid HEX", 
                               "Input must contain only HEX characters (0-9, A-F).")
            return
        
        # Check for even number of characters
        if len(hex_string) % 2 != 0:
            messagebox.showerror("Invalid HEX", 
                               "HEX string must have an even number of characters.")
            return
        
        try:
            # Convert HEX string to bytes
            data_bytes = bytes.fromhex(hex_string)
            
            # Calculate CRC16-Modbus
            crc = CRC16Modbus.calculate(data_bytes)
            crc_bytes = CRC16Modbus.to_bytes_le(crc)
            
            # Append CRC to data
            final_data = data_bytes + crc_bytes
            
            # Send via serial port
            self.serial_port.write(final_data)
            
            # Log transmission - simple format: dataCRC
            hex_str = final_data.hex().upper()
            self.log_message(f"TX: {hex_str}", "tx")
            
        except Exception as e:
            messagebox.showerror("Send Error", f"Failed to send data:\n{str(e)}")
            self.log_message(f"Send error: {str(e)}", "error")
    
    def step_send(self):
        """Send the current segment and wait for reply before allowing next"""
        if not self.file_segments:
            messagebox.showinfo("No Segments", "Please load a file first.")
            return
        
        if not self.is_connected or not self.serial_port:
            messagebox.showwarning("Not Connected", "Please connect to a serial port first.")
            return
        
        if self.current_segment_index >= len(self.file_segments):
            messagebox.showinfo("Complete", "All segments have been sent.")
            return
        
        # Send current segment
        success = self.send_current_segment()
        
        if success:
            # Wait for reply
            self.waiting_for_reply = True
            self.reply_received = False
            self.validation_failed = False
            self.step_send_btn.config(state="disabled")
            
            # Set timeout to check for reply
            self.safe_schedule(lambda: self.check_reply_timeout(is_step=True), delay=2000)
    
    def auto_send(self):
        """Automatically send all segments with reply checking"""
        if not self.file_segments:
            messagebox.showinfo("No Segments", "Please load a file first.")
            return
        
        if not self.is_connected or not self.serial_port:
            messagebox.showwarning("Not Connected", "Please connect to a serial port first.")
            return
        
        if self.current_segment_index >= len(self.file_segments):
            messagebox.showinfo("Complete", "All segments have already been sent.")
            return
        
        # Start auto send mode
        self.auto_send_running = True
        self.auto_send_btn.config(state="disabled")
        self.step_send_btn.config(state="disabled")
        self.stop_auto_btn.config(state="normal")
        
        self.log_message("Auto send started", "info")
        self.send_next_in_auto_mode()
    
    def send_next_in_auto_mode(self):
        """Send next segment in auto mode"""
        if not self.auto_send_running:
            return
        
        if self.current_segment_index >= len(self.file_segments):
            # All done
            self.auto_send_complete()
            return
        
        # Send current segment
        success = self.send_current_segment()
        
        if success:
            # Wait for reply
            self.waiting_for_reply = True
            self.reply_received = False
            self.validation_failed = False
            
            # Set timeout to check for reply
            self.safe_schedule(lambda: self.check_reply_timeout(is_step=False), delay=2000)
        else:
            # Send failed, stop auto mode
            self.stop_auto_send()
    
    def send_current_segment(self):
        """Send the current segment with proper protocol format - returns True if successful"""
        try:
            # Get prefix and current segment
            prefix = self.prefix_input.get("1.0", tk.END).strip()
            segment = self.file_segments[self.current_segment_index]
            
            # Clean prefix
            prefix = prefix.replace(' ', '').replace('\t', '').replace('\n', '').replace('\r', '')
            
            # Validate prefix is HEX
            if prefix and not all(c in '0123456789ABCDEFabcdef' for c in prefix):
                messagebox.showerror("Invalid HEX", "Prefix contains non-HEX characters.")
                return False
            
            if prefix and len(prefix) % 2 != 0:
                messagebox.showerror("Invalid HEX", "Prefix has odd length.")
                return False
            
            # Convert prefix to bytes
            prefix_bytes = bytes.fromhex(prefix) if prefix else b''
            
            # Validate segment is HEX
            if not all(c in '0123456789ABCDEFabcdef' for c in segment):
                messagebox.showerror("Invalid HEX", "Segment contains non-HEX characters.")
                return False
            
            if len(segment) % 2 != 0:
                messagebox.showerror("Invalid HEX", "Segment has odd length.")
                return False
            
            # Convert segment data to bytes
            data_bytes = bytes.fromhex(segment)
            
            # Build request packet: [prefix][block_number][length][data][CRC]
            
            # Block number (2 bytes, big-endian - high byte first)
            block_number = self.current_segment_index
            block_bytes = block_number.to_bytes(2, byteorder='big')
            
            # Length (2 bytes, big-endian - high byte first) - number of data bytes
            length = len(data_bytes)
            length_bytes = length.to_bytes(2, byteorder='big')
            
            # Combine: prefix + block_number + length + data
            packet_without_crc = prefix_bytes + block_bytes + length_bytes + data_bytes
            
            # Calculate CRC over the entire packet (without CRC)
            crc = CRC16Modbus.calculate(packet_without_crc)
            crc_bytes = CRC16Modbus.to_bytes_le(crc)
            
            # Final packet
            final_packet = packet_without_crc + crc_bytes
            
            # Send
            self.serial_port.write(final_packet)
            
            # Log transmission - simple format
            hex_str = final_packet.hex().upper()
            self.log_message(f"TX: {hex_str}", "tx")
            
            return True
            
        except Exception as e:
            self.log_message(f"Send error: {str(e)}", "error")
            return False
    
    def check_reply_timeout(self, is_step):
        """Check if reply was received within timeout"""
        if self.reply_received:
            # Reply received and validated successfully, advance to next segment
            self.current_segment_index += 1
            
            if self.current_segment_index < len(self.file_segments):
                # Update display with next segment
                self.segment_input.delete("1.0", tk.END)
                self.segment_input.insert("1.0", self.file_segments[self.current_segment_index])
                
                total = len(self.file_segments)
                self.progress_var.set(f"Segment {self.current_segment_index + 1} / {total}")
                
                # Update block and length display
                self.update_block_length_display()
                
                if not is_step:
                    # Continue auto send
                    self.safe_schedule(self.send_next_in_auto_mode, delay=100)
                else:
                    # Re-enable step button
                    self.step_send_btn.config(state="normal")
            else:
                # All segments sent
                self.progress_var.set(f"Complete: {len(self.file_segments)} / {len(self.file_segments)}")
                
                if not is_step:
                    self.auto_send_complete()
                else:
                    self.log_message("All segments sent successfully", "info")
                    self.step_send_btn.config(state="normal")
        
        elif self.validation_failed:
            # Response received but validation failed - already handled in display_received_data
            # Just re-enable controls for step mode
            if is_step:
                self.step_send_btn.config(state="normal")
            # Auto send already stopped in display_received_data
        
        else:
            # No reply received within timeout
            self.log_message(f"Timeout: No response for block {self.current_segment_index + 1}", "error")
            
            if not is_step:
                self.stop_auto_send()
            else:
                self.step_send_btn.config(state="normal")
        
        self.waiting_for_reply = False
        self.validation_failed = False
    
    def auto_send_complete(self):
        """Handle completion of auto send"""
        self.auto_send_running = False
        self.auto_send_btn.config(state="normal")
        self.step_send_btn.config(state="normal")
        self.stop_auto_btn.config(state="disabled")
        self.log_message("Auto send completed successfully", "info")
    
    def stop_auto_send(self):
        """Stop the auto send process"""
        self.auto_send_running = False
        self.waiting_for_reply = False
        self.reply_received = False
        self.validation_failed = False
        self.auto_send_btn.config(state="normal")
        self.step_send_btn.config(state="normal")
        self.stop_auto_btn.config(state="disabled")
        self.log_message("Auto send stopped", "info")
    
    def poll_serial_data(self):
        """
        Poll for incoming serial data (replaces background thread).
        Uses Tkinter's after() to schedule periodic checks - more transparent than threading.
        """
        if not self.is_connected or not self.serial_port:
            return

        try:
            # Check if data is available
            if self.serial_port.in_waiting > 0:
                data = self.serial_port.read(self.serial_port.in_waiting)
                if data:
                    self.display_received_data(data)
        except Exception as e:
            self.log_message(f"Read error: {str(e)}", "error")

        # Schedule next poll if still connected
        if self.is_connected:
            self.safe_schedule(self.poll_serial_data, delay=self.polling_interval)
    
    def display_received_data(self, data: bytes):
        """
        Display received data in the log and validate response.
        
        Args:
            data: Received bytes to display
        """
        # Simple format: just show all hex data
        hex_str = data.hex().upper()
        self.log_message(f"RX: {hex_str}", "rx")
        
        # If we're waiting for a reply, validate it
        if self.waiting_for_reply:
            valid, error_msg = self.validate_response(data)
            
            if valid:
                self.reply_received = True
                self.validation_failed = False
            else:
                self.reply_received = False
                self.validation_failed = True
                self.log_message(f"Response error: {error_msg}", "error")
                # Stop auto send if running
                if self.auto_send_running:
                    self.safe_schedule(self.stop_auto_send)
    
    def validate_response(self, data: bytes):
        """
        Validate response packet according to protocol.
        
        Response format: [Slave ID][Function Code][Block Number][State][CRC]
        Total: 7 bytes (1 + 1 + 2 + 1 + 2)
        
        Args:
            data: Received response bytes
            
        Returns:
            tuple: (is_valid: bool, error_message: str)
        """
        # Check minimum length
        if len(data) < 7:
            return False, f"Response too short: {len(data)} bytes (expected 7)"
        
        # Extract fields
        slave_id = data[0]
        function_code = data[1]
        block_number_bytes = data[2:4]
        state = data[4]
        received_crc_bytes = data[5:7]
        
        # Verify CRC
        data_without_crc = data[0:5]
        calculated_crc = CRC16Modbus.calculate(data_without_crc)
        calculated_crc_bytes = CRC16Modbus.to_bytes_le(calculated_crc)
        
        if received_crc_bytes != calculated_crc_bytes:
            received_crc_hex = received_crc_bytes.hex().upper()
            calculated_crc_hex = calculated_crc_bytes.hex().upper()
            return False, f"CRC mismatch (received={received_crc_hex}, calculated={calculated_crc_hex})"
        
        # Check State field
        if state != 0xAC:
            return False, f"State != 0xAC (received State=0x{state:02X})"
        
        # Success
        return True, ""
    
    def log_message(self, message: str, tag: str = "info"):
        """
        Add a message to the log window.
        
        Args:
            message: The message to log
            tag: Text tag for coloring (tx, rx, error, info)
        """
        self.log_text.config(state="normal")
        
        # Add timestamp
        timestamp = time.strftime("%H:%M:%S")
        
        # Special formatting for TX/RX messages
        if message.startswith("TX: ") or message.startswith("RX: "):
            direction = message[:2]  # "TX" or "RX"
            content = message[4:]     # Everything after "TX: " or "RX: "
            self.log_text.insert(tk.END, f"[{timestamp}]", "info")
            self.log_text.insert(tk.END, f"[{direction}]: ", tag)
            self.log_text.insert(tk.END, f"{content}\n", tag)
        else:
            # Regular messages
            self.log_text.insert(tk.END, f"[{timestamp}] ", "info")
            self.log_text.insert(tk.END, f"{message}\n", tag)
        
        # Auto-scroll to bottom
        self.log_text.see(tk.END)
        
        self.log_text.config(state="disabled")
    
    def safe_schedule(self, callback, delay=0):
        """
        Safely schedule a callback to run in the main thread.
        
        Args:
            callback: Function to call
            delay: Delay in milliseconds (default: 0)
        """
        try:
            after_id = self.root.after(delay, callback)
            self.after_ids.append(after_id)
        except Exception:
            pass  # Window might be closing
    
    def on_closing(self):
        """Handle window close event - cleanup resources"""
        # Stop auto send if running
        if self.auto_send_running:
            self.stop_auto_send()
        
        # Disconnect if connected
        if self.is_connected:
            self.disconnect()
        
        # Cancel all scheduled callbacks
        for after_id in self.after_ids:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        
        self.after_ids.clear()
        
        # Destroy the window
        self.root.destroy()


def main():
    """Main entry point of the application"""
    root = tk.Tk()
    app = RS485SerialTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()