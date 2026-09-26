# washing-machine-manual-assistant
A model-specific RAG assistant for answering washing machine questions using official manuals.

## Current prototype

The project currently supports five washing-machine models. It extracts page-labelled
manual passages and applies the brand/model filter before ranking passages with a
local BM25 keyword baseline. No API key is required for ingestion or retrieval.

## Run the pipeline

Activate the virtual environment and create the manual chunks:

```bash
source .venv/bin/activate
python src/ingest.py
```

Retrieve the three most relevant passages for one supported model:

```bash
python src/retrieve.py \
  --brand Gaggenau \
  --model WM260164 \
  --question "What does error code E:30 / -80 mean?"
```

Run the answerable cases in the initial retrieval test set:

```bash
python evaluation/run_smoke_retrieval.py
```

The smoke-test runner reports Recall@3. Refusal behaviour and generated-answer
faithfulness will be evaluated separately after answer generation is implemented.
