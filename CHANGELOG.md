# Changelog - RS485 Serial Communication Tool

## Version 1.0.1 - No Background Operations Update

### Major Changes to Reduce Antivirus False Positives

#### Removed Background Threading
- **REMOVED**: `SerialReaderThread` class that used Python threading
- **WHY**: Background threads are a common characteristic of malware
- **IMPACT**: Significantly reduces false positive detection rates

#### New Polling-Based Architecture
- **ADDED**: `poll_serial_data()` method using Tkinter's event loop
- **HOW IT WORKS**:
  - Uses `root.after()` to schedule periodic checks every 50ms
  - Runs entirely in the main GUI thread
  - No hidden background processes
  - Completely transparent to antivirus software

#### Benefits
1. **More Transparent**: All operations visible in main event loop
2. **AV-Friendly**: No thread spawning that triggers heuristic detection
3. **Same Functionality**: Serial communication works identically
4. **Safer**: Easier to audit and understand code flow

### Technical Details

#### Before (v1.0.0):
```python
# Background thread continuously reading
class SerialReaderThread(threading.Thread):
    def run(self):
        while self.running:
            if self.serial_port.in_waiting > 0:
                data = self.serial_port.read(...)
```

#### After (v1.0.1):
```python
# Polling using Tkinter event loop
def poll_serial_data(self):
    if self.serial_port.in_waiting > 0:
        data = self.serial_port.read(...)
    # Schedule next check
    self.root.after(50, self.poll_serial_data)
```

### Files Modified
- `main.py` - Complete rewrite of serial reading mechanism

### Compatibility
- **Python Version**: 3.7+
- **Dependencies**: pyserial (no changes)
- **Functionality**: 100% compatible with v1.0.0

### Performance Impact
- **CPU Usage**: Slightly lower (no thread context switching)
- **Responsiveness**: Identical for most use cases
- **Latency**: ~50ms polling interval vs instant thread wakeup
- **Practical Impact**: Negligible for RS485/Modbus communication

### Migration Notes
If you were using v1.0.0, simply replace the file. No configuration changes needed.

---

## Version 1.0.0 - Initial Release
- RS485/Modbus RTU communication
- CRC16-Modbus automatic calculation
- File chunking and segmented transmission
- GUI interface with Tkinter
