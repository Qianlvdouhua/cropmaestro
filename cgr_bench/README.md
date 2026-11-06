# CGR-Bench

**CGR-Bench**（Crop Germplasm Retrieval Benchmark）是种质资源智能检索的评测**金标数据集**，与论文 Table S2 对应。本目录发布题目与标注，并提供独立的[RSS评分复核材料](rss_evaluation/)；不包含底层种质库数据。

## 文件

| 文件 | 说明 |
|------|------|
| `cgr_bench_v1.0.csv` | 150 题金标（UTF-8） |
| `cgr_bench_gold.xlsx` | 与论文 Table S2 表头一致的单表 xlsx |

### 列说明

| 列名 | 含义 |
|------|------|
| `作物` / xlsx「作物」 | 大麦、水稻、玉米、大豆、小麦 |
| `编号` | 题号，如 `B-Q01`、`W-Q30` |
| `难度` | `L1` / `L2` / `L3`（各 50 题） |
| `query` / xlsx「测试问题」 | 自然语言查询 |
| `gold_sla` / xlsx「字段映射 (Schema Linking)」 | 字段链接金标 |
| `gold_vga` / xlsx「字段取值与阈值对齐 (Value Grounding)」 | 取值与阈值对齐金标 |

## 规模

- **150** 道自然语言查询  
- **5** 种作物 × **30** 题/作物  
- **L1 / L2 / L3** 各 50 题（难度递进）

论文中 SLA、VGA、EX、L3 等指标的定义与计分方式见正文；完整端到端评测仍需相应数据环境；[RSS复核目录](rss_evaluation/)提供针对已保存结果的离线复算脚本。

## 与本仓库（CropMaestro 开源版）的关系

| 内容 | 本 GitHub 仓库 | CGR-Bench |
|------|----------------|-----------|
| 可运行数据 | 仅 **商业水稻**（`bus_rice_data`） | 金标覆盖 **5 种作物** |
| 种质库 | 不含国家种质库全量数据 | 金标按**国家种质库 schema** 标注 |
| 能否在本仓库内直接跑满 150 题 | **否** | 金标供对照与二次评测使用 |

**口径说明：** 论文中的完整 CropMaestro 评测是在具备五种作物国家种质库数据的环境下进行的。出于数据安全，公开仓库**不**提供国家种质库数据，因此**无法**仅凭本仓库复现 CGR-Bench 上五种作物的端到端检索结果。  
CGR-Bench 在此开源的目的是：提供可复用的**题目与金标**，供研究者在自己的种质库或合规数据环境中评测；与本仓库演示用的商业水稻分支相互独立。

## 不包含的内容

- 国家种质库 / 商业种质库表数据  
- 模型调用凭据、完整跑批日志及依赖底层种质库的端到端评测环境
- 论文附表中含完整 API 响应的多 sheet 原始 xlsx  

## 引用

若在研究中使用了 CGR-Bench，请引用（DOI：）。

## RSS evaluation materials

The [English RSS evaluation guide](rss_evaluation/) explains the released relevance judgments, per-query normalization values, exclusions, scored accession outputs, and offline reproduction script. Complementary set comparisons are explicitly defined against pooled positive reference lists rather than exhaustive database result sets. These materials permit score reproduction without providing the underlying germplasm database.
