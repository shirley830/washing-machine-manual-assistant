# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People who own or operate one of the supported washing-machine models and need a quick, trustworthy answer while standing near the appliance. Course assessors are a secondary audience evaluating whether the system works and whether its evidence is traceable.

## Product Purpose

Washing Machine Manual Assistant lets a user choose an exact brand and model, ask a natural-language question, and receive either a grounded answer with the relevant manual page or a clear refusal when the manual does not support an answer.

## Positioning

The assistant filters by exact model before retrieval and requires manual evidence before answering. It is not a general appliance chatbot.

## Operating Context

The primary workflow is: select brand, select exact model, ask a question, read the answer, and inspect the cited official-manual evidence. The application is a Streamlit web interface backed by a local retrieval index and OpenRouter generation.

## Capabilities and Constraints

- Five supported model entries across Gaggenau, SMEG, and Zanussi.
- Official manual content is the only answer source.
- Exact-model filtering is mandatory before retrieval.
- Unsupported questions must produce a refusal.
- Original PDF manuals remain local and are not committed to GitHub.
- API credentials remain local in `.env` and must never be committed.

## Brand Commitments

- Product name: Washing Machine Manual Assistant.
- Preserve the custom washing-machine and graduation-cap logo in `assets/logo.svg`.
- Use a cool navy, blue, cyan, and white visual family.
- The interface should feel like a real appliance product experience, not a generic AI dashboard or a stack of cards.
- Typography follows Apple's native system stack: SF Pro on Apple devices, with Helvetica Neue and Arial as safe fallbacks elsewhere.

## Evidence on Hand

- Fixed manual catalogue: `data/manuals_manifest.csv`.
- Prebuilt retrieval index: `data/chunks.jsonl`.
- Formal evaluation set and results under `evaluation/`.
- Official product imagery stored under `assets/machines/` with source pages documented in the repository.
- Existing desktop and mobile reference captures under `docs/images/`.

## Product Principles

1. Match the exact machine before searching.
2. Show the evidence a user can verify.
3. Refuse when the manual does not support an answer.
4. Keep technical evaluation details in project documentation rather than the main user answer.
5. Make the core question-and-answer workflow immediately understandable.

## Accessibility & Inclusion

Maintain keyboard focus visibility, readable contrast, responsive layouts, and a reduced-motion path for all nonessential animation.
