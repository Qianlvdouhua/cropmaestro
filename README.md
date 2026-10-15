<div align="center">
  <img width="2172" height="724" alt="image" src="https://github.com/user-attachments/assets/be8722c5-8b84-4554-a762-204744847d5f" />

  <h1>CropMaestro: Germplasm intelligence,<br>unlocked for everyone.</h1>

  <p>A multi-agent framework for natural-language crop germplasm retrieval.</p>

  <p>
    <a href="https://github.com/Qianlvdouhua/cropmaestro/stargazers">
      <img src="https://img.shields.io/github/stars/Qianlvdouhua/cropmaestro" alt="GitHub stars">
    </a>
    <a href="https://github.com/Qianlvdouhua/cropmaestro/forks">
      <img src="https://img.shields.io/github/forks/Qianlvdouhua/cropmaestro" alt="GitHub forks">
    </a>
  </p>

  <p>
    <a href="http://122.9.8.16/">Online Demo</a>
    ·
    <a href="docs/setup.md">Installation</a>
    ·
    <a href="cgr_bench/">CGR-Bench</a>
    ·
    <a href="tools/data_importer/">Data-import Tool</a>
  </p>
</div>
CropMaestro is a multi-agent intelligent retrieval framework designed for crop germplasm resources. It helps agricultural researchers and breeders identify candidate materials that meet their requirements from germplasm data by describing their needs using natural language.

Traditional form-based retrieval typically requires users to be familiar with trait names, evaluation scales, and screening thresholds. CropMaestro organizes requirement understanding, trait-field mapping, database queries, and result interpretation into a collaborative workflow, supporting multi-trait, multi-constraint searches of germplasm data as well as Q&A regarding relevant domain expertise.

## 🌐 Interface Preview

<table>
  <tr>
    <td align="center" valign="top" width="50%">
      <h3>Platform Overview</h3>
      <p>Discover CropMaestro and its main functions.</p>
      <a href="https://github.com/user-attachments/assets/be01baf7-7cfd-46ae-b925-fed9088f7180">
        <img width="440" alt="CropMaestro platform overview"
             src="https://github.com/user-attachments/assets/be01baf7-7cfd-46ae-b925-fed9088f7180">
      </a>
    </td>
    <td align="center" valign="top" width="50%">
      <h3>Intelligent Retrieval</h3>
      <p>Describe your germplasm requirements in natural language.</p>
      <a href="https://github.com/user-attachments/assets/2ae1b5ba-14d1-40da-95fe-5de192a2146f">
        <img width="440" alt="CropMaestro intelligent retrieval interface"
             src="https://github.com/user-attachments/assets/2ae1b5ba-14d1-40da-95fe-5de192a2146f">
      </a>
    </td>
  </tr>
  <tr>
    <td align="center" valign="top" width="50%">
      <h3>Mode Guide</h3>
      <p>Explore available modes and data-source options.</p>
      <a href="https://github.com/user-attachments/assets/518ee96a-1a77-462e-b936-d3a027d534c9">
        <img width="440" alt="CropMaestro mode guide"
             src="https://github.com/user-attachments/assets/518ee96a-1a77-462e-b936-d3a027d534c9">
      </a>
    </td>
    <td align="center" valign="top" width="50%">
      <h3>Retrieval Results</h3>
      <p>Review candidate accessions, explanations, and visualizations.</p>
      <a href="https://github.com/user-attachments/assets/62f4e6a9-dd93-4737-afb6-5e9ff2702038">
        <img width="440" alt="CropMaestro retrieval results"
             src="https://github.com/user-attachments/assets/62f4e6a9-dd93-4737-afb6-5e9ff2702038">
      </a>
    </td>
  </tr>
</table>

## 🎬 Modes and Demonstrations

### Default Mode

Start with a natural-language request. CropMaestro analyzes your requirements, generates and executes database queries, and presents the returned germplasm records. On-screen status updates show the progress of the retrieval task.

https://github.com/user-attachments/assets/72b2dfd7-8cf8-4c95-a231-50516fdf63ed

### Expert Mode

Expert mode adds knowledge-enhanced retrieval to help interpret requests that require domain-specific information. Relevant crop standards, trait explanations, and source-specific knowledge guide the translation of user requirements into retrieval conditions.

<details>
<summary>▶ Watch the Expert Mode demonstration</summary>
  
https://github.com/user-attachments/assets/92db7152-4d85-49e6-9338-a341c578cdf1

</details>

### Robust Mode

Robust mode uses concurrent retrieval agents to generate and execute candidate queries. A review agent compares the candidates against the user’s requirements and selects the final result.

<details>
<summary>▶ Watch the File Mode demonstration</summary>
  
https://github.com/user-attachments/assets/364e14e4-42f2-4765-a4f3-6259c1b64d21

</details>

### Data-Source Options

CropMaestro also provides options for switching the dataset used for retrieval:

- **Commercial Varieties**: Search the commercial rice variety dataset through the natural-language interface.
- **International Data**: Search the currently integrated AfricaRice rice accession records obtained through Genesys. This option covers the imported dataset, rather than the complete Genesys database.

Queries are executed within the selected data source, using its corresponding fields and retrieval configuration. Records from different sources are not combined for joint filtering or ranking.

> The screenshots and videos demonstrate the online service. The deployment example provided in this repository uses the commercial rice dataset and does not include all datasets available through the online service.
## Framework Overview

CropMaestro employs a four-layer multi-agent architecture:

- **Control Layer**: Identifies user intent, determines task type, and guides users to clarify their requirements.
- **Analysis Layer**: Identifies the target crop and maps user requirements to corresponding data fields and search criteria.
- **Execution Layer**: Generates and executes database queries, filtering candidate germplasm records based on search strategies.
- **Interpretation Layer**: Summarizes search results, providing trait interpretations, rationale for recommendations, and visualizations.
  
<img width="2386" height="1269" alt="Figure1" src="https://github.com/user-attachments/assets/fcb4d310-4a49-4b2f-9061-d5c7597201a5" />


The framework adapts to different search tasks by loading data sources along with the corresponding field definitions, units of measurement, category definitions, and related knowledge for each crop. Different data sources can reuse the same core workflow, but each query is executed within the selected data source; records from different sources are not merged for combined filtering or sorting.

CropMaestro integrates two search strategies:

- **Knowledge-Enhanced Search**: Retrieves task-relevant crop standards, trait explanations, and data source-specific knowledge to assist in converting natural language queries into appropriate fields and filter criteria.
- **Concurrent Adversarial Search**: Multiple search agents generate and execute candidate queries in parallel; an evaluation agent then compares their alignment with the user’s query to select the final result.

<img width="2487" height="1319" alt="figure3" src="https://github.com/user-attachments/assets/a4dd3b41-5b4e-408d-8e4c-17fc8bf372e7" />



## Evaluation Benchmark and Repository Contents
We have developed the Crop Germplasm Resource Retrieval Evaluation Benchmark **[CGR-Bench](cgr_bench/)**, which includes 150 queries across five major crop types and covers three difficulty levels. It is designed to evaluate the quality of field selection, retrieval criteria, and returned germplasm records.

This repository provides an anonymized n8n workflow, **commercial rice (`bus_rice`)** four-level prompts, MySQL table structures, scripts for importing commercial variety data, and reusable data integration tools.

The CGR-Bench directory provides query examples and reference annotations, but **does not include germplasm repository data for the five crop types**. Therefore, the commercial rice deployment example in the repository cannot be used directly to complete all 150 benchmark queries; see the directory description for specific usage conditions.

## Quick Start

1. Run [schema/ddl](schema/ddl) and import [data/bus_rice_data.sql](data/bus_rice_data.sql)
2. Start [backend/](backend/) (Status API 5000; optional GS API 8000)
3. Follow [docs/setup.md](docs/setup.md) to mount `prompts/bus_rice/` to n8n `/data`
4. Import [workflow/CropMaestro.workflow.json](workflow/CropMaestro.workflow.json) and bind MySQL / LLM credentials
5. Set `“commercialMode”: true` when calling the webhook (commercial rice repository branch)

## Directory Overview

| Directory | Description |
|------|------|
| `workflow/` | n8n JSON |
| `prompts/bus_rice/` | Four-layer prompts for commercial rice |
| `schema/` | DDL + `schema_bus_rice_demo.txt` |
| `data/` | `bus_rice_data.sql` commercial variety data |
| `cgr_bench/` | CGR-Bench Gold Standard Dataset (150 questions, five crops; note that the scope differs from open-source data) |
| `backend/` | State Synchronization and GS Prediction Service |
| `docs/` | Architecture and Deployment |
| [`tools/data_importer/`](tools/data_importer/) | Reusable data import tools: CSV/TSV/XLSX profiling, source-specific prompts, and non-overlapping MySQL imports; includes English documentation and synthetic examples |

## Data Import Tool

[`tools/data_importer/`](tools/data_importer/) provides reusable data import tools along with installation, configuration, and testing instructions. The tool accepts acquired tabular data, generates source-specific import packages, and supports publishing data to a configured MySQL database. It does not automatically retrieve data from external platforms, modify existing n8n workflows, or perform cross-source data reconciliation or automatic synchronization. Source semantics and workflow connections still require configuration. This directory provides only source code, tests, and synthetic examples; it does not contain actual germplasm records or deployment credentials.

The reusable [data-import tool](tools/data_importer/) includes source code, tests, and an English usage guide. It prepares source-specific retrieval packages from tabular datasets and supports non-overwriting publication to a configured MySQL deployment. The included example is synthetic; no additional germplasm records or deployment credentials are distributed with the tool.

## Citation

If you use this framework in your research, please cite this research paper (DOI:).

## License

The data import tool [`tools/data_importer/`](tools/data_importer/) (including the documentation, tests, and synthetic examples in this directory) is licensed under the [MIT License](tools/data_importer/LICENSE). Copyright © 2026 Bintao Pan. This license does not apply to other directories in the repository and does not grant the right to use external germplasm data or other third-party data; third-party dependencies are subject to their respective licenses.

