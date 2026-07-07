<div align="center">
  <img src="https://raw.githubusercontent.com/regulaforge/regulaforge/main/docs/assets/regulaforge-banner.svg" alt="RegulaForge Banner" width="800" />

  # RegulaForge — Enterprise Regulatory Compliance Platform

  **AI-powered regulatory compliance management for the regulated enterprise**

  [![Build](https://img.shields.io/github/actions/workflow/status/regulaforge/regulaforge/ci.yml?branch=main&style=flat-square&label=Build&logo=github)](https://github.com/regulaforge/regulaforge/actions)
  [![Tests](https://img.shields.io/github/actions/workflow/status/regulaforge/regulaforge/test.yml?branch=main&style=flat-square&label=Tests&logo=pytest)](https://github.com/regulaforge/regulaforge/actions)
  [![Coverage](https://img.shields.io/codecov/c/github/regulaforge/regulaforge/main?style=flat-square&label=Coverage&logo=codecov)](https://codecov.io/gh/regulaforge/regulaforge)
  [![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
  [![TypeScript](https://img.shields.io/badge/TypeScript-5.3-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
  [![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=white)](https://reactjs.org/)
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
  [![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
  [![License](https://img.shields.io/badge/License-Apache%202.0-blue?style=flat-square&logo=apache)](LICENSE)
  [![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)

  <br/>

  [Features](#-key-features) •
  [Architecture](#%EF%B8%8F-architecture) •
  [Quick Start](#-quick-start) •
  [Tech Stack](#%EF%B8%8F-tech-stack) •
  [Deployment](#-docker-deployment) •
  [Contributing](#-contributing)

</div>

---

RegulaForge is an open-source, enterprise-grade platform that transforms how regulated organizations manage compliance. It ingests regulations from any jurisdiction, uses AI to assess compliance posture, and provides real-time visibility through interactive dashboards and knowledge graphs. Built for BFSI, healthcare, and other regulated industries, RegulaForge replaces fragmented spreadsheets and manual assessments with a unified, intelligent compliance engine.

---

## ✨ Key Features

- **Multi-Jurisdiction Regulation Tracking** — Ingest, decompose, and version-track regulations from any source (PDF, DOCX, HTML, API) across multiple jurisdictions and regulatory bodies
- **AI-Powered Compliance Assessments** — Leverage LLMs and ML models to automatically assess entities against regulatory requirements with confidence scoring and hallucination detection
- **Interactive Knowledge Graph** — Visualize relationships between regulations, requirements, entities, and findings in an interactive Cytoscape-powered graph
- **Real-Time Monitoring** — Grafana dashboards, Prometheus metrics, and structured logging provide live insight into system health and compliance posture
- **Role-Based Access Control** — Fine-grained RBAC with multi-tenant isolation ensures users see only what they should
- **Audit Logging** — Every state change is cryptographically logged with immutable audit trails for regulatory submission readiness
- **ML-Driven Insights** — XGBoost, CatBoost, and LightGBM models predict compliance risk and identify emerging gaps before they become findings
- **Enterprise-Grade Security** — Encryption at rest and in transit, rate limiting, DDoS protection, and sensitive data masking

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                          CLIENT LAYER                                             │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │   React SPA (Vite)   │  │   Grafana Dashboards │  │  Admin CLI       │  │  External API      │ │
│  │   Port 5173          │  │   Port 3000          │  │  (Typer)         │  │  Consumers         │ │
│  └──────────┬───────────┘  └──────────┬───────────┘  └────────┬─────────┘  └─────────┬──────────┘ │
└─────────────┼──────────────────────────┼──────────────────────┼───────────────────────┼────────────┘
              │        HTTPS/REST        │        HTTP          │         CLI           │   RabbitMQ
┌─────────────┼──────────────────────────┼──────────────────────┼───────────────────────┼────────────┐
│             ▼                          ▼                      ▼                       ▼            │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                                    API GATEWAY (FastAPI)                                     │ │
│  │  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────┐ ┌──────────────────┐  │ │
│  │  │  REST API   │ │  WebSocket   │ │  Auth (JWT)  │ │  Rate Limit    │ │  OpenTelemetry   │  │ │
│  │  │  /api/v1/*  │ │  /ws/*       │ │  + RBAC      │ │  (Token Bucket)│ │  Traces & Metrics│  │ │
│  │  └──────┬──────┘ └──────┬───────┘ └──────┬───────┘ └───────┬────────┘ └────────┬─────────┘  │ │
│  └─────────┼───────────────┼────────────────┼─────────────────┼───────────────────┼─────────────┘ │
│            ▼               ▼                ▼                 ▼                   ▼               │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                                  APPLICATION SERVICES                                        │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐   │ │
│  │  │  Regulation   │ │  Compliance  │ │   Entity    │ │   Reporting  │ │    Notification   │   │ │
│  │  │  Service      │ │  Assessment  │ │   Manager   │ │   Engine     │ │    Service        │   │ │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬──────┘ └──────┬───────┘ └────────┬──────────┘   │ │
│  └─────────┼────────────────┼────────────────┼───────────────┼──────────────────┼───────────────┘ │
│            ▼                ▼                ▼               ▼                  ▼                 │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                                    DOMAIN LAYER                                              │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐   │ │
│  │  │Regulation│ │Requiremnt│ │ Finding │ │  Entity  │ │Assessment│ │  Domain Events     │   │ │
│  │  │Aggregate │ │  VO      │ │  Entity │ │  Root    │ │Aggregate │ │  & Specifications  │   │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────────────────┘   │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                            │                                                      │
│  ┌──────────────────────────────────────────┼──────────────────────────────────────────────────┐  │
│  │                          INFRASTRUCTURE LAYER                                               │  │
│  │  ┌────────────────────────────────────────────────────────────────────────────────────┐     │  │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │     │  │
│  │  │  │ PostgreSQL │  │   Redis 7  │  │  RabbitMQ  │  │  MLflow    │  │   S3/Minio │   │     │  │
│  │  │  │   16       │  │  Cache/Sess│  │  3.12      │  │  2.9       │  │  Artifacts  │   │     │  │
│  │  │  │ Async/Sync │  │  Pub/Sub   │  │  Task Queue│  │  ML Registry│  │  Document   │   │     │  │
│  │  │  └─────┬──────┘  └─────┬──────┘  └──────┬─────┘  └──────┬─────┘  └──────┬──────┘   │     │  │
│  │  └────────┼───────────────┼────────────────┼───────────────┼───────────────┼──────────┘     │  │
│  └───────────┼───────────────┼────────────────┼───────────────┼───────────────┼────────────────┘  │
└──────────────┼───────────────┼────────────────┼───────────────┼───────────────┼───────────────────┘
               │               │                │               │               │
  ┌────────────┼───────────────┼────────────────┼───────────────┼───────────────┼───────────────────┐
  │            ▼               ▼                ▼               ▼               ▼                    │
  │  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
  │  │                                MONITORING & OBSERVABILITY                                  │ │
  │  │  ┌─────────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  ┌───────────┐  │ │
  │  │  │  Prometheus  │  │Grafana │  │   Loki   │  │ Promtail │  │  Sentry     │  │  OpenTele │  │ │
  │  │  │  Metrics     │  │Alerts  │  │  Logs    │  │  Agent   │  │  Errors     │  │  Collector│  │ │
  │  │  └─────────────┘  └────────┘  └──────────┘  └──────────┘  └─────────────┘  └───────────┘  │ │
  │  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
  └──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- [Python](https://www.python.org/) 3.11+
- [Node.js](https://nodejs.org/) 18+ (LTS)
- [Docker](https://www.docker.com/) 24+ with Docker Compose v2
- [Poetry](https://python-poetry.org/) 1.7+

### 1. Clone the Repository

```bash
git clone https://github.com/regulaforge/regulaforge.git
cd regulaforge
```

### 2. Set Up Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install poetry
poetry install
cp .env.example .env
```

### 3. Set Up Frontend

```bash
cd frontend
npm install
cp .env.example .env
```

### 4. Start Infrastructure Services

```bash
cd docker
docker compose up -d postgres redis rabbitmq
```

### 5. Run Migrations & Start Development Servers

```bash
# Terminal 1 — Database migrations
cd backend
alembic upgrade head

# Terminal 1 — Backend API (http://localhost:8000)
uvicorn regulaforge.interfaces.api.app:app --reload --port 8000

# Terminal 2 — Frontend (http://localhost:5173)
cd frontend
npm run dev
```

Open [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs) for the interactive API documentation, and [http://localhost:5173](http://localhost:5173) for the frontend UI.

---

## 📁 Project Structure

```
regulaforge/
├── backend/                           # Python backend (FastAPI)
│   ├── src/regulaforge/
│   │   ├── config/                    # Application settings, logging, constants
│   │   ├── domain/                    # Business entities, value objects, aggregate roots
│   │   ├── application/               # Use cases, services, port interfaces
│   │   ├── infrastructure/            # Persistence, messaging, cache, external integrations
│   │   ├── interfaces/                # API controllers, CLI commands, event consumers
│   │   └── ai/                        # NLP, classification, extraction, evaluation, ML models
│   ├── tests/                         # pytest suite (unit, integration, e2e)
│   ├── alembic/                       # Database migration scripts
│   ├── pyproject.toml                 # Poetry configuration & tool settings
│   └── .env.example                   # Environment variable template
├── frontend/                          # React SPA (TypeScript, Vite)
│   ├── src/                           # Application source code
│   │   ├── components/                # Reusable UI components
│   │   ├── pages/                     # Route-level page components
│   │   ├── store/                     # Redux Toolkit slices
│   │   ├── hooks/                     # Custom React hooks
│   │   ├── api/                       # API client (Axios, React Query)
│   │   └── lib/                       # Utility functions
│   ├── tests/                         # Vitest unit & component tests
│   ├── e2e/                           # Playwright end-to-end tests
│   ├── package.json
│   └── vite.config.ts
├── docker/                            # Docker Compose & Dockerfiles
│   ├── docker-compose.yml             # Full stack orchestration
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
├── k8s/                               # Kubernetes deployment manifests
├── ml/                                # ML model training & evaluation pipelines
├── infrastructure/                    # Terraform & monitoring configuration
├── docs/                              # Architecture Decision Records & documentation
├── scripts/                           # Utility scripts
└── .github/                           # CI workflows, issue/PR templates
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, TypeScript 5.3, Vite 5, Tailwind CSS 3, Redux Toolkit, TanStack React Query 5, Recharts, Cytoscape, React Router v6, React Hook Form, Zod |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2.0 Async, Pydantic v2, Alembic, Uvicorn, OpenTelemetry |
| **Infrastructure** | PostgreSQL 16, Redis 7, RabbitMQ 3.12, Docker Compose, MinIO (S3-compatible) |
| **Monitoring** | Prometheus, Grafana, Loki, Promtail, Sentry |
| **AI/ML** | MLflow 2.9, LangChain, LangGraph, Hugging Face, OpenAI, Anthropic, XGBoost, CatBoost, LightGBM, Optuna, SHAP, scikit-learn |
| **Security** | JWT + RBAC, bcrypt, PyJWT, Cryptography, Sentry, Rate Limiting |

---

## 💻 Development Commands

### Backend

| Command | Description |
|---------|-------------|
| `uvicorn regulaforge.interfaces.api.app:app --reload` | Start development server |
| `pytest` | Run all tests |
| `pytest --cov=regulaforge --cov-report=term-missing` | Run tests with coverage |
| `ruff check .` | Lint Python code |
| `ruff format .` | Format Python code |
| `mypy src/regulaforge` | Static type check |
| `alembic upgrade head` | Run database migrations |
| `alembic revision --autogenerate -m "desc"` | Generate new migration |

### Frontend

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server (port 5173) |
| `npm run build` | Production build |
| `npm run test` | Run vitest in watch mode |
| `npm run test:run` | Run vitest once |
| `npm run test:e2e` | Run Playwright E2E tests |
| `npm run lint` | ESLint check |
| `npm run typecheck` | TypeScript type check |

### Docker

| Command | Description |
|---------|-------------|
| `docker compose up -d` | Start all services |
| `docker compose down` | Stop all services |
| `docker compose logs -f` | Follow service logs |
| `docker compose run --rm migrate` | Run database migrations |
| `docker compose --profile monitoring up -d` | Start with monitoring stack |

---

## 🧪 Testing

### Run All Tests

```bash
# Backend
cd backend && pytest

# Frontend unit tests
cd frontend && npm run test:run

# Frontend E2E tests
cd frontend && npm run test:e2e
```

### Test Categories

| Category | Backend Command | Frontend Command |
|----------|----------------|-----------------|
| Unit | `pytest -m unit` | `npm run test:run` |
| Integration | `pytest -m integration` | — |
| E2E | `pytest -m e2e` | `npm run test:e2e` |
| Coverage | `pytest --cov=regulaforge` | `npx vitest run --coverage` |

---

## 🐳 Docker Deployment

RegulaForge ships with a comprehensive Docker Compose setup supporting multiple profiles:

```bash
# Minimal stack (backend + frontend + database)
docker compose -f docker/docker-compose.yml up -d

# Full stack with monitoring (Prometheus + Grafana + Loki)
docker compose -f docker/docker-compose.yml --profile monitoring up -d

# Full stack with AI/ML (MLflow included)
docker compose -f docker/docker-compose.yml --profile ai up -d

# Everything
docker compose -f docker/docker-compose.yml --profile all up -d
```

### Monitoring URLs

| Service | URL | Default Credentials |
|---------|-----|-------------------|
| API Docs | [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs) | — |
| Frontend | [http://localhost:5173](http://localhost:5173) | — |
| Grafana | [http://localhost:3000](http://localhost:3000) | `admin` / `admin` |
| Prometheus | [http://localhost:9090](http://localhost:9090) | — |
| RabbitMQ UI | [http://localhost:15672](http://localhost:15672) | `guest` / `guest` |
| MLflow | [http://localhost:5000](http://localhost:5000) | — |

---

## 🤝 Contributing

We welcome contributions from the community! Whether it's bug fixes, features, documentation, or ideas, please see our [Contributing Guide](CONTRIBUTING.md) to get started.

- 📖 Read the [Contributing Guide](CONTRIBUTING.md)
- 📝 Review our [Code of Conduct](CODE_OF_CONDUCT.md)
- 🐛 Report bugs via [GitHub Issues](https://github.com/regulaforge/regulaforge/issues)
- 💬 Join [GitHub Discussions](https://github.com/regulaforge/regulaforge/discussions)

---

## 📄 License

Copyright 2026 RegulaForge Contributors

This project is licensed under the Apache License, Version 2.0 — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <strong>Built for enterprises that take compliance seriously.</strong>
  <br/>
  <br/>
  <a href="https://regulaforge.dev">regulaforge.dev</a> &nbsp;·&nbsp;
  <a href="https://github.com/regulaforge/regulaforge">GitHub</a> &nbsp;·&nbsp;
  <a href="https://twitter.com/regulaforge">@RegulaForge</a>
  <br/>
  <br/>
  <sub>© 2026 RegulaForge Contributors. Apache 2.0 License.</sub>
</div>
