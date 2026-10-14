# CropMaestro
CropMaestro 是一个面向作物种质资源的多智能体智能检索框架，帮助农业科研人员和育种工作者通过自然语言描述需求，从种质资源数据中寻找符合要求的候选材料。

传统表单式检索通常要求用户熟悉性状名称、评价尺度和筛选阈值。CropMaestro 将需求理解、性状字段映射、数据库查询和结果解释组织为协同工作流，支持多性状、多约束的种质资源数据检索，以及相关专业知识问答。

## 框架概览

CropMaestro 采用四层多智能体架构：

- **控制层**：识别用户意图，判断任务类型，并引导用户澄清需求。
- **分析层**：定位目标作物，将用户需求映射到对应的数据字段和检索条件。
- **执行层**：生成并执行数据库查询，结合检索策略筛选候选种质记录。
- **解释层**：汇总检索结果，提供性状解释、推荐依据和可视化展示。
  
<img width="2386" height="1269" alt="Figure1" src="https://github.com/user-attachments/assets/fcb4d310-4a49-4b2f-9061-d5c7597201a5" />

框架通过加载数据源和作物对应的字段定义、计量单位、类别含义及相关知识，适配不同的检索任务。不同数据源可以复用同一套核心工作流，但每次查询在所选数据源内执行，不将不同来源的记录合并用于联合筛选或排序。

CropMaestro 集成两种检索策略：

- **知识增强检索**：检索与任务相关的作物标准、性状解释和数据源特定知识，辅助将自然语言需求转换为适当的字段与筛选条件。
- **并发对抗检索**：由多个检索智能体并行生成、执行候选查询，再通过评审智能体比较其与用户需求的匹配程度，选择最终结果。

 <img width="2487" height="1319" alt="Figure3" src="https://github.com/user-attachments/assets/59ddfad3-876a-4f9f-a4ca-8c765e849e0c" />

## 评测基准与仓库内容
我们构建了作物种质资源检索评测基准 **[CGR-Bench](cgr_bench/)**，包含五种主要作物的 150 道查询，覆盖三个难度等级，用于评估字段选择、检索条件及返回种质记录的质量。

本仓库提供脱敏 n8n 工作流、**商业水稻（`bus_rice`）** 四层提示词、MySQL 表结构、商业品种数据导入脚本，以及可复用的数据接入工具。

CGR-Bench 目录提供查询题目与参考标注，**不包含五种作物的种质库数据**。因此，仓库中的商业水稻部署示例不能直接用于完成全部 150 道基准查询，具体使用条件见该目录说明。

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

若在研究中使用了本框架，请引用本研究论文（DOI:）。

## 许可

数据导入工具 [`tools/data_importer/`](tools/data_importer/)（含该目录内的说明、测试和合成示例）采用 [MIT License](tools/data_importer/LICENSE)，版权所有 © 2026 Bintao Pan。此许可证不适用于仓库其他目录，不授予外部种质数据或其他第三方数据的使用权；第三方依赖遵循其各自许可证。

