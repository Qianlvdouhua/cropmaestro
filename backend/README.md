# Auxiliary HTTP Services

**This directory is not the intelligent retrieval backend.** CropMaestro performs retrieval through the [n8n workflows](../workflow/), configured with model services, prompts, and MySQL. These HTTP services support progress tracking and an optional GS prediction branch. Neither serves the hosted frontend.

For retrieval setup and Webhook requests, start with [Workflow Setup](../docs/setup.md).

## Status API

`status_api.py` is a Flask helper, using port **5000** by default:

- `POST /api/status`: store a session's progress status/message and optional confirmation value.
- `GET /api/status/<session_id>`: read stored state for client polling.
- `POST /api/status/confirm`: store a confirmation value for a session.
- `GET /health`: report that the helper process is running; it does not test MySQL or retrieval.

The helper does not interpret retrieval questions, invoke LLMs, generate resource-selection SQL, or return germplasm search results.

### Install only the status dependencies

From the repository root, in your Python environment:

```bash
python -m pip install "flask>=2.3.0" "flask-cors>=4.0.0" "pymysql>=1.1.0" "DBUtils>=3.0.0" "python-dotenv>=1.0.0"
```

`backend/requirements.txt` includes dependencies for both services, including GS prediction. Installing that whole file is unnecessary when using only status tracking.

### Configure and start with MySQL

Create the status table if it was not already created during setup:

```bash
mysql -u root -p cropmaestro_demo < schema/ddl/03_request_status.sql
```

Copy `.env.example` to a local `.env` and edit it with your settings:

```bash
cp -n .env.example .env
```

Do not overwrite an existing `.env`. Configure `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, and `MYSQL_PASSWORD`; use `STATUS_API_USE_MEMORY=0` for MySQL-backed operation.

**The script reads process environment variables; it does not call `load_dotenv()` itself.** Load the file explicitly when launching from the repository root:

```bash
python -c "from dotenv import load_dotenv; import runpy; load_dotenv('.env'); runpy.run_path('backend/status_api.py', run_name='__main__')"
```

Alternatively, export the variables in your service manager or shell, then run `python backend/status_api.py`. The `.env` file does not create n8n credentials. Keep it local and out of Git.

### Temporary in-memory status tracking

For a single-process smoke test without a status database, use a separate terminal. This does not make the n8n retrieval workflow database-free.

Bash:

```bash
STATUS_API_USE_MEMORY=1 python backend/status_api.py
```

PowerShell:

```powershell
$env:STATUS_API_USE_MEMORY = '1'
python backend/status_api.py
```

The store disappears when the process stops and is not shared across server processes. MySQL-backed status storage is required if other nodes on your configured path directly read `request_status`.

### Check progress tracking

```bash
curl 'http://localhost:5000/health'
curl --request POST 'http://localhost:5000/api/status' \
  --header 'Content-Type: application/json' \
  --data '{"sessionId":"status-demo-001","status":"processing","message":"Status callback test"}'
curl 'http://localhost:5000/api/status/status-demo-001'
```

These requests test the helper only. Send retrieval questions to the main n8n Webhook, not port 5000.

### Integrate with n8n

The main workflow calls `http://host.docker.internal:5000/api/status`. Confirm reachability **from n8n** and update URLs for your topology. `host.docker.internal` commonly works with Docker Desktop; Linux may need a host-gateway mapping or a service-network hostname.

Although status tracking is auxiliary, its callbacks currently sit inline before other nodes. If you do not need it, deliberately bypass the callback nodes and verify downstream input expressions. Do not merely stop the service and assume the unchanged workflow will continue. Confirmation-related branches need equivalent handling if used.

The sample Flask server binds to `0.0.0.0`, has no endpoint authentication, and enables CORS. Keep it on a trusted/private network or add access controls before exposing it. The built-in server is not a hardened public deployment.

## Optional GS Prediction Service

`gs_predict_api.py` launches the service in `gs_service/` on port **8000** by default. The n8n GS branch calls `POST /predict_phenotype_text`; it is separate from ordinary text-based germplasm retrieval.

To use this extension:

1. Install `backend/requirements.txt` in an appropriate environment. Choose a PyTorch installation compatible with your hardware.
2. Supply trained `*_model_best.pt` and `*_scaler.pkl` artifacts under `backend/gs_service/models/`; these are not included.
3. Start from the repository root:

```bash
python backend/gs_predict_api.py
```

Configure its n8n endpoint and validate it with compatible inputs. See the [GS service documentation](gs_service/README.md) and [model-artifact notes](gs_service/models/README.md). Do not enable this branch without the models and input contract configured.
