# ⬡ N-UNZIPPER

<div align="center">
  <p><strong>Recursive Extraction Engine v2.0</strong></p>
  <p>
    <img src="[https://img.shields.io/badge/Python-3.8+-blue.svg](https://img.shields.io/badge/Python-3.8+-blue.svg)" alt="Python Version">
    <img src="[https://img.shields.io/badge/GUI-CustomTkinter-7c3aed.svg](https://img.shields.io/badge/GUI-CustomTkinter-7c3aed.svg)" alt="GUI">
    <img src="[https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-22c55e.svg](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-22c55e.svg)" alt="Platform">
    <img src="[https://img.shields.io/badge/License-MIT-f59e0b.svg](https://img.shields.io/badge/License-MIT-f59e0b.svg)" alt="License">
  </p>
</div>

---

**N-UNZIPPER** is a robust, Python-based graphical utility designed to automate the extraction of nested and mass-archived files. Built with a modern, dark-themed UI, it recursively scans directories to find and extract supported payloads while guarding against malicious archive vectors.

Developed by **Noufal NS** under **Byte Craft Labs**.

## ✨ Core Features

* **Recursive Deep-Scan:** Extracts archives hidden within other archives automatically up to 20 layers deep.
* **Multi-Format Support:** Natively unpacks `ZIP`, `TAR`, `GZ`, `BZ2`, and `XZ` (along with standard fallback extensions like `.tgz`, `.tbz2`).
* **Security First:** Built-in path-traversal guard prevents malicious archives from writing outside the designated destination directory.
* **Cryptographic Support:** Handles password-protected ZIP archives dynamically.
* **Data Integrity Validation:** Performs CRC validation (BadZipFile detection) and safely quarantines corrupt files with a `.broken` extension.
* **System Console Integration:** Real-time stdout terminal built directly into the UI for granular progress monitoring.
* **Modern UI:** A high-contrast "cyber" aesthetic built on CustomTkinter.

---

## 📸 Interface Overview

*(Add a screenshot of your application here by uploading an image to your repository and replacing the link below)*

> `![N-UNZIPPER Screenshot](link_to_your_image.png)`

---

## ⚙️ Installation

### Prerequisites
* **Python 3.8+** installed on your system.
* *(Optional but recommended)* `python3-venv` for virtual environments.

### Option 1: Automated Setup (Linux / macOS)
The fastest way to get started on Unix-based systems is using the provided bash script. This script automatically checks dependencies, creates an isolated virtual environment, installs requirements, and launches the app.

**1. Clone the repository:**
```bash
git clone https://github.com/yourusername/N-UNZIPPER.git
cd N-UNZIPPER
```

**2. Make the installer executable:**
```bash
chmod +x install_and_run.sh
```

**3. Engage the script:**
```bash
./install_and_run.sh
```

### Option 2: Manual Setup (Windows / Cross-Platform)

**1. Clone the repository:**
```cmd
git clone https://github.com/yourusername/N-UNZIPPER.git
cd N-UNZIPPER
```

**2. Install the required dependencies:**
```cmd
pip install -r requirements.txt
```

**3. Run the application:**
```cmd
python nunzipper.py
```

---

## 🚀 Usage Guide

1. **Select Destination:** Choose the output directory where all extracted files will land.
2. **Set Master Archive (Optional):** * If you select a specific file here, N-UNZIPPER will unpack it first, and then recursively scan the destination folder for any sub-archives it contained.
   * If left blank, N-UNZIPPER will immediately begin a directory scan of the Destination folder.
3. **Password:** Enter a decryption key if you are extracting protected ZIP files.
4. **Options:** Choose whether to ignore hidden `.dot` files, and toggle auto-cleanup of `.broken` quarantine files.
5. **Engage:** Click the start button and monitor the integrated terminal for live extraction statistics.

---

## 🛡️ Supported Formats & Limitations

| Format | Extension | Notes |
| :--- | :--- | :--- |
| **ZIP** | `.zip` | Full support including encrypted payloads. |
| **TAR** | `.tar` | Full support. |
| **GZIP** | `.gz`, `.tgz` | Decompresses and passes `.tar` to the next cycle. |
| **BZIP2** | `.bz2`, `.tbz2` | Decompresses and passes `.tar` to the next cycle. |
| **LZMA** | `.xz`, `.txz` | Decompresses and passes `.tar` to the next cycle. |

> **Note:** Proprietary formats like `7z` and `RAR` require external system binaries (7-Zip/Unrar) and are currently flagged as unsupported by the engine to maintain a zero-dependency Python footprint.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
<div align="center">
  <i>Initiate. Extract. Deploy.</i><br>
  <b>NOUFAL N S</b>
</div>
