# Workflow Setup

This guide configures the released n8n workflows against the commercial rice dataset (`bus_rice`). The retrieval engine is the **n8n multi-agent workflow**, together with model services, MySQL, and source-specific prompts. It is not `backend/status_api.py`.

The hosted website's frontend is not included. Use a Webhook client to exercise the workflow, or supply your own UI. The release also does not contain all hosted-service datasets, a populated vector knowledge index, or GS prediction model artifacts.

## 1. Prepare the environment

You need:

- A self-hosted n8n instance that can use the exported AI, MySQL, HTTP Request, and local-file nodes. Review node compatibility in your installed version before publishing; the repository does not pin an n8n release.
- MySQL 8.0 compatible with the included dump, and a new database for the demo.
- Access to the LLM endpoints you choose, including their model IDs and credentials.
- A directory visible to n8n as `/data`, containing the files prepared below.
- Python and the status API dependencies if retaining the exported progress callbacks. Python is not the workflow execution engine.

For n8n installation, use the [official self-hosting documentation](https://docs.n8n.io/hosting/installation/). The file paths below target self-hosting; they are not an unchanged n8n Cloud deployment recipe.

```bash
git clone https://github.com/Qianlvdouhua/cropmaestro.git
cd cropmaestro
```

Unless stated otherwise, shell examples use Bash on Linux/macOS and run from the repository root. On Windows, adapt commands to your shell; use `curl.exe` rather than a PowerShell alias when running curl examples.

## 2. Create a fresh database and import the demo

**The dump contains `DROP TABLE IF EXISTS bus_rice_data`. It replaces that table and its records. Do not run it against an existing production dataset or treat it as an incremental import.**

First create a new database. If it already exists, stop and choose another name before importing. Use the same name in every command and runtime connection.

```bash
mysql -u root -p -e "CREATE DATABASE cropmaestro_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
```

Only after successful creation, import:

```bash
mysql -u root -p cropmaestro_demo < data/bus_rice_data.sql
mysql -u root -p cropmaestro_demo < schema/ddl/00_chat_memory.sql
mysql -u root -p cropmaestro_demo < schema/ddl/02_bus_rice_cache_results.sql
mysql -u root -p cropmaestro_demo < schema/ddl/03_request_status.sql
mysql -u root -p cropmaestro_demo -e "SHOW TABLES; SELECT COUNT(*) AS record_count FROM bus_rice_data;"
```

Do not additionally import `01_bus_rice_data.sql` for this path: the dump already creates the data table. That DDL is provided for schema-only use.

The runtime uses `bus_rice_data` for records, `bus_rice_cache_results` for query results, `chat_memory` for conversation/query metadata, and `request_status` for progress tracking. Configure a dedicated application account with the permissions required by those operations rather than using the administrative import account at runtime. See [data scope and import notes](../data/README_DATA.md).

## 3. Prepare field descriptions and prompt files

The workflow reads filenames derived from the selected source. For commercial rice, `crop` maps rice to `bus_rice` when `commercialMode` is true. Mounting the repository's prompt directory alone does not reproduce the expected layout.

In a fresh checkout, prepare a staging directory:

```bash
mkdir -p runtime-data/Mapping runtime-data/Prompt/rule runtime-data/Prompt/unit
cp prompts/bus_rice/control/bus_rice_data.txt runtime-data/bus_rice_data.txt
cp prompts/bus_rice/control/bus_rice_cache_results.txt runtime-data/bus_rice_cache_results.txt
cp prompts/bus_rice/control/chat_memory.txt runtime-data/chat_memory.txt
cp prompts/bus_rice/control/request_status.txt runtime-data/request_status.txt
cp prompts/bus_rice/analysis/bus_rice_mapping_data.txt runtime-data/Mapping/bus_rice_mapping_data.txt
cp prompts/bus_rice/execution/bus_rice_score_prompt.txt runtime-data/Prompt/bus_rice_score_prompt.txt
cp prompts/bus_rice/execution/bus_rice_conditional_prompt.txt runtime-data/Prompt/bus_rice_conditional_prompt.txt
cp prompts/bus_rice/interpretation/bus_rice_rule.txt runtime-data/Prompt/rule/bus_rice_rule.txt
cp prompts/bus_rice/interpretation/bus_rice_unit.txt runtime-data/Prompt/unit/bus_rice_unit.txt
cp schema/schema_bus_rice_demo.txt runtime-data/hrmshcema.txt
```

Mount the **contents of `runtime-data/` at `/data` inside n8n**. For Docker, add a bind mount equivalent to `--mount type=bind,source=/absolute/path/to/runtime-data,target=/data` to your n8n deployment. This is separate from n8n's own application-state directory. Confirm that the n8n process can read the files and that its file-access restrictions permit this directory; see the [n8n local-file node documentation](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.readwritefile/).

- `table_structure` reads `/data/bus_rice_data.txt` for this source.
- `read_mapping` reads `/data/Mapping/bus_rice_mapping_data.txt`.
- Execution prompts are under `/data/Prompt/`.
- Interpretation rules and units are under `/data/Prompt/rule/` and `/data/Prompt/unit/`.
- `/data/hrmshcema.txt` is a separate combined schema reference. It does not replace `/data/bus_rice_data.txt`.

The main workflow also contains a manual schema-export branch (`When clicking ‘Test workflow’` → `MySQL9` → `Code1` → `Read/Write Files from Disk6`). It can generate per-table descriptions after its connection and write permissions are configured. The static files above prepare the shipped source without running that branch. Do not run schema-export writers over customized files without reviewing the destinations.

The data-import tool's `deploy-prompts` command documents a host-side destination of `/data/n8n_data/`. Map that directory to the workflow's container-side `/data`, or deliberately update the node paths. Host and container paths are not interchangeable.

## 4. Import the workflows and resolve references

1. Import [CropMaestro.workflow.json](../workflow/CropMaestro.workflow.json) into n8n.
2. For Robust mode, also import [Concurrent Adversarial Search-Opensource.json](../workflow/Concurrent%20Adversarial%20Search-Opensource.json).
3. In the main workflow, open `Call 'socre_query'` and select your imported concurrent-search workflow. The exported ID belongs to the original instance. Preserve the input mappings expected by the sub-workflow trigger.
4. Review `Call 'Save process'`. Its logging workflow is **not included**. Supply a compatible replacement, or bypass this call and verify the downstream expressions. Do not leave its original workflow ID unresolved on a branch you intend to run.
5. Review other optional integrations, such as Notion and the GS branch, before using them. They are not required to demonstrate commercial rice text retrieval.

Keep the workflow unpublished while configuring it. Importing files does not provide credentials, valid local workflow IDs, or reachable model endpoints.

## 5. Configure MySQL and model calls

### MySQL

Bind the intended MySQL credentials to **all MySQL nodes and SQL tools used by your selected path**, in both workflows. Confirm database names, cache tables, and source prefixes. In a container, `localhost` refers to that container, not the host's MySQL server.

### Model services

The exports contain both AI model nodes and ordinary HTTP Request nodes:

- For AI model nodes, select your credential/provider connection and a supported model ID.
- For HTTP model calls, check the full URL, authentication, request body, and `model` field. Binding credentials elsewhere does not rewrite a node's URL or model name.
- Review `LLM_Name` and nodes referencing it. Its value must match the service receiving each request.
- In the main workflow, `Conditional Query` and `Explanation of Global Information` point to `http://localhost:5678/v1/chat/completions`. Replace these with your actual model endpoint; the n8n Webhook service is not an LLM endpoint.
- In the concurrent-search sub-workflow, `Score Query` needs a URL, model ID, and any required authentication. `Summary of Recommended Resources` also needs your endpoint/model instead of the original private-network configuration.
- Replace local-model placeholders such as `/data/models/<YOUR_LOCAL_LLM>` with IDs valid for your serving setup when those nodes are used.

Do not publish API keys, credential exports, or private connection settings. Repository `.env.example` values do not automatically configure n8n credentials.

## 6. Handle progress callbacks

`backend/status_api.py` stores/exposes task status and confirmation information. It does not accept a retrieval question and run CropMaestro. Retrieval requests go to n8n.

The current main workflow contains inline HTTP callbacks to `http://host.docker.internal:5000/api/status`. Choose an integration approach:

- **Keep progress tracking:** run the [status helper](../backend/README.md#status-api), configure its database/environment, and make its address reachable from n8n. Update callback URLs for your hostname/port. No frontend is needed to receive the final workflow response.
- **Use a client without progress tracking:** deliberately bypass the status callback nodes and check downstream input expressions. Simply stopping the service is not enough: callbacks are in the execution chain and are not configured to ignore connection failures. Confirmation-related branches need an explicit alternative if used.

For Docker Desktop, `host.docker.internal` normally addresses the host. On Linux or other container deployments, configure a suitable host gateway or service-network hostname. The status service, MySQL, and LLM endpoints may need different addresses.

## 7. Call the workflow through its Webhook

The main workflow has a **POST** Webhook with path:

```text
v0.6.0/cropmaestro_deepseek
```

Copy the Test URL shown by the `Webhook` node in **your n8n instance**, including any reverse-proxy prefix. A typical local URL is:

```text
http://localhost:5678/webhook-test/v0.6.0/cropmaestro_deepseek
```

Select **Listen for test event** before calling it. After testing, publish/activate the workflow as required by your n8n version and use the node's Production URL, typically containing `/webhook/` instead of `/webhook-test/`. See [n8n Webhook documentation](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/).

Start with commercial rice retrieval without additional strategies:

```json
{
  "config": {
    "commercialMode": true,
    "expertMode": false,
    "stableMode": false,
    "internationalMode": false
  },
  "context": {
    "sessionId": "demo-bus-rice-001",
    "userType": "B"
  },
  "query": {
    "chatInput": "查询全生育期不超过120天的水稻商业品种"
  }
}
```

For example, after entering the test-listening state:

```bash
curl --request POST \
  'http://localhost:5678/webhook-test/v0.6.0/cropmaestro_deepseek' \
  --header 'Content-Type: application/json' \
  --data '{"config":{"commercialMode":true,"expertMode":false,"stableMode":false,"internationalMode":false},"context":{"sessionId":"demo-bus-rice-001","userType":"B"},"query":{"chatInput":"查询全生育期不超过120天的水稻商业品种"}}'
```

If you configure Webhook authentication, include the corresponding credentials in your client. Keep a session ID for follow-up questions and use a new one for an independent conversation. Send mode flags as JSON booleans, not quoted strings.

The Webhook uses response nodes. Inspect the actual response and execution trace: branches return different structures, so this guide does not promise a single frontend-ready response schema or a particular retrieved variety. A successful `/health` or status update proves only that the status helper is reachable, not that retrieval works.

Before exposing a deployment, require appropriate authentication and network controls for the Webhook, status endpoints, and databases. The sample status API is not an authenticated public-facing service.

## 8. Enable strategies and additional sources

### Default, Expert, and Robust

- **Default:** `expertMode: false`, `stableMode: false`.
- **Expert:** `expertMode: true`, `stableMode: false`, after preparing the vector dependencies below.
- **Robust:** `expertMode: false`, `stableMode: true`, after configuring and rebinding the concurrent-search sub-workflow. The exported field is `stableMode`, not `robustMode`.

Keep `commercialMode: true` for the shipped commercial rice example. Strategy flags and data-source flags serve different purposes. Configure and verify one strategy at a time before attempting combinations.

### Knowledge-enhanced retrieval

Vector nodes select a Qdrant collection from `cropEn`; commercial rice therefore uses `bus_rice`. Prepare the matching field-level knowledge texts, embed/index them, and configure Qdrant and the embedding endpoint. The export includes Ollama embedding nodes referencing `qwen3-embedding-8b-f16:latest`; use an available, compatible configuration and keep indexing and query embedding models consistent.

The repository does not supply a populated collection or an automatic end-to-end index-building procedure. Installing Qdrant or binding its credential alone does not enable Expert mode. The [data-import tool](../tools/data_importer/) also does not populate Qdrant.

### Other data sources

Use the [data-import tool](../tools/data_importer/) to prepare permitted tabular datasets, inspect their field semantics, and publish source-specific tables and prompt packages. Then configure routing, table names, prompt prefixes, and any knowledge index in n8n. Propagate a new dataset prefix through the relevant nodes; updating `cropMap` alone is not sufficient.

The hosted international-data option uses an imported dataset. Setting `internationalMode` does not download Genesys data or supply missing tables/prompts. Keep it false for this example. Different sources are not automatically reconciled or jointly ranked.

The [CGR-Bench annotations](../cgr_bench/) cover five crops, but their underlying germplasm databases are not included. The commercial rice example cannot directly reproduce all 150 benchmark queries.

### GS prediction extension

The [GS service](../backend/README.md#optional-gs-prediction-service) is separate from text-based germplasm retrieval and requires model artifacts that are not distributed. It is not needed for the request above.

## Troubleshooting checklist

- **No website appears:** the frontend is not released. Call the n8n Webhook or connect your own client.
- **Port 5000 responds but retrieval does not run:** that port is the status helper. Use the n8n Webhook for retrieval requests.
- **Webhook not registered:** listen for a test event with the Test URL, or publish/activate the workflow and use its Production URL.
- **Prompt file not found:** check container-side paths, filenames, permissions, and file-access restrictions. Confirm that `bus_rice_data.txt` exists, not just `hrmshcema.txt`.
- **Sub-workflow not found:** rebind `Call 'socre_query'`; resolve or bypass the unreleased `Call 'Save process'` integration.
- **LLM request fails:** inspect that node's endpoint, authentication, model ID, and request body. Replace original local/private addresses and blank configuration.
- **Status callback fails:** start the reachable helper or correctly bypass callbacks. Copying `.env.example` without loading/exporting values does not configure the Python process.
- **Expert mode fails:** check that the source's knowledge collection is populated and that its vectors match the query embedding setup.
- **Wrong-source table selected:** verify crop recognition and `commercialMode: true`; inspect the `crop` node's `cropEn` and `datatable` outputs.

These instructions describe configuration required by the released source. Runtime success still needs validation against your own n8n version, credentials, data, and model services.
