# CropMonster

CropMonster 是一个面向作物种质资源的智能检索框架。本仓库提供脱敏 n8n 工作流、**商业水稻（`bus_rice`）** 四层提示词、MySQL 表结构及商业品种数据导入脚本；另附评测金标 **[CGR-Bench](cgr_bench/)**（仅题目与标注，**不含**五种作物种质库数据，**不能**在本仓库内直接跑满 150 题，见该目录说明）。

## 快速开始

1. 执行 [schema/ddl](schema/ddl) 并导入 [data/bus_rice_data.sql](data/bus_rice_data.sql)
2. 启动 [backend/](backend/)（状态 API 5000；可选 GS API 8000）
3. 按 [docs/setup.md](docs/setup.md) 将 `prompts/bus_rice/` 挂载到 n8n `/data`
4. 导入 [workflow/CropMonster.workflow.json](workflow/CropMonster.workflow.json)，绑定 MySQL / LLM 凭证
5. 调用 Webhook 时设置 `"commercialMode": true`（水稻商业库分支）

## 目录概览

| 目录 | 说明 |
|------|------|
| `workflow/` | 脱敏 n8n JSON |
| `prompts/bus_rice/` | 商业水稻四层提示词 |
| `schema/` | DDL + `schema_bus_rice_demo.txt` |
| `data/` | `bus_rice_data.sql` 商业品种数据 |
| `cgr_bench/` | CGR-Bench 金标数据集（150 题，五种作物；注意与开源数据口径不同） |
| `backend/` | 状态同步与 GS 预测服务 |
| `docs/` | 架构与部署 |

## 引用

若在研究中使用了本框架，请引用您的论文条目（发表后补充 DOI / arXiv）。

## 许可

发布前请确认商业品种数据与 prompt 的对外发布范围，并自行选择 `LICENSE`。
