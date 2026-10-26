# Data Scope and Import

The released workflow example uses the **commercial rice** source (`bus_rice`). It does not contain all datasets available in the hosted service.

## Included data and schemas

- [bus_rice_data.sql](bus_rice_data.sql): commercial variety records and their table definition, distributed as a complete MySQL dump.
- [01_bus_rice_data.sql](../schema/ddl/01_bus_rice_data.sql): a schema-only alternative, not an additional step when using the dump.
- [02_bus_rice_cache_results.sql](../schema/ddl/02_bus_rice_cache_results.sql): runtime cache table definition, without precomputed results.
- [00_chat_memory.sql](../schema/ddl/00_chat_memory.sql): conversation and query-metadata table definition.
- [03_request_status.sql](../schema/ddl/03_request_status.sql): progress/confirmation table definition.
- [CGR-Bench](../cgr_bench/): five-crop queries and reference annotations, **not the underlying five-crop germplasm databases**. The commercial rice example cannot directly answer the entire benchmark.

The hosted frontend, international dataset, populated knowledge indexes, and deployment credentials are not distributed with this example. The import tool includes only synthetic records in its own examples directory.

## Import into a fresh database

**The dump drops and recreates `bus_rice_data`. It is not an incremental import. Do not run it against an existing production dataset.** Back up relevant data before considering any import into an environment that already contains records.

Run these Bash examples from the repository root. First create a new database:

```bash
mysql -u root -p -e "CREATE DATABASE cropmaestro_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
```

If it already exists, stop and choose a different name. Only after successful creation, import:

```bash
mysql -u root -p cropmaestro_demo < data/bus_rice_data.sql
mysql -u root -p cropmaestro_demo < schema/ddl/00_chat_memory.sql
mysql -u root -p cropmaestro_demo < schema/ddl/02_bus_rice_cache_results.sql
mysql -u root -p cropmaestro_demo < schema/ddl/03_request_status.sql
mysql -u root -p cropmaestro_demo -e "SHOW TABLES; SELECT COUNT(*) AS record_count FROM bus_rice_data;"
```

The dump originates from MySQL 8.0 and uses `utf8mb4_0900_ai_ci`. Verify compatibility before import. Creating tables does not configure n8n credentials or model services.

## Match the data to the workflow

- Send a rice question with `config.commercialMode: true` so the `crop` node selects `bus_rice` and `bus_rice_data`.
- Prepare `prompts/bus_rice/control/bus_rice_data.txt` as `/data/bus_rice_data.txt` inside n8n. It is distinct from the combined `/data/hrmshcema.txt` reference.
- Keep mapping, execution, interpretation, and cache field descriptions aligned with the tables. Follow [Workflow Setup](../docs/setup.md) for the file layout and Webhook example.
- Prepare the source's vector knowledge collection separately for Expert mode. A populated index is not included in the SQL dump.

For permitted datasets of your own, see the [data-import tool](../tools/data_importer/). It supports source-specific preparation and non-overwriting MySQL publication, but does not automatically configure n8n, acquire external data, populate Qdrant, or harmonize different sources.

## Data-use conditions

Check applicable data-provider and institutional terms before redistribution or deployment. The import tool's MIT license does not extend to external germplasm data or grant rights over other repository contents. Each request uses its selected source; the example does not provide cross-source joint filtering or ranking.
