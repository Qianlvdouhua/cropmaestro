-- Progress/status table used by backend/status_api.py (n8n HTTP callbacks on port 5000)
CREATE TABLE IF NOT EXISTS request_status (
  session_id VARCHAR(64) PRIMARY KEY,
  status VARCHAR(32) NOT NULL DEFAULT 'processing' COMMENT 'processing / success / failed',
  message VARCHAR(255) DEFAULT '' COMMENT 'Human-readable progress text',
  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  confirmation VARCHAR(10) DEFAULT NULL COMMENT 'User confirmation: yes / no'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Webhook session progress for frontend polling';
