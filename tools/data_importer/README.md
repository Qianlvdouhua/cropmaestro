# CropMaestro data-import tool

Version 0.3.0. This tool prepares crop- and source-specific retrieval packages from CSV, TSV, or XLSX data and supports non-overwriting publication to an existing MySQL deployment. It is the data-import component used when adapting CropMaestro to additional datasets.

The tool does **not** download data from external PGR systems, grant access to restricted records, harmonize measurements across sources, or provide automatic synchronization. Obtain the data and permission to use them before importing them. Source-specific semantic information and runtime workflow connections still require configuration.

Only source code, tests, a blank configuration template, and a four-record **synthetic** example are provided here. The example values are not germplasm observations or agronomic recommendations. Production configuration, real data, credentials, and historical deployment reports are excluded.

## Installation

Use Python 3.11 or newer. Run from this directory in an activated virtual environment:

```sh
python -m pip install -r requirements.txt
```

Alternatively, `python -m pip install .` installs the `cropmaestro-import` command. The examples below use `python -m cm_importer`, which exposes the same interface. CLI messages and generated prompt templates currently include Chinese text; database identifiers are retained from the input.

## Quick start: offline preparation

No database, API key, or model service is required for this example:

```sh
python -m cm_importer prepare examples/synthetic_rice.csv --crop rice --dataset-prefix demo_rice --offline --out outputs/demo_rice
python -m cm_importer verify outputs/demo_rice
```

This prepares and verifies a local package; it does not import anything into MySQL or deploy an online retrieval service. Without source annotations or a configured model, preparation uses conservative field-label inference. Missing units and category meanings must not be invented.

The package contains a data profile, serialized rows, a manifest with integrity hashes, and seven prompt files:

```text
outputs/demo_rice/
  profile.json
  rows.jsonl
  manifest.json
  prompts/
    demo_rice_data.txt
    demo_rice_cache_results.txt
    demo_rice_mapping_data.txt
    demo_rice_conditional_prompt.txt
    demo_rice_score_prompt.txt
    demo_rice_rule.txt
    demo_rice_unit.txt
```

For your own input, choose one crop per file and a distinct dataset prefix for each source. The crop identifies the crop context; the prefix names the source-specific tables and prompt files. `--sheet` selects an XLSX worksheet and `--encoding` selects a non-default CSV encoding. Spreadsheet formulas are not evaluated; supply value-only data.

## Source-specific interpretation

The tool calculates counts, missing values, observed categories, and numerical summaries from the input. These describe the supplied dataset; they are not universal trait thresholds or optimal breeding values.

Two optional inputs can enrich preparation:

- `--annotations annotations.json`: source-bound field labels, aliases, definitions, units with evidence, and descriptor information. The file is tied to the input SHA-256. Schema validation is implemented in `cm_importer/annotations.py`; small synthetic examples are exercised in `tests/test_annotations.py` and `tests/test_annotation_integration.py`.
- `--evaluation-policy policy.json`: explicit target-to-field preferences and ordered-category or quantile-based scoring policies, also bound to the source hash. The tool calculates numerical cutoffs rather than accepting invented statistics. Validation is implemented in `cm_importer/evaluation.py`, with examples in `tests/test_evaluation.py`. Preferences still require domain review; quantiles do not establish agronomic optima.

An optional model can provide bounded field-semantic annotations through a configured chat-completions endpoint. Set `llm.enabled`, `llm.base_url`, and the actual served `llm.model` in your local config. Use `llm.api_key_env` for the name of an environment variable containing the key. With a model enabled, field metadata, statistics, and limited non-identifier examples may be sent to that endpoint; use it only when authorized to transmit those data. `--offline` disables model calls. Offline annotations and enabled model annotation are not combined.

The importer does not automatically populate Qdrant or build a complete knowledge-enhanced retrieval deployment. Review source definitions and configure any vector knowledge materials and workflow routing separately.

## MySQL configuration and publication

Copy `config.example.json` to a local `config.json` and configure the existing database, host, port, and user. The example is intentionally not ready to publish. The database and the compatible shared `chat_memory` table must already exist.

Credentials are read from environment variables identified by `mysql.password_env` and, if needed, `llm.api_key_env`. Never put actual passwords or keys in the JSON file or commit local configuration. Remote database connections require a configured `mysql.ssl_ca` for certificate verification unless a trusted private network has been explicitly configured. Do not send database credentials over an untrusted plaintext connection.

`template_cache_table` identifies an existing cache table whose metadata contract is inspected without copying its data. If there is no suitable template, set this option to null and explicitly configure and confirm `cache_contract` after checking the runtime workflow. Inspect the target before publication:

```sh
python -m cm_importer inspect --config config.json
```

To prepare and publish a dataset using that configuration:

```sh
python -m cm_importer run /path/to/source.csv --crop rice --dataset-prefix source_rice --offline --config config.json
```

Alternatively, use `prepare` with a compatible configured cache contract, verify the resulting package, and then run:

```sh
python -m cm_importer apply /path/to/prepared-package --config config.json
```

Publication creates `<prefix>_data` and an initially empty `<prefix>_cache_results`. Existing tables belonging to a different package are not overwritten. Repeating publication of the same package verifies the existing data rather than resetting runtime cache contents. The tool does not modify the shared `chat_memory` schema. Database permissions must cover the operations performed by the importer, including staging and renaming tables; scope permissions to the intended deployment.

Different input data under an existing prefix are not treated as an automatic update. Plan data-version changes and affected metadata/configuration updates separately. Interrupted publication may leave staging objects; inspect the reported state before any manual cleanup.

## Prompt deployment and runtime integration

Preview placement of a reviewed seven-file prompt set without modifying the destination:

```sh
python -m cm_importer deploy-prompts /path/to/reviewed-prompts --dataset-prefix source_rice
```

On the Linux environment that owns the n8n prompt filesystem, add `--apply` to publish the files. The fixed target layout is:

```text
/data/n8n_data/<prefix>_data.txt
/data/n8n_data/<prefix>_cache_results.txt
/data/n8n_data/Mapping/<prefix>_mapping_data.txt
/data/n8n_data/Prompt/<prefix>_conditional_prompt.txt
/data/n8n_data/Prompt/<prefix>_score_prompt.txt
/data/n8n_data/Prompt/rule/<prefix>_rule.txt
/data/n8n_data/Prompt/unit/<prefix>_unit.txt
```

Confirm the container mounts and permissions first. This command does not use SSH or configure mounts. Files are copied without rewriting their contents; differing existing targets are rejected rather than overwritten. Publication is per file, not a transaction across all seven files. Successful copying is not an end-to-end workflow test.

Configure the n8n data-source routing, table names, prompt prefixes, and connections for the new source, and validate representative queries before making it available to users. The importer does not edit existing n8n workflows automatically.

## Tests

Run from this directory:

```sh
python -m unittest discover -s tests -v
```

Tests use synthetic fixtures. Some model-interface tests start a loopback HTTP server; they do not call an external model. MySQL integration tests are opt-in: without `CM_MYSQL_TEST_CONFIG`, they are skipped. If enabled, the configured database must be the isolated `cm_onboarding_test` database. Integration tests create database objects and must never be pointed at production.

## Scope and limitations

- The tool prepares source-specific inputs; metadata quality still requires review.
- It does not guarantee correct LLM-generated queries or replace end-to-end retrieval validation.
- Preparation loads the dataset into memory and is intended for small-to-medium research tables. Large-scale ingestion has not been established by this release.
- The supplied code does not implement periodic downloads, incremental synchronization, or cross-source phenotypic harmonization.
- Source data, generated packages, and configuration may contain sensitive information. Do not commit them without review and the appropriate permission.
