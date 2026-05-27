-- Session memory for multi-turn retrieval (required by n8n workflow)
CREATE TABLE IF NOT EXISTS chat_memory (
  id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
  session_id VARCHAR(128) NOT NULL COMMENT '会话唯一标识',
  question TEXT COMMENT '用户提问内容',
  answer TEXT COMMENT 'LLM 回答内容',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `sql` TEXT COMMENT '最近一次有效查询 SQL',
  query_hash VARCHAR(64) COMMENT '查询哈希，用于缓存命中',
  varieties TEXT COMMENT '作物英文标识，如 bus_rice'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话与查询缓存元数据';

CREATE INDEX idx_chat_memory_session ON chat_memory (session_id, created_at DESC);
CREATE INDEX idx_chat_memory_hash ON chat_memory (query_hash);
