# 💊 Pharmacy Workflow Automation System

> A full-stack pharmacy prescription management platform built with **Python**, **FastAPI**, and **SQLite** — featuring automated drug interaction checking, a status-driven workflow engine, and a live web frontend. Deployed on [Render](https://render.com).

---

## 🧭 Table of Contents

- [Overview](#-overview)
- [Live Demo](#-live-demo)
- [Tech Stack](#-tech-stack)
- [Features](#-features)
- [Workflow States](#-workflow-states)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [API Reference](#-api-reference)
- [Improvements Roadmap](#-improvements-roadmap)
- [Author](#-author)

---

## 📋 Overview

The Pharmacy Workflow Automation System automates the end-to-end lifecycle of a pharmacy prescription intake — from patient intake creation through clinical review, dispensing, and completion. It reduces manual pharmacist effort, catches drug interactions automatically, and enforces a safe, validated workflow.

This project demonstrates:
- Real-world **REST API design** with FastAPI
- **State machine** patterns for business workflow enforcement
- **Cloud deployment** with environment configuration and persistent storage
- Full-stack development across **backend API + HTML/JS frontend**

---

## 🌐 Live Demo

> **Backend API (Render):** _Add your Render URL here_
> **API Docs (Swagger UI):** `<your-render-url>/docs`
> **Frontend:** Open `frontend/index.html` locally or serve via HTTP (see setup below)

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn |
| Database | SQLite via SQLAlchemy ORM |
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Deployment | Render (cloud PaaS) |
| Version Control | Git, GitHub |

---

## ✨ Features

- **Intake Management** — Create and track patient prescriptions with name, age, allergies, and medication lists
- **Drug Interaction Checking** — Automatic detection of major/moderate severity interactions; re-check available at any time
- **7-Stage Workflow Engine** — Validated state transitions enforce correct business logic and prevent invalid status jumps
- **Counselling Points** — Auto-generated from medication types; fully editable by pharmacists
- **Pharmacist Notes** — Private, editable notes per intake
- **Dispense Tracking** — Timestamp-recorded dispense events
- **Staff Assignment** — Assign intakes to specific staff members
- **Statistics Dashboard** — Real-time counts by workflow status
- **Filtering** — Filter intake list by status

---

## 🔄 Workflow States

```
new → triage → waiting_info → ready_to_fill → filled → dispensed → completed
```

| State | Description |
|---|---|
| `new` | Intake just created |
| `triage` | Under clinical review |
| `waiting_info` | Awaiting additional patient information |
| `ready_to_fill` | Approved and ready for pharmacist to fill |
| `filled` | Prescription filled, awaiting pickup |
| `dispensed` | Medication handed to patient |
| `completed` | Workflow complete |

Transitions are strictly enforced at the service layer — invalid jumps return a `400` error with a descriptive message.

---

## 📁 Project Structure

```
Pharmacy-Project/
├── fastapi/
│   ├── myapi.py                  # App entry point, CORS config, router registration
│   ├── database.py               # SQLAlchemy models, engine, session management
│   ├── routers/
│   │   └── intakes.py            # All /intakes REST endpoints
│   ├── services/
│   │   └── intake_service.py     # Business logic: state transitions, drug checks
│   └── schemas/
│       ├── intake.py             # Pydantic request/response models
│       └── intake_actions.py     # Action schemas (status update, assign, dispense)
├── frontend/
│   └── index.html                # Single-page web UI (HTML + CSS + JS)
├── requirements.txt
├── Procfile                      # Render deployment command
├── runtime.txt                   # Python version pin
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- pip

### Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/MannPatel-CMPUT/Pharmacy-Project.git
cd Pharmacy-Project

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the backend
cd fastapi
uvicorn myapi:app --reload --port 8000
```

- API base URL: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

```bash
# 4. Serve the frontend (separate terminal)
cd frontend
python -m http.server 8080
# Open http://localhost:8080
```

> The database file `fastapi/pharmacy.db` is created automatically on first run.

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/intakes` | Create a new intake (auto drug-check) |
| `GET` | `/intakes` | List all intakes (`?status=` / `?assigned_to=`) |
| `GET` | `/intakes/{id}` | Get a specific intake |
| `POST` | `/intakes/{id}/status` | Advance workflow status |
| `POST` | `/intakes/{id}/assign` | Assign to a staff member |
| `POST` | `/intakes/{id}/counseling` | Update counselling points |
| `POST` | `/intakes/{id}/pharmacist-notes` | Update pharmacist notes |
| `POST` | `/intakes/{id}/dispense` | Record dispense event |
| `GET` | `/intakes/{id}/check-interactions` | Re-run drug interaction check |
| `GET` | `/intakes/stats/summary` | Intake counts by status |
| `GET` | `/health` | Health check |

Full interactive docs at `/docs` when the server is running.

---

## 🛣 Improvements Roadmap

- [ ] Add JWT-based authentication for staff login
- [ ] Replace SQLite with PostgreSQL for production scalability
- [ ] Add `pytest` unit tests for service layer and API endpoints
- [ ] Integrate a real drug database (e.g., OpenFDA API / RxNorm)
- [ ] Add pagination to `GET /intakes` for large datasets
- [ ] Add input sanitization and rate limiting middleware
- [ ] Dockerize the app for consistent local and cloud environments
- [ ] Add GitHub Actions CI/CD pipeline for automated testing on push

---

## 👤 Author

**Mann Patel**
BSc Computing Science — University of Alberta
[LinkedIn](https://www.linkedin.com/in/mann-patel-08359a3a3/) · [GitHub](https://github.com/MannPatel-CMPUT) · mannjpatel234@gmail.com
