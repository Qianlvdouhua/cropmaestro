"""
Session status API for n8n workflow progress callbacks (port 5000).

Start:
  cd backend
  python status_api.py

Environment variables (see .env.example at repo root):
  MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, request
from flask_cors import CORS
import pymysql
from pymysql.cursors import DictCursor

try:
    from DBUtils.PooledDB import PooledDB
except ImportError:  # DBUtils 2.x
    from dbutils.pooled_db import PooledDB

app = Flask(__name__)
CORS(app)

# In-memory fallback when MySQL is unavailable (demo only)
_memory_store: dict[str, dict] = {}


def _use_memory() -> bool:
    return os.getenv("STATUS_API_USE_MEMORY", "0").lower() in ("1", "true", "yes")


def _get_pool():
    return PooledDB(
        creator=pymysql,
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "cropmonster_demo"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        maxconnections=10,
    )


db_pool = None if _use_memory() else _get_pool()


def _memory_get(session_id: str) -> dict:
    return _memory_store.get(
        session_id,
        {"status": "unknown", "message": "", "confirmation": None},
    )


def _memory_set(session_id: str, status: str, message: str, confirmation=None) -> None:
    row = _memory_store.setdefault(session_id, {})
    row["status"] = status
    row["message"] = message
    if confirmation is not None:
        row["confirmation"] = confirmation


@app.route("/api/status", methods=["POST"])
def update_status():
    data = request.get_json(silent=True) or {}
    session_id = data.get("sessionId")
    if not session_id:
        return jsonify({"error": "sessionId is required"}), 400

    status = data.get("status", "processing")
    message = data.get("message", "")
    confirmation = data.get("confirmation")

    if _use_memory():
        _memory_set(session_id, status, message, confirmation)
        return jsonify({"success": True, "mode": "memory"})

    conn = None
    try:
        conn = db_pool.connection()
        with conn.cursor() as cursor:
            if confirmation is not None:
                sql = """
                    INSERT INTO request_status (session_id, status, message, confirmation)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                      status = VALUES(status),
                      message = VALUES(message),
                      confirmation = VALUES(confirmation),
                      update_time = CURRENT_TIMESTAMP
                """
                cursor.execute(
                    sql,
                    (session_id, status, message, confirmation),
                )
            else:
                sql = """
                    INSERT INTO request_status (session_id, status, message)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                      status = VALUES(status),
                      message = VALUES(message),
                      update_time = CURRENT_TIMESTAMP
                """
                cursor.execute(sql, (session_id, status, message))
        conn.commit()
        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if conn is not None:
            conn.close()


@app.route("/api/status/<session_id>", methods=["GET"])
def get_status(session_id: str):
    if _use_memory():
        return jsonify(_memory_get(session_id))

    conn = None
    try:
        conn = db_pool.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT status, message, confirmation FROM request_status WHERE session_id = %s",
                (session_id,),
            )
            row = cursor.fetchone()
        return jsonify(
            row or {"status": "unknown", "message": "", "confirmation": None}
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if conn is not None:
            conn.close()


@app.route("/api/status/confirm", methods=["POST"])
def confirm_status():
    data = request.get_json(silent=True) or {}
    session_id = data.get("sessionId")
    confirmation = data.get("confirmation")
    if not session_id or confirmation is None:
        return jsonify({"error": "sessionId and confirmation are required"}), 400

    if _use_memory():
        row = _memory_get(session_id)
        _memory_set(session_id, row.get("status", "unknown"), row.get("message", ""), confirmation)
        return jsonify({"success": True, "mode": "memory"})

    conn = None
    try:
        conn = db_pool.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE request_status SET confirmation = %s, update_time = CURRENT_TIMESTAMP WHERE session_id = %s",
                (confirmation, session_id),
            )
        conn.commit()
        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if conn is not None:
            conn.close()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "status_api"})


if __name__ == "__main__":
    port = int(os.getenv("STATUS_API_PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
