
# PlanLytics Refactor — Clean Backend + Frontend

This splits your Python backend from the React frontend so Python files no longer contain JSX or notes that break deploys.

## Structure
```
planlytics-refactor/
  backend/
    app/
      main.py           # FastAPI app (serves /health, /api/*, and static FE)
      __init__.py
    requirements.txt
  frontend/
    index.html
    vite.config.ts      # outputs to ../backend/static
    tsconfig.json
    src/
      main.tsx
      App.tsx
  Dockerfile            # Multi-stage: builds FE, then Python 3.12 runtime
  render.yaml           # Render blueprint (Docker)
```

## Local dev (optional)
- Backend: `uvicorn app.main:app --reload --port 8080` from `backend/`
- Frontend: `npm i && npm run dev` from `frontend/` (proxy -> backend on 8080)

## Build and run with Docker (locally)
```
docker build -t planlytics .
docker run -p 8080:8080 planlytics
open http://localhost:8080/health
open http://localhost:8080/
```

## Deploy on Render
1. Commit these files to your repo.
2. On Render: **New → Blueprint → select `render.yaml`**.
3. Deploy. The Docker build will compile the frontend and serve it from the backend.

## Bring your analysis code
Add your existing processing logic under `/api/analyze` in `backend/app/main.py`, and merge any required libraries into `backend/requirements.txt`.
