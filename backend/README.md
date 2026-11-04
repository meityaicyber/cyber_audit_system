# Cybersecurity Audit Report Management System

A production-ready full-stack application for managing cybersecurity audit reports with role-based access control, secure file upload with validation, metadata extraction, and comprehensive audit logging.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Material UI, React Hook Form |
| Backend | FastAPI, SQLAlchemy, Alembic, Pydantic |
| Database | PostgreSQL 16 |
| Auth | JWT + Argon2 password hashing |
| Containerization | Docker, Docker Compose |

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

### 1. Clone and Configure

```bash
# Copy environment template
cp .env.example .env

# (Optional) Edit .env to set secure passwords
```

### 2. Start the Application

```bash
docker compose up --build
```

This will:
- Start PostgreSQL 16 with health checks
- Wait for the database to be ready
- Run Alembic migrations to create all tables
- Seed default roles (ADMIN, AUDITOR, REVIEWER) and admin user
- Start the FastAPI backend on port 8000
- Build and serve the React frontend via Nginx on port 3000

### 3. Access the Application

| Service | URL |
|---------|-----|
| Frontend | [http://localhost:3000](http://localhost:3000) |
| Backend API | [http://localhost:8000](http://localhost:8000) |
| API Docs (Swagger) | [http://localhost:8000/docs](http://localhost:8000/docs) |

### 4. Login

```
Username: admin
Password: Admin@123
```

## Features

### Authentication & Authorization
- JWT access tokens (30 min expiry) + refresh tokens (7 day expiry)
- Refresh token rotation for security
- Argon2 password hashing
- Role-based access control (ADMIN, AUDITOR, REVIEWER)

### File Upload & Processing
- Drag & drop file upload with progress bar
- Supported formats: PDF, DOCX, TXT
- File validation: extension check, MIME type verification
- SHA256 hash generation and duplicate detection
- Metadata extraction (title, author, page count, etc.)
- Files stored at `/storage/reports/YYYY/MM/`

### Dashboard
- Total reports and users count
- Reports by status breakdown
- Recent uploads table

### User Management (Admin)
- Create, edit, deactivate users
- Role assignment with multi-select

### Audit Logging
- Tracks all file uploads, deletions, and user actions
- Filterable by action type
- Timestamped with user attribution

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login and get tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/logout` | Logout and revoke session |
| GET | `/api/auth/me` | Get current user profile |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reports/upload` | Upload a report file |
| GET | `/api/reports` | List reports with search |
| GET | `/api/reports/{id}` | Get report details |
| GET | `/api/reports/{id}/download` | Download report file |
| DELETE | `/api/reports/{id}` | Delete report (admin) |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users` | List users (admin) |
| POST | `/api/users` | Create user (admin) |
| PUT | `/api/users/{id}` | Update user (admin) |
| DELETE | `/api/users/{id}` | Deactivate user (admin) |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/audit-logs` | List audit logs (admin) |
| GET | `/api/dashboard/stats` | Dashboard statistics |
| GET | `/api/health` | Health check |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Configuration settings
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── dependencies.py      # Auth dependencies
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # API route handlers
│   │   ├── services/            # Business logic
│   │   └── utils/               # Security & file utilities
│   ├── alembic/                 # Database migrations
│   ├── requirements.txt
│   ├── Dockerfile
│   └── entrypoint.sh
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api/axios.js         # API client with interceptors
│   │   ├── contexts/            # Auth context
│   │   ├── components/          # Layout, guards
│   │   └── pages/               # All application pages
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
└── README.md
```

## Database Schema

10 tables: `users`, `roles`, `user_roles`, `user_sessions`, `reports`, `report_metadata`, `file_validation`, `file_storage`, `audit_logs`, `security_events`

## Stopping the Application

```bash
docker compose down

# To also remove data volumes:
docker compose down -v
```

## Development

### Backend only (outside Docker)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend only (outside Docker)

```bash
cd frontend
npm install
npm run dev
```

## License

MIT