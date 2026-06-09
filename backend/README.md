# Backend services

External HTTP services invoked by the n8n workflow (`host.docker.internal` from Docker).

| Service | Port | Entry | n8n usage |
| --- | --- | --- | --- |
| Status API | 5000 | `status_api.py` | `POST /api/status` — progress messages for the UI |
| GS API | 8000 | `gs_predict_api.py` | `POST /predict_phenotype_text` — molecular / GS branch |

## Install

```bash
cd backend
pip install -r requirements.txt
```

Copy repo `.env.example` to `.env` and set MySQL variables for the status API.

## 1. Status API (required for progress callbacks)

Create table:

```bash
mysql -u root -p cropmaestro_demo < ../schema/ddl/03_request_status.sql
```

Run:

```bash
python status_api.py
```

Demo without MySQL:

```bash
set STATUS_API_USE_MEMORY=1
python status_api.py
```

## 2. GS phenotype API (optional branch)

Only needed if you use molecular / genomic-selection nodes in the workflow.

1. Put `*_model_best.pt` and `*_scaler.pkl` under `gs_service/models/`
2. Start:

```bash
python gs_predict_api.py
```

Equivalent:

```bash
cd gs_service
uvicorn src.app:app --host 0.0.0.0 --port 8000
```

## Docker note

When n8n runs in Docker, `host.docker.internal` must reach these services on the host (Windows/Mac Docker Desktop supports this by default).
