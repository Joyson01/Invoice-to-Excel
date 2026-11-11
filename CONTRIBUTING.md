# Contributing to Invoice PDF to Excel

Thank you for considering contributing! This document outlines our workflow, testing expectations, and contribution guidelines.

---

## Code of Conduct

Please be respectful, constructive, and professional in all interactions.

---

## Development Setup

### Prerequisites
- **Python 3.11+** (Python 3.12 recommended)
- **Node.js 18+** / **npm 9+**
- **Docker & Docker Compose** (optional, for containerized development)

### 1. Clone & Branch
```bash
git clone <repository-url>
cd Mojo
git checkout -b feature/your-feature-name
```

### 2. Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Frontend Setup
```bash
cd frontend
npm ci
npm run dev
```
Open [http://localhost:5173](http://localhost:5173). The Vite development server automatically proxies `/api` requests to `http://127.0.0.1:8000`.

---

## Running Tests & Quality Checks

Before submitting a pull request, verify that all quality checks pass.

### Backend Automated Tests
From the repository root:
```bash
backend/.venv/bin/python -m pytest
```
All tests must pass. The test suite includes unit tests, PDF parsing tests, template generation, and real OCR tests.

### Frontend Typecheck & Build
From the `frontend/` directory:
```bash
cd frontend
npm run lint    # Type-check via tsc --noEmit
npm run build   # Production Vite bundle build
```

---

## Pull Request Guidelines

1. **Keep PRs Focused:** Aim for small, single-purpose pull requests rather than broad refactorings.
2. **Add Tests:** If you are fixing a bug or adding a feature, provide test coverage in `tests/` or `backend/tests/`.
3. **Respect Security Boundaries:** Never commit sensitive files, credentials, or actual customer PDFs containing unredacted PII.
4. **Follow Formatting:** Adhere to `.editorconfig` (4 spaces for Python, 2 spaces for TypeScript/React/JSON/YAML).
5. **Update Documentation:** If you add or modify environment variables, endpoints, or workflows, update `README.md` and `.env.example`.
