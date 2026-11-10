# ASET — Ansh Secure Examination Technology
> **Tagline:** *Secure. Offline. Intelligent.*

**ASET** (**A**nsh **S**ecure **E**xamination **T**echnology) is a modern, tamper-resistant, web-based examination & proctoring platform engineered specifically for college computer laboratories, campus LANs, and local Wi-Fi environments.

---

## 🎯 Key Project Highlights (4th-Year CSE Final Project Ready)

1. **100% Offline & Zero Cloud Dependency**:
   - Runs directly on local lab servers or teacher laptops without requiring active internet connectivity.
   - Powered by **Python 3, Flask, and SQLite** for lightweight, highly reliable local concurrency.

2. **Cross-Device Responsiveness (Mobile, Tablet, Laptop, Desktop)**:
   - Modern, fluid CSS grid/flex architecture without bulky external CDNs.
   - Supports touch-screen smartphones (WebRTC front-camera, responsive question palette, large tap targets) as well as lab PCs.

3. **Facial Attendance & Live Identity Verification**:
   - Integrated with **OpenCV (Biometric Presence & Facial Matching)**.
   - Verifies single frontal face presence before granting exam entry.
   - Stores candidate facial snapshot badge alongside attendance records in SQLite.

4. **Paper Leak Prevention & Cryptography**:
   - **AES-256 Symmetric Fernet Encryption**: Questions and answer options are encrypted at rest in the SQLite database.
   - Decryption takes place **in-memory only** when an authorized candidate supplies the secret exam passcode announced by the invigilator.
   - **Dynamic Full-Screen Watermarking**: Semi-transparent, multi-diagonal watermark of `Student Name | Roll No | Client IP | Live Timestamp` rendered over the viewport to deter mobile photography or screen capture.

5. **Multi-Strike Anti-Cheating & Malpractice Protection**:
   - **Fullscreen Enforcement**: Fullscreen is strictly mandatory; exiting prompts an immediate modal alert.
   - **Tab Switch & App Blur Detection**: Intercepts `visibilitychange`, `blur`, and `pagehide` events across desktop and mobile browsers.
   - **3-Strike Termination**: Every malpractice attempt logs a strike in the candidate's session; upon reaching 3 strikes, the exam is automatically locked and submitted.
   - **Input & DevTools Lockdown**: Blocks right-click context menu, text selection, copy/paste, and shortcuts (`F12`, `Ctrl+Shift+I`, `Ctrl+U`, `Ctrl+P`, `Alt+Tab`).

6. **Student Self-Registration**:
   - Students can self-register using their College Roll Number, Name, Branch, and snap their reference face photo via webcam.
   - Eliminates the need for teachers to manually hand out IDs and passwords.

7. **Instant Automated Evaluation & Deep Question Analysis**:
   - Graded automatically upon submission with immediate marks, percentage, and pass/fail calculations.
   - Detailed question-by-question post-exam analysis showing the candidate's selected choice, true correct choice, and faculty explanations.

8. **College Exam Leaderboard**:
   - Real-time merit rankings.
   - Top 3 Podium (Gold, Silver, Bronze badges) and full college rank list with tie-breaking logic based on accuracy and completion speed.

---

## 🚀 Quick Start Guide (Windows)

### Option 1: 1-Click Batch Starter
Simply double-click `run.bat` in the project folder:
`C:\Users\LOQ\.gemini\antigravity\scratch\offline-exam-portal\run.bat`

### Option 2: Terminal / PowerShell
```powershell
cd C:\Users\LOQ\.gemini\antigravity\scratch\offline-exam-portal
python seed_data.py
python app.py
```

Open your browser at:
- **Local Access:** `http://localhost:5000`
- **Lab / LAN Access:** `http://<YOUR_LAN_IP>:5000` (e.g. `http://10.207.235.106:5000`)
