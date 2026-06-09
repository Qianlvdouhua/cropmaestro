# Setup

## 1. 数据库

```bash
mysql -u root -p cropmaestro_demo < schema/ddl/00_chat_memory.sql
mysql -u root -p cropmaestro_demo < schema/ddl/01_bus_rice_data.sql
mysql -u root -p cropmaestro_demo < data/bus_rice_data.sql
mysql -u root -p cropmaestro_demo < schema/ddl/02_bus_rice_cache_results.sql
mysql -u root -p cropmaestro_demo < schema/ddl/03_request_status.sql
```

说明：`data/bus_rice_data.sql` 为完整 dump（含建表与 INSERT），若已执行 `01_bus_rice_data.sql`，导入 dump 时会先 `DROP TABLE` 再重建并灌数。

## 2. 启动后端服务

见 [backend/README.md](../backend/README.md)。

```bash
cd backend
pip install -r requirements.txt
python status_api.py
# 可选：python gs_predict_api.py
```

## 3. 挂载商业水稻提示词到 n8n

| 本地文件 | 容器路径 |
|----------|----------|
| `prompts/bus_rice/control/bus_rice_data.txt` | `/data/bus_rice_data.txt` |
| `prompts/bus_rice/analysis/bus_rice_mapping_data.txt` | `/data/Mapping/bus_rice_mapping_data.txt` |
| `prompts/bus_rice/execution/bus_rice_score_prompt.txt` | `/data/Prompt/bus_rice_score_prompt.txt` |
| `prompts/bus_rice/execution/bus_rice_conditional_prompt.txt` | `/data/Prompt/bus_rice_conditional_prompt.txt` |
| `prompts/bus_rice/interpretation/bus_rice_unit.txt` | `/data/Prompt/unit/bus_rice_unit.txt` |
| `prompts/bus_rice/interpretation/bus_rice_rule.txt` | `/data/Prompt/rule/bus_rice_rule.txt` |
| `schema/schema_bus_rice_demo.txt` | `/data/hrmshcema.txt` |

## 4. 导入 n8n 工作流

1. 导入 `workflow/CropMaestro.workflow.json`
2. 配置 MySQL、LLM（及可选 Qdrant）凭证
3. Webhook 请求示例（商业水稻）：

```json
{
  "config": { "commercialMode": true },
  "context": { "sessionId": "demo-001", "userType": "B" },
  "query": { "chatInput": "查询生育期较短的水稻商业品种" }
}
```

## 5. 扩展其他作物

参考 `bus_rice` 模式：建表 `{crop}_data`、编写四层 prompt、在工作流 `cropMap` 中注册。
