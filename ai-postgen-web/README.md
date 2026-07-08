# GrowMino Publisher Frontend

React frontend for the `ai-postgen` FastAPI backend, served as static files with no Vite build step.

## Run

1. Start a simple static server from this folder:

```powershell
python -m http.server 5173
```

2. Open:

```text
http://localhost:5173
```

The frontend calls the backend at `http://127.0.0.1:8000`.
