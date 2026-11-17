<div align="center">
  <img width="2172" height="724" alt="CropMaestro 横幅" src="https://github.com/user-attachments/assets/be8722c5-8b84-4554-a762-204744847d5f" />

  <h1>CropMaestro：让种质资源智能检索<br>触手可及。</h1>

  <p>面向作物种质资源自然语言检索的多智能体框架。</p>

  <p>
    <a href="https://github.com/Qianlvdouhua/cropmaestro/stargazers">
      <img src="https://img.shields.io/github/stars/Qianlvdouhua/cropmaestro" alt="GitHub 星标数">
    </a>
    <a href="https://github.com/Qianlvdouhua/cropmaestro/forks">
      <img src="https://img.shields.io/github/forks/Qianlvdouhua/cropmaestro" alt="GitHub 复刻数">
    </a>
    &nbsp; · &nbsp;
    <strong>简体中文</strong> | <a href="README.md">English</a>
  </p>

  <p>
    <a href="http://122.9.8.16/">在线演示</a>
    ·
    <a href="docs/setup.md">工作流配置</a>
    ·
    <a href="cgr_bench/">CGR-Bench</a>
    ·
    <a href="docs/crop_standards/">作物描述标准（英文）</a>
    ·
    <a href="tools/data_importer/">数据导入工具</a>
  </p>
</div>

CropMaestro 是一个面向作物种质资源的多智能体智能检索框架。农业科研人员和育种工作者可以用自然语言描述需求，从种质数据中筛选出符合要求的候选材料。

传统的表单式检索通常要求用户熟悉性状名称、评价尺度和筛选阈值。CropMaestro 将需求理解、性状字段映射、数据库查询和结果解读组织为协同工作流，支持种质数据的多性状、多约束检索，以及相关领域知识问答。

## 界面预览

<table>
  <tr>
    <td align="center" valign="top" width="50%">
      <h3>平台概览</h3>
      <p>了解 CropMaestro。</p>
      <a href="https://github.com/user-attachments/assets/be01baf7-7cfd-46ae-b925-fed9088f7180">
        <img width="440" alt="CropMaestro 平台概览"
             src="https://github.com/user-attachments/assets/be01baf7-7cfd-46ae-b925-fed9088f7180">
      </a>
    </td>
    <td align="center" valign="top" width="50%">
      <h3>智能检索</h3>
      <p>用自然语言检索种质资源。</p>
      <a href="https://github.com/user-attachments/assets/2ae1b5ba-14d1-40da-95fe-5de192a2146f">
        <img width="440" alt="CropMaestro 智能检索界面"
             src="https://github.com/user-attachments/assets/2ae1b5ba-14d1-40da-95fe-5de192a2146f">
      </a>
    </td>
  </tr>
  <tr>
    <td align="center" valign="top" width="50%">
      <h3>模式指南</h3>
      <p>选择模式和数据源。</p>
      <a href="https://github.com/user-attachments/assets/518ee96a-1a77-462e-b936-d3a027d534c9">
        <img width="440" alt="CropMaestro 模式指南"
             src="https://github.com/user-attachments/assets/518ee96a-1a77-462e-b936-d3a027d534c9">
      </a>
    </td>
    <td align="center" valign="top" width="50%">
      <h3>检索结果</h3>
      <p>查看种质材料、结果说明和图表。</p>
      <a href="https://github.com/user-attachments/assets/62f4e6a9-dd93-4737-afb6-5e9ff2702038">
        <img width="440" alt="CropMaestro 检索结果"
             src="https://github.com/user-attachments/assets/62f4e6a9-dd93-4737-afb6-5e9ff2702038">
      </a>
    </td>
  </tr>
</table>

## 模式与演示

### 默认模式

输入自然语言需求后，CropMaestro 会分析需求，生成并执行数据库查询，然后展示返回的种质记录。界面上的状态更新会显示检索任务的进度。

https://github.com/user-attachments/assets/72b2dfd7-8cf8-4c95-a231-50516fdf63ed

### 专家模式

专家模式加入知识增强检索，辅助理解需要领域知识的需求。相关作物描述标准、性状说明和数据源专属知识用于指导将用户需求转换为检索条件。

<details>
<summary>▶ 观看专家模式演示</summary>

https://github.com/user-attachments/assets/92db7152-4d85-49e6-9338-a341c578cdf1

</details>

### 稳健模式

稳健模式通过并发检索智能体生成并执行候选查询。评审智能体将候选结果与用户需求进行比较，选出最终结果。

<details>
<summary>▶ 观看稳健模式演示</summary>

https://github.com/user-attachments/assets/364e14e4-42f2-4765-a4f3-6259c1b64d21

</details>

### 数据源选项

CropMaestro 还提供切换检索数据集的选项：

- **商业品种**：通过自然语言界面检索商业水稻品种数据集。
- **国际数据**：检索当前已集成的、通过 Genesys 获取的 AfricaRice 水稻种质材料记录。此选项仅覆盖已导入的数据集，不涵盖完整的 Genesys 数据库。

查询在所选数据源内执行，使用该数据源对应的字段和检索配置。不同来源的记录不会合并进行联合筛选或排序。

> 截图和视频展示的是托管在线服务，其前端源代码未包含在本仓库中。已发布的工作流示例使用商业水稻数据集，并未包含在线服务提供的全部数据集。

## 框架概览

CropMaestro 采用四层多智能体架构：

- **控制层**：识别用户意图，确定任务类型，并引导用户明确需求。
- **分析层**：识别目标作物，将用户需求映射为对应的数据字段和检索条件。
- **执行层**：生成并执行数据库查询，依据检索策略筛选候选种质记录。
- **解读层**：汇总检索结果，提供性状解读、推荐依据和可视化图表。

<img width="2379" height="1289" alt="CropMaestro 四层多智能体架构" src="https://github.com/user-attachments/assets/daf736ac-1b54-400b-9823-589b9d376688" />


框架通过加载数据源及各作物对应的字段定义、计量单位、类别定义和相关知识，适配不同的检索任务。不同数据源可以复用同一核心工作流，但每次查询均在所选数据源内执行；不同来源的记录不会合并进行联合筛选或排序。

CropMaestro 集成了两种检索策略：

- **知识增强检索**：检索与任务相关的作物描述标准、性状说明和数据源专属知识，辅助将自然语言查询转换为恰当的字段和筛选条件。
- **并发对抗检索**：多个检索智能体并行生成并执行候选查询，再由评估智能体比较各候选结果与用户查询的匹配程度，选出最终结果。

<img width="3152" height="1641" alt="CropMaestro 检索策略" src="https://github.com/user-attachments/assets/9529ea40-5280-47dc-aab4-7bb9c6552447" />



## 评测基准与仓库内容

我们构建了作物种质资源检索评测基准 **[CGR-Bench](cgr_bench/)**，包含五类主要作物的 150 条查询，覆盖三个难度等级，用于评估字段选择、检索条件和返回种质记录的质量。

本仓库提供 n8n 工作流导出文件、**商业水稻（`bus_rice`）**四层提示词、MySQL 表结构和商业品种数据转储文件，以及可复用的数据导入工具。

CGR-Bench 目录提供查询示例和参考标注，但**不包含这五类作物的种质库数据**。因此，仓库中的商业水稻部署示例无法直接完成全部 150 条基准查询；具体使用条件请参阅该目录的说明。

## RSS 评测材料

[RSS 评测包](cgr_bench/rss_evaluation/)提供已冻结的查询级相关性判定、已评分的种质材料输出、归一化数值、排除项，以及无需访问数据库或模型即可复现已报告 RSS 数值的独立 Python 脚本。它还提供相对于已发布汇总参考列表的补充精确率、召回率和 F1 对比。指南说明了评分规则、源自模型的参考条目，以及使用汇总参考列表进行比较的局限。

[中文提示词模板](docs/prompt_templates/)与补充说明中的英文阅读版本配套提供，并区分了 CGR-Bench 材料与当前部署模板。

## 作物描述标准英文译本

作者编译的大麦、玉米、水稻、大豆和小麦作物描述标准英文译本可在[作物描述标准指南](docs/crop_standards/)中获取。这些文档提供与知识增强检索相关的性状术语、计量单位和评价尺度参考信息。指南说明了原始来源和翻译情况，并提供全部五份 PDF 的链接。

## 本仓库可运行的内容

已发布的实现以 **n8n 工作流和数据源配置**为核心，并非独立的 Web 应用。检索由工作流调用模型服务和 MySQL 完成。你可以通过 n8n Webhook 调用主工作流，无需重建托管界面，也可以接入自己的客户端。

- **已包含：**主工作流和并发检索子工作流、商业水稻数据及提示词、SQL 表结构、基准标注、数据导入工具和辅助服务代码。
- **未包含：**托管前端、在线服务的全部数据集、已填充的向量知识索引、GS 预测模型文件或部署凭据。
- **需要配置：**模型端点和 ID、凭据、提示词文件挂载以及子工作流引用均须与你的环境匹配。导出的工作流不能一键部署为托管在线服务。

`backend/status_api.py` 是**进度跟踪辅助服务**，并非智能检索后端。它存储并提供任务状态，供客户端轮询。当前工作流会在执行过程中直接调用该服务，因此需要运行它，或明确绕过回调节点。独立的 GS 预测服务是可选扩展，并非商业水稻文本检索示例的必需组件。

## 快速开始：商业水稻工作流

完整命令、节点配置和故障排查步骤请参阅[工作流配置指南](docs/setup.md)：

1. 克隆仓库，准备自托管的 n8n 实例、MySQL 和计划使用的模型服务。
2. 创建全新的演示数据库，导入[商业水稻数据和运行时表结构](data/README_DATA.md)。数据转储文件会替换 `bus_rice_data`；请勿将其导入已有的生产数据集。
3. 将商业水稻字段说明和提示词准备到 n8n 的 `/data` 挂载目录下，并保留预期的 `Mapping/` 和 `Prompt/` 子目录。
4. 导入[主工作流](workflow/CropMaestro.workflow.json)，配置其中的 MySQL 和模型节点，并按指南处理辅助状态回调和可选日志集成。
5. 如需使用稳健模式，还需导入[并发检索子工作流](workflow/Concurrent%20Adversarial%20Search-Opensource.json)，配置其模型节点，并重新绑定主工作流中的子工作流引用。
6. 使用商业水稻检索请求测试主 Webhook。先设置 `commercialMode: true`、`expertMode: false` 和 `stableMode: false`，待相关依赖准备就绪后，再启用其他策略。

导出的工作流使用 `expertMode` 启用知识增强，使用 **`stableMode` 启用稳健模式**。这些字段位于请求的 `config` 对象中；`query.chatInput` 包含问题，`context.sessionId` 标识会话。请参阅[完整请求示例](docs/setup.md#7-call-the-workflow-through-its-webhook)。

如需使用自定义数据集，请先使用[数据导入工具](tools/data_importer/)，再配置相应的工作流路由和提示词路径。导入数据集不会自动配置 n8n，也不会创建向量知识索引。

## 目录概览

| 目录 | 说明 |
|------|------|
| `workflow/` | 主 n8n 工作流和并发检索子工作流导出文件 |
| `prompts/bus_rice/` | 商业水稻四层提示词 |
| `schema/` | 运行时表 DDL 和合并的演示数据库表结构参考 |
| `data/` | `bus_rice_data.sql` 商业品种数据 |
| `cgr_bench/` | CGR-Bench 金标准数据集（150 个问题、五类作物；请注意其范围与开源数据不同） |
| `backend/` | 辅助任务状态 API 和可选的 GS 预测服务；并非检索引擎 |
| `docs/` | 工作流架构、配置、部署说明和[作物描述标准英文译本](docs/crop_standards/) |
| [`tools/data_importer/`](tools/data_importer/) | 可复用的数据导入工具：CSV/TSV/XLSX 数据概况分析、数据源专属提示词和无重叠的 MySQL 导入；包含英文文档和合成示例 |

## 数据导入工具

[`tools/data_importer/`](tools/data_importer/)提供可复用的数据导入工具，以及安装、配置和测试说明。该工具接收已获取的表格数据，生成数据源专属导入包，并支持将数据发布到已配置的 MySQL 数据库。它不会自动从外部平台获取数据、修改现有 n8n 工作流，也不会执行跨数据源的数据协调或自动同步。数据源语义和工作流连接仍需配置。该目录仅提供源代码、测试和合成示例，不包含真实种质记录或部署凭据。

## 许可证

数据导入工具 [`tools/data_importer/`](tools/data_importer/)（包括该目录中的文档、测试和合成示例）采用 [MIT 许可证](tools/data_importer/LICENSE)。版权所有 © 2026 Bintao Pan。此许可证不适用于仓库中的其他目录，也不授予使用外部种质数据或其他第三方数据的权利；第三方依赖受各自许可证约束。
