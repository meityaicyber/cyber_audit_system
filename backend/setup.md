# Cybersecurity Audit Report Management System - Setup Guide

This guide explains exactly how to run this project from scratch on a new system. 

The entire application is completely dockerized. You do **not** need to install Python, Node.js, or PostgreSQL on your host system. Everything runs inside isolated containers.

## 1. Prerequisites
You only need to have one piece of software installed on your computer:
* **Docker Desktop** (for Windows/Mac) or **Docker Engine + Docker Compose** (for Linux).

## 2. Project Setup

1. **Clone or copy the repository** to your local machine.
2. Open a terminal and navigate to the project's root folder (the folder containing `docker-compose.yml`).

## 3. Environment Variables
The application requires a few environment variables to run.

1. In the root directory, look for the file named `.env.example`.
2. Duplicate or rename this file to `.env`.
3. (Optional) Open `.env` and change the `DB_PASSWORD` and `SECRET_KEY` if you are deploying to a production server. For local development, the defaults are fine.

## 4. Run the Application

In your terminal, at the root of the project, run the following command:
```bash
docker compose up -d --build
```

**What this command does:**
* Downloads the necessary base images (PostgreSQL, SeaweedFS, Python, Node, Nginx, Adminer).
* Starts **SeaweedFS** (Master, Volume Server, and Filer) for distributed file storage.
* Builds the Backend API using FastAPI.
* Builds the React Frontend using Vite.
* Starts the database and runs the Alembic database migration scripts automatically to create all tables.
* Seeds the database with the default Admin user.
* Starts the Frontend static web server.

*(Note: The first time you run this, it may take a few minutes to download the base images and compile the frontend).*

## 5. Access the Services

Once the terminal returns to the prompt, all your services are running in the background.

Open your browser and navigate to the following URLs:

### 🌐 1. Frontend Application
* **URL:** [http://localhost:3000](http://localhost:3000)
* **Default Admin Credentials:**
  * **Username:** `admin`
  * **Password:** `Admin@123`
*(Use this account to log in, upload reports, and manage users).*

### ⚙️ 2. Backend API Documentation
* **URL:** [http://localhost:8000/docs](http://localhost:8000/docs)
* This is an interactive Swagger UI where you can view and test all the REST API endpoints directly.

### 🗄️ 3. Database Manager (Adminer)
* **URL:** [http://localhost:8080](http://localhost:8080)
* We included Adminer in the `docker-compose.yml` to give you a lightweight UI to inspect the PostgreSQL database.
* **Login Credentials:**
  * **System:** `PostgreSQL`
  * **Server:** `postgres`
  * **Username:** `postgres`
  * **Password:** *(Whatever you set as `DB_PASSWORD` in your `.env` file, default is `supersecretpassword`)*
  * **Database:** `cyber_audit`

### 📦 4. SeaweedFS Distributed File Storage
SeaweedFS is a distributed file storage system used to store all uploaded audit report files. It replaces traditional S3-compatible storage with a lightweight, high-performance alternative.

**Architecture** (all managed automatically via Docker Compose):
* **Master Server** — Coordinates the cluster, manages volume placement.
* **Volume Server** — Stores the actual file data on disk.
* **Filer** — Provides a familiar HTTP REST API (upload, download, delete) with automatic directory management.

**Accessible Endpoints:**
* **Filer UI:** [http://localhost:8888](http://localhost:8888) — Browse stored files via the Filer web interface.
* **Master UI:** [http://localhost:9333](http://localhost:9333) — View cluster status, topology, and volume health.

**Key Details:**
* No manual bucket/directory creation is needed — the Filer automatically creates directories on file upload.
* The backend communicates with the Filer at `http://seaweedfs-filer:8888` inside the Docker network.
* All uploaded files are encrypted with Fernet before being stored.
* Data is persisted in the `seaweedfs_data` Docker volume.

## Troubleshooting

**Viewing Logs:**
If a service isn't starting, you can view its logs. For example, to check the backend:
```bash
docker compose logs -f backend
```

To check SeaweedFS services:
```bash
docker compose logs -f seaweedfs-master seaweedfs-volume seaweedfs-filer
```

**Stopping the App:**
To shut down the application without losing data:
```bash
docker compose down
```

**Completely Resetting the App (Wiping Database & Storage):**
If you want to start completely fresh and wipe the database and uploaded files:
```bash
docker compose down -v
```
**To Downlaod Models:**
```bash
docker exec -it cyber-audit-backend python download_models.py
```