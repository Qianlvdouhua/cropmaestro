# Model artifacts (not included in public repo)

Place trained files here before starting the GS API, for example:

- `*_model_best.pt`
- `*_scaler.pkl`

The n8n workflow calls `POST /predict_phenotype_text` on port **8000**. Without these files, prediction endpoints return HTTP 500 until models are configured.
