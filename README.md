# 🔍 Drishti AICTE
**AI-Powered Complaint Monitoring & Tracking System**
*Smart India Hackathon 2026 Prototype*

---

## 📋 Project Overview

Drishti AICTE ek integrated dashboard hai jo AICTE ke alag-alag bureaus/cells mein scattered complaints ko centralize karta hai. Isme AI-based cross-bureau complaint correlation, SLA tracking, role-based access control, aur immutable audit trail hai.

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite + Tailwind CSS v4 |
| Routing | React Router v7 |
| Charts | Recharts |
| HTTP | Axios |
| Icons | lucide-react |
| Backend | Python 3.11, FastAPI |
| ORM | SQLAlchemy 2.x + Alembic |
| Validation | Pydantic v2 |
| Auth | JWT (python-jose) + bcrypt |
| Database | SQLite (local dev) / PostgreSQL 16 (Docker) |
| Scheduling | APScheduler |
| ML | scikit-learn TF-IDF similarity |
| Testing | pytest + httpx |

---

## 📁 Project Structure

```
d:/SIH/
├── app/                        # FastAPI Backend
│   ├── main.py                 # App entry point, CORS, routes
│   ├── seed.py                 # Demo data seeder (120 complaints)
│   ├── core/
│   │   ├── config.py           # Settings (SECRET_KEY, DB URL, SLA, etc.)
│   │   ├── database.py         # SQLAlchemy engine + session
│   │   └── security.py         # JWT + bcrypt helpers
│   ├── models/                 # SQLAlchemy ORM models
│   ├── schemas/                # Pydantic v2 schemas
│   ├── api/v1/                 # Route handlers (auth, complaints, admin, analytics)
│   ├── services/               # Business logic (SLA, AI correlation)
│   └── ml/                     # ML utilities
├── frontend/                   # React Frontend
│   ├── src/
│   │   ├── App.jsx             # Router setup
│   │   ├── pages/              # Login, Register, Dashboards
│   │   └── components/         # Reusable UI components
│   └── vite.config.js          # Proxy: /api → localhost:8000
├── alembic/                    # DB migrations
├── tests/                      # pytest test suite
├── uploads/                    # Uploaded attachments
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # Full Docker stack
├── Dockerfile.backend
├── Dockerfile.frontend
└── .env.example                # Environment variables template
```

---

## 🚀 Local Development (SQLite — No Docker Needed)

### Step 1 — Backend

```powershell
# Project folder mein jao
cd d:\SIH

# Virtual environment activate karo
.\.venv\Scripts\Activate.ps1

# Pehli baar: install + migrate + seed
pip install -r requirements.txt
alembic upgrade head
python -m app.seed

# Backend start karo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Backend:** http://localhost:8000  
- **Swagger API Docs:** http://localhost:8000/docs

---

### Step 2 — Frontend

```powershell
# Naye terminal mein
cd d:\SIH\frontend

# Pehli baar hi install karein
npm install

# Dev server start karo
npm run dev
```

- **Frontend:** http://localhost:5173

---

## 👥 Demo Login Credentials

| Role | Email | Password |
|------|-------|----------|
| Super Admin | admin@aicte.gov.in | Admin@1234 |
| Bureau Officer | officer@aicte.gov.in | Officer@1234 |
| Complainant | user@example.com | User@1234 |

---

## 🐳 Docker Setup (PostgreSQL — Production-like)

```powershell
cd d:\SIH

# Saari services ek saath start karo
docker compose up --build

# Pehli baar seed karo
docker compose exec backend python -m app.seed
```

| Service | URL |
|---------|-----|
| Full App | http://localhost:80 |
| Backend | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

---

## 🧪 Tests Chalana

```powershell
cd d:\SIH
.\.venv\Scripts\Activate.ps1

pytest tests/ -v
```

---

## ⚙️ Environment Variables

```powershell
# .env.example ko copy karo
Copy-Item .env.example .env
```

Key variables:

```env
SECRET_KEY=apna-secret-key-likho
DATABASE_URL=sqlite:///./drishti.db

# PostgreSQL ke liye:
# DATABASE_URL=postgresql://drishti:drishti_pass@localhost:5432/drishti_db

SMTP_HOST=localhost
SMTP_PORT=1025
```

---

## 🔑 Features

- ✅ Role-Based Access — Complainant / Bureau Officer / Admin
- ✅ Complaint Filing — Attachments support (PDF, image, DOCX)
- ✅ AI Correlation — TF-IDF se cross-bureau similar complaints detect karo
- ✅ SLA Tracking — Urgent(1d) / High(3d) / Medium(7d) / Low(14d)
- ✅ Immutable Audit Trail
- ✅ Analytics Dashboard — Recharts graphs
- ✅ Auto Escalation on SLA breach

---

## 🌐 API Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/register` | Register |
| GET | `/api/v1/complaints/` | Complaints list |
| POST | `/api/v1/complaints/` | Nai complaint file karo |
| GET | `/api/v1/admin/dashboard` | Admin stats |
| GET | `/api/v1/analytics/bureau-stats` | Bureau analytics |

Full interactive docs: **http://localhost:8000/docs**

---

## 🛠️ Troubleshooting

### Backend start nahi ho raha?
```powershell
# Venv activate check karo
.\.venv\Scripts\Activate.ps1

# Port 8000 use mein hai?
netstat -ano | findstr :8000
# Wali PID kill karo: taskkill /PID <PID> /F
```

### Database reset karna ho?
```powershell
Remove-Item drishti.db -ErrorAction SilentlyContinue
alembic upgrade head
python -m app.seed
```

### Frontend API calls fail ho rahi hain?
```powershell
# Backend chal raha hai check karo:
Invoke-WebRequest http://localhost:8000/docs
```

---

## 📊 Current Session Status

| Service | URL | Status |
|---------|-----|--------|
| Backend (uvicorn) | http://localhost:8000 | ✅ Running |
| Frontend (vite) | http://localhost:5173 | ✅ Running |
| Database | SQLite — drishti.db | ✅ Active |

---

*Drishti AICTE — Smart India Hackathon 2026*
