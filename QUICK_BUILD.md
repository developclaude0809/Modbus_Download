# Quick Build Instructions

## Fastest Way to Build

### 1. Install Requirements (One Time)

```bash
pip install pyserial PyQt5 nuitka
```

### 2. Build

```bash
# Just double-click or run:
build.bat
```

### 3. Done!

Your executable is ready: **RS485_Modbus_Tool.exe**

---

## Alternative: PyInstaller

If Nuitka gives errors:

```bash
pip install pyinstaller
build_pyinstaller.bat
```

---

## Don't Want to Build?

Just run from source:

```bash
pip install pyserial PyQt5
python main.py
```

---

## Antivirus Detection?

✓ This code has **no background threads**
✓ Uses **PyQt5** (more trusted)
✓ Built with **console mode** (transparent)
✓ **No UPX compression**

**Still flagged?**
1. Code sign the .exe (best solution)
2. Submit false positive to AV vendor
3. Distribute source code with executable

See [BUILD_GUIDE.md](BUILD_GUIDE.md) for detailed instructions.
