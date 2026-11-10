# Chinese-language prompt templates

These files contain the Chinese-language reference templates corresponding to the English reading versions in the CropMaestro Supplementary Note. The original supplement section numbers are retained for cross-references.

## CGR-Bench materials

- [Shared crop context (Section 2.1)](shared_crop_context.zh.txt) contains the schemas and field rules for barley, maize, rice, soybean, and wheat.
- [Baseline prompt templates (Section 2.2)](baseline_templates.zh.txt) contains the Chinese prompt blocks and shared-context wrapper. Section 1.2 of the Supplementary Note contains the native English framework instructions, placeholders, and message assembly details.

## Current CropMaestro service

- [CropMaestro agent templates (Section 2.3)](cropmaestro_deployment.zh.txt) describes the four-layer workflow in the current service.
- [Crop-specific dynamic materials (Section 2.4)](deployment_crop_context.zh.txt) provides terminology mappings and additional retrieval rules for that service.

CGR-Bench used Chinese queries and crop-specific context. Sections 2.3–2.4 describe the current deployment, including its international-data mode and five-record output limit. These are publication reference copies. Sensitive statistics, data-derived thresholds, and physical table or workflow identifiers are represented by placeholders. Running the templates requires the applicable source data and runtime configuration.
