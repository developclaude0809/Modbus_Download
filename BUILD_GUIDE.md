# Build Guide - RS485 Serial Communication Tool

## Overview

This guide explains how to build the RS485 Serial Communication Tool from source code into a standalone executable. The PyQt5 version with polling-based serial reading is optimized to avoid antivirus false positives.

## Prerequisites

### 1. Install Python
- Python 3.7 or higher
- Download from: https://www.python.org/downloads/

### 2. Install Dependencies

```bash
# Install runtime dependencies
pip install pyserial PyQt5

# Install Nuitka (recommended for lower AV detection)
pip install nuitka

# OR install PyInstaller (alternative, easier to use)
pip install pyinstaller

# Install all at once
pip install -r requirements-build.txt
```

### 3. Install C++ Compiler (for Nuitka)

**Windows:**
- Install Visual Studio 2019 or 2022 (Community Edition is free)
- During installation, select "Desktop development with C++"
- Download: https://visualstudio.microsoft.com/downloads/

## Build Methods

### Method 1: Nuitka (Recommended - Lowest AV Detection)

**Advantages:**
- Compiles to native machine code
- Better performance
- Lower antivirus detection rates
- Smaller executable size

**Build Command:**

```bash
# Using the provided batch file (easiest)
build.bat

# OR manually
python -m nuitka ^
  --onefile ^
  --windows-console-mode=attach ^
  --enable-plugin=pyqt5 ^
  --company-name="Industrial Automation Tool" ^
  --product-name="RS485 Serial Communication Tool" ^
  --file-version=1.0.1.0 ^
  --file-description="RS485 Modbus Serial Testing Tool - NOT malware" ^
  --output-filename="RS485_Modbus_Tool.exe" ^
  main.py
```

**Output:** `RS485_Modbus_Tool.exe`

### Method 2: PyInstaller (Alternative)

**Advantages:**
- Easier to use (no C++ compiler needed)
- Faster build time
- More mature tooling

**Disadvantages:**
- Slightly higher AV detection rate
- Larger executable size

**Build Command:**

```bash
# Using the provided batch file
build_pyinstaller.bat

# OR manually
pyinstaller ^
  --onefile ^
  --console ^
  --noupx ^
  --name="RS485_Modbus_Tool" ^
  main.py
```

**Output:** `dist\RS485_Modbus_Tool.exe`

### Method 3: Run from Source (No Build Required)

**For testing or if you don't need an executable:**

```bash
python main.py
```

## Build Options Explained

### Key Options to Reduce AV Detection

| Option | Purpose | Impact on AV Detection |
|--------|---------|----------------------|
| `--console` / `--windows-console-mode=attach` | Shows console window | ✓ More transparent, lower detection |
| `--noupx` | Disables UPX compression | ✓ UPX often triggers AV |
| `--company-name` | Adds company metadata | ✓ Legitimate applications have metadata |
| `--file-description` | Adds description | ✓ Helps AV understand purpose |
| `--enable-plugin=pyqt5` | Include PyQt5 properly | - Required for PyQt5 apps |

### Console vs No Console

**With Console (`--console`):**
- ✓ More transparent to antivirus
- ✓ Shows errors if they occur
- ✓ Users can see the application is legitimate
- ✗ Console window always visible

**Without Console (`--noconsole` or `--windows-disable-console`):**
- ✓ Cleaner appearance
- ✗ Higher AV suspicion
- ✗ Can't see error messages

**Recommendation:** Use console mode for distribution to minimize AV issues.

## After Building

### 1. Test the Executable

```bash
# Run on your development machine
RS485_Modbus_Tool.exe

# Test on a clean Windows VM
# - Windows 10/11 with Windows Defender enabled
# - No Python installed
# - Fresh install
```

### 2. Check with VirusTotal

**IMPORTANT:** Only upload if you're comfortable with public distribution.

1. Go to https://www.virustotal.com/
2. Upload your executable
3. Review detection results
4. Report false positives to flagging vendors

### 3. Code Sign (Highly Recommended)

**Why?**
- Reduces false positives by 90%+
- Establishes trust with Windows
- Professional appearance

**How?**
1. Purchase code signing certificate ($100-300/year)
   - DigiCert, Sectigo, GlobalSign
2. Use `signtool.exe` to sign:

```bash
signtool sign /f your_certificate.pfx /p password /t http://timestamp.digicert.com RS485_Modbus_Tool.exe
```

### 4. Submit False Positives

If any antivirus flags your executable:

**Windows Defender:**
https://www.microsoft.com/en-us/wdsi/filesubmission

**Other Vendors:**
- Check VirusTotal results for vendor links
- Submit through vendor portals
- Include source code and explanation

## Distribution Checklist

- [ ] Build with console mode enabled
- [ ] Disable UPX compression
- [ ] Include metadata (company, version, description)
- [ ] Test on clean Windows VM
- [ ] Check with VirusTotal
- [ ] Code sign if possible
- [ ] Include source code
- [ ] Include README.md explaining legitimacy
- [ ] Include this BUILD_GUIDE.md
- [ ] Report false positives

## Troubleshooting

### Nuitka: "C++ compiler not found"

**Solution:**
1. Install Visual Studio with C++ development tools
2. Restart command prompt/terminal
3. Try again

### PyInstaller: "Failed to execute script"

**Solution:**
```bash
# Build with console to see error
pyinstaller --onefile --console main.py

# Run and check error message
dist\RS485_Modbus_Tool.exe
```

### Antivirus Deletes Executable

**Solution:**
1. Add exception in antivirus settings
2. Rebuild with `--console` flag
3. Submit false positive to vendor
4. Consider code signing

### Import Errors

**Solution:**
```bash
# Ensure all dependencies installed
pip install -r requirements-build.txt

# For Nuitka, explicitly include modules
python -m nuitka --follow-imports main.py
```

## Advanced: Creating an Installer

For professional distribution, consider creating an installer:

### Using Inno Setup

1. Download Inno Setup: https://jrsoftware.org/isinfo.php
2. Create installer script (example: installer.iss)
3. Build installer
4. Sign installer with code signing certificate

**Benefits:**
- Professional appearance
- Can add shortcuts, registry entries
- Uninstaller included
- Better perceived legitimacy

## Performance Tips

### Nuitka Optimization

```bash
python -m nuitka ^
  --onefile ^
  --lto=yes ^
  --windows-console-mode=attach ^
  --enable-plugin=pyqt5 ^
  main.py
```

- `--lto=yes` enables link-time optimization (faster executable)

### Reducing File Size

```bash
# Exclude unnecessary modules
python -m nuitka ^
  --onefile ^
  --nofollow-import-to=tkinter ^
  --nofollow-import-to=matplotlib ^
  main.py
```

## Final Notes

### Why This Approach Reduces False Positives

1. **No background threads** - Polling instead of threading
2. **PyQt5** - More trusted framework than Tkinter
3. **Console mode** - Transparent operation
4. **No UPX** - Avoids compression detection
5. **Metadata** - Professional appearance
6. **Clean code** - No obfuscation

### Support

For build issues:
1. Check error messages carefully
2. Verify all dependencies installed
3. Try PyInstaller if Nuitka fails
4. Run from source to verify code works

For antivirus issues:
1. Submit false positives
2. Consider code signing
3. Distribute with source code
4. Explain tool purpose clearly

---

**Remember:** This is a legitimate industrial automation tool. All features are standard for RS485/Modbus communication testing.
