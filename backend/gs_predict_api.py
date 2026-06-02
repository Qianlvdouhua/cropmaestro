"""
Launch genomic selection (GS) phenotype prediction API on port 8000.

Matches n8n nodes calling:
  POST http://host.docker.internal:8000/predict_phenotype_text

Start (from repository root):
  python backend/gs_predict_api.py

Or from backend/gs_service:
  uvicorn src.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

GS_ROOT = Path(__file__).resolve().parent / "gs_service"


def main() -> None:
    os.chdir(GS_ROOT)
    sys.path.insert(0, str(GS_ROOT))

    import uvicorn

    host = os.getenv("GS_API_HOST", "0.0.0.0")
    port = int(os.getenv("GS_API_PORT", "8000"))
    uvicorn.run("src.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
