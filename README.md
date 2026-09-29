# washing-machine-manual-assistant
A model-specific RAG assistant for answering washing machine questions using official manuals.

## Run the web interface from a fresh clone

The repository includes the prebuilt, model-labelled retrieval index at
`data/chunks.jsonl`. The original PDF manuals are intentionally not required at
runtime, so a fresh clone can answer questions without rebuilding the index.

Create a virtual environment, install the pinned dependencies, configure a private
OpenRouter key, and start the Streamlit app:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and replace only the OPENROUTER_API_KEY placeholder.
streamlit run streamlit_app.py
```

The interface lets the user select one of the five supported models, ask a natural
language question, and inspect the exact manual page used for the answer. Requests
without sufficient model-specific evidence are refused before answer generation.

## Current prototype

The project currently supports five washing-machine models. It extracts page-labelled
manual passages and applies the brand/model filter before ranking passages with a
local BM25 keyword baseline. No API key is required for ingestion or retrieval.

## Run the pipeline

Rebuilding the checked-in index is optional. Place the five manifest-listed PDFs in
`data/manuals/`, activate the virtual environment, and run:

```bash
source .venv/bin/activate
python src/ingest.py
```

This replaces `data/chunks.jsonl`. PDF files remain excluded from Git, while the
small deterministic index is committed so reviewers can run the project directly.

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
refused without a citation.

## Browser end-to-end test

The browser test starts the real Streamlit application and a deterministic local
OpenRouter-compatible server. It tests two model-specific E30 answers, exact page
citations, evidence-gated refusal, empty input, API authentication failure, stale
answer clearing, desktop layout, mobile overflow, title alignment, and touch-target
size. It does not use the real `.env` key and makes no paid API calls.

Install the test-only browser dependency once, then run the test:

```bash
npm install
npx playwright install chromium webkit
npm run test:e2e:all
```

To use an existing Chrome installation instead of downloading Chromium:

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE="/path/to/Google Chrome" npm run test:e2e
```

The WebKit run exercises the browser engine used by Safari. It is a browser-engine
test rather than a claim that every physical iPhone or macOS Safari version was tested.

The same retrieval, behavior, syntax, and browser checks run automatically through
GitHub Actions on every push and pull request.

The generation prompt also includes a regression-tested PDF-layout clarification for
control labels that become ambiguous when a control-panel diagram is extracted as
linear text.

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

## Formal evaluation

The fixed evaluation set contains 50 cases: 35 answerable questions, five questions
whose answers are absent from the selected model's manual, five unsupported models,
and five requests with missing model information. Twenty answerable cases are fixed
in advance for manual faithfulness review.

Run retrieval and routing without making API calls:

```bash
python evaluation/run_formal_evaluation.py
```

This writes `evaluation/formal_retrieval_results_50.csv` and does not overwrite the
completed generated-answer results.

Run grounded answer generation through the configured OpenRouter account:

```bash
python evaluation/run_formal_evaluation.py --generate
```

Use `--resume` to reuse passing rows and rerun failures only. The completed results
are written to `evaluation/formal_results_50.csv`.

Recorded formal run:

- Recall@3: 35/35 (100%)
- Answer generation: 35/35 answerable cases
- Refusal accuracy: 15/15 unanswerable or unroutable cases
- Manually reviewed faithfulness: 20/20 (100%)
- API use: 37,055 tokens across 35 recorded evaluation calls; estimated cost USD 0.00575937
