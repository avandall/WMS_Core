# Kaggle Fine-Tuning Workflow

This guide captures the minimal workflow for fine-tuning the WMS query-template extractor on Kaggle when local hardware is not strong enough.

## Goal

Fine-tune a local model that converts WMS data questions into the runtime JSON template used by `ai-service`:

```json
{
  "intent": "inventory_lookup",
  "target": "inventory",
  "filters": {"sku": "SKU-LAP-001"},
  "metrics": ["available_quantity"],
  "limit": 20,
  "sql": "SELECT ..."
}
```

The fine-tuned model only replaces the structured data-query extractor. It does not replace the RAG or agent path.

## Files To Upload

Create a small folder or zip, for example `wms-finetune/`, with this structure:

```text
wms-finetune/
  Services/ai-service/src/ai_service/pipeline/templates.py
  training/__init__.py
  training/fine_tuning/__init__.py
  training/fine_tuning/train_wms.py
  training/fine_tuning/build_enriched_dataset.py
  training/fine_tuning/data/wms_data_enriched.jsonl
```

Required for training:

- `training/fine_tuning/train_wms.py`
- `training/fine_tuning/data/wms_data_enriched.jsonl`
- `Services/ai-service/src/ai_service/pipeline/templates.py`

Optional but recommended:

- `training/fine_tuning/build_enriched_dataset.py`, so the dataset can be regenerated or extended on Kaggle.
- `training/__init__.py` and `training/fine_tuning/__init__.py`, so imports stay predictable.

## Kaggle Setup

1. Create a Kaggle dataset from the `wms-finetune/` folder, or upload the zip directly to a notebook.
2. Create a new Kaggle notebook.
3. Enable GPU in notebook settings.
4. Add the uploaded dataset to the notebook.
5. Copy the dataset into the working directory if needed:

```bash
cp -r /kaggle/input/<your-dataset-name>/wms-finetune /kaggle/working/wms-finetune
cd /kaggle/working/wms-finetune
```

If the uploaded files appear directly under `/kaggle/input/<your-dataset-name>/`, adjust the `cp` path accordingly.

## Install Dependencies

In a Kaggle notebook cell:

```bash
pip install -U unsloth datasets trl transformers peft accelerate bitsandbytes
```

If Kaggle already has compatible versions, this may be enough:

```bash
pip install -U unsloth
```

## Train

Default training command:

```bash
python training/fine_tuning/train_wms.py \
  --data-path training/fine_tuning/data/wms_data_enriched.jsonl \
  --output-dir /kaggle/working/wms_checkpoints \
  --adapter-dir /kaggle/working/wms_final_adapter \
  --merged-model-dir /kaggle/working/wms_final_model
```

If Kaggle runs out of VRAM or disk while merging the final model, train only the PEFT adapter:

```bash
python training/fine_tuning/train_wms.py \
  --data-path training/fine_tuning/data/wms_data_enriched.jsonl \
  --output-dir /kaggle/working/wms_checkpoints \
  --adapter-dir /kaggle/working/wms_final_adapter \
  --skip-merge
```

Useful low-resource adjustments:

```bash
python training/fine_tuning/train_wms.py \
  --data-path training/fine_tuning/data/wms_data_enriched.jsonl \
  --output-dir /kaggle/working/wms_checkpoints \
  --adapter-dir /kaggle/working/wms_final_adapter \
  --merged-model-dir /kaggle/working/wms_final_model \
  --max-steps 100 \
  --batch-size 1 \
  --gradient-accumulation-steps 8 \
  --skip-merge
```

## Outputs

After training, keep one of these folders:

```text
/kaggle/working/wms_final_model
/kaggle/working/wms_final_adapter
```

Use `wms_final_model` if the merge succeeded. It is the most convenient runtime artifact.

Use `wms_final_adapter` if you trained with `--skip-merge`. The project runtime supports PEFT adapter folders that contain `adapter_config.json`.

## Download Artifacts

In Kaggle, download the folder from `/kaggle/working`, or zip it first:

```bash
cd /kaggle/working
zip -r wms_final_model.zip wms_final_model
zip -r wms_final_adapter.zip wms_final_adapter
```

Download the zip from the notebook output panel.

## Use In This Project

Place the downloaded folder somewhere local, for example:

```text
training/fine_tuning/wms_final_model
```

Then configure `ai-service`:

```bash
FINE_TUNED_MODEL_PATH=training/fine_tuning/wms_final_model
FINE_TUNED_MODEL_DEVICE=cpu
FINE_TUNED_MAX_NEW_TOKENS=256
```

For GPU runtime:

```bash
FINE_TUNED_MODEL_DEVICE=cuda
```

For an adapter-only artifact:

```bash
FINE_TUNED_MODEL_PATH=training/fine_tuning/wms_final_adapter
```

## Verify Runtime Selection

Start `ai-service` and check status. The pipeline status should report:

```text
fine_tuned_template_extractor_enabled: true
template_extractor_source: fine_tuned
```

If loading fails, the service falls back to the Groq extractor.

## Dataset Notes

The default enriched dataset is:

```text
training/fine_tuning/data/wms_data_enriched.jsonl
```

It includes:

- Inventory lookup
- Document lookup
- Warehouse and position lookup
- Product lookup
- Customer lookup
- Reporting queries
- Order status queries
- Unknown/non-data prompts
- Vietnamese and English paraphrases
- SQL-bearing templates and non-SQL unknown examples

To regenerate it locally:

```bash
python training/fine_tuning/build_enriched_dataset.py
```

Then upload the refreshed `wms_data_enriched.jsonl` to Kaggle.

## Quick Checklist

- Upload `train_wms.py`, `templates.py`, and `wms_data_enriched.jsonl`.
- Enable GPU in Kaggle.
- Install `unsloth`, `datasets`, `trl`, `transformers`, `peft`, `accelerate`, `bitsandbytes`.
- Train to `/kaggle/working/wms_final_model` or `/kaggle/working/wms_final_adapter`.
- Download the artifact.
- Set `FINE_TUNED_MODEL_PATH` in `ai-service`.
- Confirm status reports `fine_tuned`.
