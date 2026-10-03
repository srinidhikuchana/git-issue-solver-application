# OpenFix AI

OpenFix AI is a multimodal open-source contribution copilot.

The main workflow is intentionally simple:

1. Paste a **public GitHub repository URL**
2. OpenFix analyzes the repository and open issues
3. Pick an issue
4. OpenFix inspects likely relevant source files
5. It produces a root-cause explanation, fix plan, suggested patch, tests, and contribution checklist

As an optional workflow, a contributor can also upload an **error screenshot**. The open-weight vision model reads the screenshot and produces a debugging report. A repository URL may optionally be supplied with the screenshot for extra context.

## Why this fits the challenge

Open-weight AI is central to the product. It powers:

- repository understanding
- issue triage
- contribution difficulty estimation
- relevant-file selection
- source-code reasoning
- root-cause analysis
- patch suggestions
- test planning
- screenshot / visual error understanding

The repository is public-ready and includes an MIT license.

## Architecture

```text
React + Vite frontend
        |
        v
FastAPI backend
        |
        +---- GitHub REST API
        |
        +---- OpenRouter
                  |
                  v
          Open-weight multimodal model
```

## Project structure

```text
openfix-ai/
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── .env.example
│   └── render.yaml
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── .env.example
│   └── vercel.json
├── .gitignore
├── LICENSE
└── README.md
```

## Local setup

### 1. Backend

```bash
cd backend
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, then add your OpenRouter key:

```env
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=qwen/qwen2.5-vl-32b-instruct:free
ALLOWED_ORIGINS=http://localhost:5173
```

Run:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Backend health check:

```text
http://localhost:8000/api/health
```

### 2. Frontend

Open another terminal:

```bash
cd frontend
npm install
```

Copy `.env.example` to `.env`:

```env
VITE_API_URL=http://localhost:8000
```

Run:

```bash
npm run dev
```

Then open:

```text
http://localhost:5173
```

## Deploy

Recommended:

- Frontend: Vercel
- Backend: Render
- AI: OpenRouter
- Source: GitHub

Detailed steps are included in the ChatGPT response that accompanied this project bundle.

## Environment variables

### Backend

- `OPENROUTER_API_KEY` — required
- `OPENROUTER_MODEL` — optional; default is defined in `app.py`
- `ALLOWED_ORIGINS` — comma-separated frontend URLs
- `GITHUB_TOKEN` — optional; useful if you hit GitHub's anonymous rate limit

### Frontend

- `VITE_API_URL` — deployed FastAPI backend URL

## Security

Never commit `.env` files, API keys, tokens, passwords, or private repository content.

This app is designed for public repositories. Suggested patches are AI-generated guidance and must be reviewed and tested before opening a pull request.
