# Contributing to RegulaForge

Welcome to RegulaForge! We're thrilled that you'd like to contribute. This document outlines everything you need to know to get started.

Please read and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md) in all interactions.

---

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Local Setup](#local-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Commit Message Conventions](#commit-message-conventions)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Getting Help](#getting-help)

---

## Development Environment Setup

### Prerequisites

Ensure the following tools are installed on your development machine:

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | 18+ (LTS) | Frontend runtime |
| Python | 3.11+ | Backend runtime |
| Docker | 24+ with Docker Compose v2 | Containerized services |
| Poetry | 1.7+ | Python dependency management |
| Git | 2.40+ | Version control |

### Recommended Tools

- **Editor**: VS Code with ESLint, Prettier, Python, and Ruff extensions
- **PostgreSQL Client**: DBeaver, pgAdmin, or `psql`
- **Redis Insight**: For inspecting cached data
- **RabbitMQ Management UI**: Accessible at `http://localhost:15672`

---

## Local Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/regulaforge/regulaforge.git
cd regulaforge
```

### Step 2: Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

# Install Poetry if not already installed
pip install poetry

# Install all dependencies (including dev)
poetry install

# Configure environment
cp .env.example .env
```

Edit `.env` with your local database credentials and API keys. The defaults work with the Docker Compose services.

### Step 3: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
```

### Step 4: Start Infrastructure Services

```bash
cd docker
docker compose up -d postgres redis rabbitmq
```

This starts PostgreSQL (port 5432), Redis (port 6379), and RabbitMQ (port 5672).

### Step 5: Run Database Migrations

```bash
cd backend
alembic upgrade head
```

### Step 6: Start Development Servers

```bash
# Terminal 1 — Backend API (hot-reload enabled)
cd backend
uvicorn regulaforge.interfaces.api.app:app --reload --port 8000

# Terminal 2 — Frontend (hot-reload enabled)
cd frontend
npm run dev
```

The API is now at `http://localhost:8000/api/v1/docs` and the frontend at `http://localhost:5173`.

---

## Code Style Guidelines

We enforce strict code formatting and linting. All code must pass automated checks before merging.

### Python (Backend)

| Tool | Purpose | Configuration |
|------|---------|---------------|
| [Black](https://black.readthedocs.io/) | Code formatter | Line length: 100 |
| [Ruff](https://docs.astral.sh/ruff/) | Linter & import sorter | See `pyproject.toml` |
| [mypy](https://mypy-lang.org/) | Static type checker | Strict mode enabled |

Run checks locally:

```bash
cd backend

# Format code
ruff format .

# Lint
ruff check .

# Type check
mypy src/regulaforge
```

#### Python Conventions

- Follow [PEP 8](https://peps.python.org/pep-0008/) with a 100-character line limit
- Use type annotations for all function signatures and public APIs
- Use `async def` for all I/O-bound endpoints and database operations
- Prefer Pydantic v2 models for data validation and serialization
- Use dependency injection via FastAPI's `Depends()` rather than global state
- Write docstrings in Google style for all public modules, classes, and functions

### TypeScript / React (Frontend)

| Tool | Purpose | Configuration |
|------|---------|---------------|
| [Prettier](https://prettier.io/) | Code formatter | Default config |
| [ESLint](https://eslint.org/) | Linter | TypeScript + React Hooks rules |

Run checks locally:

```bash
cd frontend

# Format code
npx prettier --write src/

# Lint
npm run lint

# Type check
npm run typecheck
```

#### TypeScript Conventions

- Use TypeScript in strict mode — avoid `any` wherever possible
- Prefer functional components with hooks over class components
- Use Redux Toolkit for global state, TanStack React Query for server state
- Name files in kebab-case for components (`compliance-dashboard.tsx`)
- Use named exports for components, default exports only for pages and lazy routes
- Write unit tests for all components, hooks, and utilities

---

## Commit Message Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/) to auto-generate changelogs and releases.

### Format

```
<type>(<optional scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Usage |
|------|-------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `chore` | Routine tasks, dependency updates, tooling |
| `docs` | Documentation-only changes |
| `test` | Adding or updating tests |
| `refactor` | Code restructuring (no functional change) |
| `perf` | Performance improvements |
| `ci` | CI/CD configuration changes |
| `style` | Formatting, missing semicolons (no logic change) |

### Examples

```
feat(assessments): add bulk assessment export to CSV
fix(regulations): handle empty requirement list in parser
docs(api): update assessment endpoint examples
refactor(auth): extract RBAC middleware into shared module
ci: add Playwright e2e test pipeline
```

### Scope Guidelines

- `api` — FastAPI routes and handlers
- `domain` — Domain entities and business logic
- `infra` — Database, cache, or message broker code
- `ui` — React components and pages
- `ai` — ML models and NLP pipelines
- `docs` — Documentation only
- `deps` — Dependency updates

---

## Pull Request Process

### Branching Strategy

- **`main`** — Production-ready code. Protected — no direct pushes.
- **`develop`** — Integration branch for feature work. (Optional — we often branch directly from `main`.)
- **Feature branches** — Name them `feat/<short-description>`, `fix/<short-description>`, or `refactor/<short-description>`.

```bash
git checkout main
git pull origin main
git checkout -b feat/my-feature
```

### PR Checklist

Before submitting your pull request, ensure:

- [ ] Your code builds and passes all tests (`pytest` + `npm test:run`)
- [ ] You've run linters and formatters (`ruff`, `mypy`, `prettier`, `eslint`)
- [ ] All new and existing tests pass
- [ ] You've added tests for any new functionality
- [ ] You've updated documentation if APIs or behaviors changed
- [ ] Your commits follow the Conventional Commits format
- [ ] Your branch is up to date with `main` (rebased, not merged)
- [ ] You've included a screenshot for UI changes

### PR Size

- Keep PRs focused and small — ideally under 400 lines changed
- Break large features into multiple sequential PRs
- Mark work-in-progress PRs with `[WIP]` or use Draft PR mode

### CI Pipeline

All PRs automatically run:

1. **Lint & Format** — Ruff, mypy, ESLint, Prettier
2. **Unit Tests** — pytest (backend) + vitest (frontend)
3. **Integration Tests** — pytest with live database
4. **E2E Tests** — Playwright (on-demand)
5. **Build** — Frontend production build + Docker image
6. **Security Scan** — Dependency vulnerability check

Your PR must pass all CI checks before review. If checks fail, address the issues and push new commits — do not squash or rebase until review is complete.

### Review Process

1. At least one maintainer review is required
2. Address all review comments with additional commits
3. Once approved, squash-merge into `main` with a clean commit message
4. Delete the feature branch after merge

---

## Testing

### Backend (Python)

**Framework**: pytest with pytest-asyncio

```bash
cd backend

# Run all tests
pytest

# Run with coverage report
pytest --cov=regulaforge --cov-report=term-missing

# Run by category
pytest -m unit         # Unit tests (fast, no external deps)
pytest -m integration  # Integration tests (needs database)
pytest -m e2e          # End-to-end tests (full stack)
pytest -m "not slow"   # Skip slow tests

# Run specific file
pytest tests/test_assessments.py
```

Write tests in `backend/tests/` mirroring the `src/regulaforge/` structure. Use `factory-boy` for test data and `respx` for HTTP mocking.

### Frontend (TypeScript/React)

**Unit Testing**: Vitest + Testing Library

```bash
cd frontend

# Run all unit tests (watch mode)
npm test

# Run once
npm test:run

# With coverage
npx vitest run --coverage
```

**E2E Testing**: Playwright

```bash
cd frontend

# Run Playwright tests (headless)
npm run test:e2e

# Open Playwright UI
npm run test:e2e:ui
```

Write component tests in `frontend/tests/` alongside their corresponding source files.

---

## Project Structure

```
regulaforge/
├── backend/
│   ├── src/regulaforge/
│   │   ├── config/              # Settings, logging, constants
│   │   ├── domain/              # Entities, value objects, events
│   │   ├── application/         # Use cases, services, ports
│   │   ├── infrastructure/      # Persistence, messaging, cache
│   │   ├── interfaces/          # API, CLI, consumers
│   │   └── ai/                  # NLP, ML, evaluation pipelines
│   ├── tests/                   # Test suite
│   ├── alembic/                 # Database migrations
│   ├── pyproject.toml           # Python project config
│   └── .env.example             # Environment template
├── frontend/
│   ├── src/                     # React application
│   ├── tests/                   # Component tests
│   ├── e2e/                     # Playwright end-to-end tests
│   ├── package.json
│   └── vite.config.ts           # Vite configuration
├── docker/
│   ├── docker-compose.yml       # Service orchestration
│   ├── Dockerfile.backend       # Backend image
│   └── Dockerfile.frontend      # Frontend image
├── k8s/                         # Kubernetes manifests
├── ml/                          # ML training pipelines
├── infrastructure/              # Terraform, monitoring configs
├── docs/                        # Architecture documentation
├── scripts/                     # Utility scripts
├── .github/                     # GitHub templates and workflows
├── README.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── LICENSE
```

---

## Getting Help

- **Issue Tracker**: [github.com/regulaforge/regulaforge/issues](https://github.com/regulaforge/regulaforge/issues)
- **Discussions**: [github.com/regulaforge/regulaforge/discussions](https://github.com/regulaforge/regulaforge/discussions)
- **Email**: engineering@regulaforge.io
- **Slack**: [Join our workspace](https://join.slack.com/t/regulaforge/shared_invite/zt-intro)

---

Thank you for contributing to RegulaForge — together we're building the future of enterprise compliance.
