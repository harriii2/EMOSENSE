# EmoSense — AI-Based Facial Emotion Detection & Wellness System

EmoSense is a real-time facial emotion detection and wellness web application built with **Flask**, **TensorFlow/Keras (CNN)**, and **OpenCV**. It detects a user's emotional state from their webcam feed and provides emotion-aware features: history tracking, a daily diary, an AI chatbot, personalized music/video recommendations, daily quotes, and emergency email alerts for trusted contacts.

---

## Features

- Real-time facial emotion detection (Angry, Disgust, Fear, Happy, Sad, Surprise, Neutral)
- Emotion history tracking with PDF export
- Daily diary with edit/delete support
- Emotion-aware AI chatbot (Groq API)
- Mood-based music & video recommendations
- Daily inspirational quotes
- Automatic emergency email alerts to a trusted contact after repeated "Sad" detections
- Full account management (profile photo, password, trusted contact)
- Secure authentication with password reset via email

---

## Project Structure

```
├── .env
├── .gitignore
├── app.py
├── auth/
│   ├── __init__.py
│   └── auth_routes.py
├── docs/
│   └── screenshots/
│       ├── landing.png
│       ├── dashboard.png
│       ├── scan.png
│       ├── history.png
│       └── diary.png
├── facialemotionmodel.json
├── model.h5
├── README.md
├── requirements.txt
├── static/
│   └── js/
│       └── webcam.js
└── templates/
    └── index.html
```

---

## Prerequisites

- **Python 3.9** (required — TensorFlow 2.10 used in this project only supports Python 3.9 reliably on most platforms)
- **MySQL Server** running locally (or accessible remotely), with a database created for the app
- A **Gmail account with an App Password** (for sending reset/alert emails) — [How to create a Gmail App Password](https://support.google.com/accounts/answer/185833)
- A **Groq API key** for the AI chatbot — [Get one here](https://console.groq.com/keys)

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/harriii2/EMOSENSE.git
cd EMOSENSE
```

### 2. Create a Python 3.9 virtual environment

TensorFlow 2.10 (used for the CNN emotion model) requires Python 3.9 — newer Python versions are not reliably supported.

```bash
py -3.9 -m venv venv
```

### 3. Activate the virtual environment

**Windows (PowerShell):**
```bash
venv\Scripts\activate
```

**Git Bash, WSL on Windows (Unix-like shells):**
```bash
source venv/Scripts/activate
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Set up MySQL

Create the database that your app will connect to (name must match `DB_NAME` in your `.env`):

```sql
CREATE DATABASE emosense_db;
```

Tables (`users`, `password_resets`, `emotion_history`, `diary`) are created automatically on first run via `init_auth_db()` — no manual schema setup needed.

### 6. Create your `.env` file

Create a `.env` file in the project root (same folder as `app.py`) with the following variables:

```env
# ── MySQL Database ──
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=emosense_db

# ── Email (SMTP) — used for password reset & emergency alerts ──
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
EMAIL_FROM=EmoSense<your_email@gmail.com>
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false

# ── Groq AI Chatbot ──
GROQ_API_KEY=your_groq_api_key
```

**Notes on `.env` values:**

| Variable | Description |
|---|---|
| `DB_HOST` | MySQL host — usually `localhost` |
| `DB_USER` | MySQL username — usually `root` |
| `DB_PASSWORD` | MySQL password for that user |
| `DB_NAME` | Database name the app will use/create tables in |
| `EMAIL_HOST` | SMTP server — `smtp.gmail.com` for Gmail |
| `EMAIL_PORT` | `587` for TLS (recommended), `465` for SSL |
| `EMAIL_USER` | Your full Gmail address |
| `EMAIL_PASSWORD` | A Gmail **App Password**, NOT your regular Gmail password (regular passwords will fail with an SMTP auth error) |
| `EMAIL_FROM` | Display name + address shown as sender, e.g. `EmoSense<you@gmail.com>` |
| `EMAIL_USE_TLS` | `true` if using port 587 |
| `EMAIL_USE_SSL` | `true` if using port 465 (mutually exclusive with TLS) |
| `GROQ_API_KEY` | API key from [console.groq.com](https://console.groq.com/keys) — powers the AI chatbot |


### 7. Run the app

```bash
python app.py
```

The app runs with a self-signed SSL certificate (`ssl_context='adhoc'`), so it will be available at:

```
https://127.0.0.1:5000
```

Your browser will show a security warning for the self-signed cert — click **Advanced → Proceed** to continue. (HTTPS is required here because browsers only allow camera access (`getUserMedia`) over a secure context or `localhost`.)

---

## Common Issues

- **`ModuleNotFoundError`** — make sure your virtual environment is activated before running `pip install` and `python app.py`.
- **MySQL connection errors** — verify `DB_HOST`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` in `.env`, and that MySQL server is running.
- **SMTP authentication failed** — use a Gmail **App Password**, not your normal password. Ensure 2-Step Verification is enabled on the Google account first.
- **Chatbot says "Sorry, I could not respond right now"** — check your terminal logs for the Groq API error; usually an invalid/expired `GROQ_API_KEY` or an unsupported `model` name.
- **Camera doesn't start** — make sure you're accessing the app via `https://` (or `localhost`), and that camera permissions are allowed in your browser.
- **TensorFlow install fails** — confirm you're using Python 3.9 exactly; TensorFlow 2.10 will not install on Python 3.11+.

---

## Screenshots

### Landing Page
![Landing Page](https://github.com/harriii2/EMOSENSE/blob/80e53c52b295047a4d6eaeeeba8761dabce27b53/docs/screenshots/landing.png)

### Dashboard
![Dashboard](https://github.com/harriii2/EMOSENSE/blob/80e53c52b295047a4d6eaeeeba8761dabce27b53/docs/screenshots/dashboard.png)

### Emotion Scan
![Emotion Scan](https://github.com/harriii2/EMOSENSE/blob/80e53c52b295047a4d6eaeeeba8761dabce27b53/docs/screenshots/scan.png)

### Emotion History
![Emotion History](https://github.com/harriii2/EMOSENSE/blob/80e53c52b295047a4d6eaeeeba8761dabce27b53/docs/screenshots/history.png)

### Daily Diary
![Daily Diary](https://github.com/harriii2/EMOSENSE/blob/80e53c52b295047a4d6eaeeeba8761dabce27b53/docs/screenshots/diary.png)

---

## Tech Stack

Python · Flask · TensorFlow/Keras · OpenCV · MySQL · Groq API or use any other · HTML/CSS/JavaScript

---

## Team

| Name | Role |
|---|---|
| Amit Kumar Kurmi | Frontend Development & UI Design |
| Dipu Thakur | CNN Model Training & Emotion Detection Module |
| Harichandra Thakur | Backend Development & Database Management |
| Prabin Kumar Sah | System Integration & Testing |

---
