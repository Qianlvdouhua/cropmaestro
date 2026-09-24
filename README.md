# CropMaestro

CropMaestro 是一个面向作物种质资源的智能检索框架。本仓库提供脱敏 n8n 工作流、**商业水稻（`bus_rice`）** 四层提示词、MySQL 表结构及商业品种数据导入脚本；另附评测金标 **[CGR-Bench](cgr_bench/)**（仅题目与标注，**不含**五种作物种质库数据，**不能**在本仓库内直接跑满 150 题，见该目录说明）。

## 快速开始

1. 执行 [schema/ddl](schema/ddl) 并导入 [data/bus_rice_data.sql](data/bus_rice_data.sql)
2. 启动 [backend/](backend/)（状态 API 5000；可选 GS API 8000）
3. 按 [docs/setup.md](docs/setup.md) 将 `prompts/bus_rice/` 挂载到 n8n `/data`
4. 导入 [workflow/CropMaestro.workflow.json](workflow/CropMaestro.workflow.json)，绑定 MySQL / LLM 凭证
5. 调用 Webhook 时设置 `"commercialMode": true`（水稻商业库分支）

## 目录概览

| 目录 | 说明 |
|------|------|
| `workflow/` | n8n JSON |
| `prompts/bus_rice/` | 商业水稻四层提示词 |
| `schema/` | DDL + `schema_bus_rice_demo.txt` |
| `data/` | `bus_rice_data.sql` 商业品种数据 |
| `cgr_bench/` | CGR-Bench 金标数据集（150 题，五种作物；注意与开源数据口径不同） |
| `backend/` | 状态同步与 GS 预测服务 |
| `docs/` | 架构与部署 |
| [`tools/data_importer/`](tools/data_importer/) | 可复用数据接入工具：CSV/TSV/XLSX 画像、来源专属提示词及非覆盖 MySQL 导入；附英文说明与合成示例 |

## 数据接入工具 / Data-import tool

[`tools/data_importer/`](tools/data_importer/) 提供可复用的数据接入工具及安装、配置和测试说明。工具接收已获取的表格数据，生成作物/数据源专属的接入包，并支持将数据发布到已配置的 MySQL。它不自动获取外部平台数据、不修改现有 n8n 工作流，也不执行跨来源数据协调或自动同步。来源语义和工作流连接仍需配置。该目录只提供源码、测试和合成示例，不包含实际种质记录或部署凭据。

The reusable [data-import tool](tools/data_importer/) includes source code, tests, and an English usage guide. It prepares source-specific retrieval packages from tabular datasets and supports non-overwriting publication to a configured MySQL deployment. The included example is synthetic; no additional germplasm records or deployment credentials are distributed with the tool.

## 引用

若在研究中使用了本框架，请引用您的论文条目（发表后补充 DOI / arXiv）。

## 许可

发布前请确认商业品种数据与 prompt 的对外发布范围，并自行选择 `LICENSE`。
