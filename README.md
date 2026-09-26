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

Create an evidence-gated extractive answer with a page citation:

```bash
python src/answer.py \
  --brand Gaggenau \
  --model WM260164 \
  --question "What does error code E:30 / -80 mean?"
```

Run all initial answer/refusal checks:

```bash
python evaluation/run_smoke_answering.py
```

The retrieval smoke test reports Recall@3. The answer/refusal test checks that
answerable questions cite the expected evidence and that unsupported requests are
refused without a citation. The current answer is an extractive baseline; grounded
language-model generation and manual faithfulness review will be added separately.

## Grounded language-model generation

Install the dependencies, create a private local environment file, and add your own
OpenRouter API key:

```bash
pip install -r requirements.txt
cp .env.example .env
nano .env
```

The real `.env` file is ignored by Git. Do not paste the key into source code or
commit it to the repository.

Generate an English answer from the retrieved official-manual evidence:

```bash
python src/generate.py \
  --brand Gaggenau \
  --model WM260164 \
  --question "What does error code E:30 / -80 mean?"
```

The program uses the OpenAI-compatible OpenRouter endpoint and defaults to
`openai/gpt-6-luna`. API usage is appended locally to `outputs/api_usage.jsonl`,
including input tokens, output tokens, latency, and reported or estimated token cost.
Requests rejected by the local evidence gate do not call the API.
