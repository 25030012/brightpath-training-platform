# BrightPath Corporate Training Platform

Replaces BrightPath's 8 training spreadsheets with a role-based web platform for **Administrators**, **Instructors**, and **Learners**.

## Start in One Command (from a fresh clone)

```bash
./start.sh
```

This single command:
1. Creates `.venv` and installs dependencies (`Django`, `psycopg[binary]`, `pytest`, `pytest-django`).
2. Initializes and starts a local PostgreSQL instance (`.pgdata` on port `5433`) if not already running, and creates the `brightpath` database.
3. Runs database migrations (`python manage.py migrate`).
4. Runs the idempotent seed data importer (`python manage.py import_seed --data-dir data`).
5. Starts the HTTP server at **`http://127.0.0.1:8000`**.

## Default Sign-In Credentials

All imported accounts use default password: **`password123`** (you can sign in with either your **ID** or **email**):

| Role | Username (ID or Email) | Password | Notes |
|------|------------------------|----------|-------|
| **Administrator (Global)** | `S001` (`imran.doyle@brightpath.example`) | `password123` | Sees all clients & learners |
| **Administrator (Client CL02)** | `S004` (`pablo.kowalski@harbourbank.example`) | `password123` | Scoped to Harbour Bank (`CL02`) |
| **Instructor** | `S007` (`priya.varma@brightpath.example`) | `password123` | Assigned to Statistics cohorts |
| **Learner** | `11391` (`arjun.bhatti.733@example.com` / `3733`) | `password123` | Active learner account |
| **Departed Staff (Blocked)** | `S003` or `S006` | `password123` | Refused sign-in (`left_on` set) |

## Running the Import Command Directly

```bash
.venv/bin/python manage.py import_seed --data-dir data
```
