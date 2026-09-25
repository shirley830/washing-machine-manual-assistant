# Preliminary Business and Technical Trade-off Analysis

**Project:** Model-Specific Washing Machine Manual Assistant  
**Status:** Initial decision draft — to be revised after implementation and evaluation

## 1. Project context

The proposed system allows a user to ask a natural-language question about a washing machine and receive an answer grounded in the official manual for the specified model. The response should identify the supporting section or page. If the model is missing, unsupported, or the selected manual does not contain sufficient evidence, the system should not invent an answer.

The initial dataset is intentionally limited to five washing-machine models. It includes a deliberately difficult evaluation pair: `E30` occurs in both AEG L6FBI27W and Gaggenau WM260164, but refers to different problems. This pair will be used to test whether the system reliably keeps information from different models separate.

This document records the decisions needed before implementation. It does not yet report measured cost, latency, or final evaluation results.

## 2. Coverage versus reliability

### Options considered

1. Support many models collected from a wide range of sources.
2. Support a small, fixed set of models using verified official manuals.

### Initial decision

Use five fixed models and accept questions only for those models.

### Business trade-off

A larger catalogue would make the system useful to more users, but it would also make it harder to verify document quality and answer correctness within the project timeline. A five-model prototype has lower market coverage, but provides a clearer demonstration of reliability and model-specific behaviour.

### Technical trade-off

A fixed collection reduces ingestion, metadata-cleaning, and evaluation complexity. The disadvantage is that the resulting architecture is demonstrated on a controlled dataset rather than at production scale.

### How the decision will be validated

The evaluation set will include ordinary questions for every supported model, unsupported-model questions, and questions without a model. Expansion to additional models is outside the first implementation unless the five-model evaluation reveals insufficient variation.

## 3. User convenience versus model-specific accuracy

### Options considered

1. Let the system search every manual and infer the user's model from the question.
2. Require a model selection and filter documents by model before retrieval.

### Initial decision

Require the user to provide or select a supported model before retrieval. Apply the model filter before similarity or keyword search.

### Business trade-off

Requiring a model adds friction because some users may not know where to find it. However, answering for the wrong washing machine could lead to ineffective or unsafe troubleshooting and would reduce trust in the product.

### Technical trade-off

Pre-filtering simplifies source attribution and reduces cross-model contamination. It also prevents the retriever from using a highly similar passage from the wrong manual. The disadvantage is that the system cannot answer a model-specific question when the model is omitted, even if the likely answer appears obvious.

### How the decision will be validated

The same `E30` question will be tested with AEG L6FBI27W, with Gaggenau WM260164, and without a model. The two model-specific questions must retrieve different explanations from their respective manuals. The model-free question should request the model rather than guess.

## 4. Semantic flexibility versus exact-code matching

### Options considered

1. Vector retrieval only.
2. Keyword retrieval only.
3. Hybrid retrieval combining semantic similarity with exact-term matching.

### Initial decision

Begin with vector retrieval as a baseline, then add exact-code matching or hybrid retrieval if the baseline performs poorly on error-code questions.

### Business trade-off

Natural-language search allows users to describe symptoms in their own words, which improves usability. Exact matching is less flexible but is important when a short identifier such as `E30` carries most of the question's meaning.

### Technical trade-off

Vector retrieval is suitable for paraphrased questions but may underweight short technical codes or retrieve semantically similar content from an unrelated section. Keyword retrieval handles codes well but may miss paraphrases and symptom descriptions. A hybrid method may improve robustness, but introduces additional ranking logic and parameters that must be tested.

### How the decision will be validated

Retrieval will be evaluated using Recall@3. Results for ordinary natural-language questions and error-code questions will also be inspected separately. Hybrid retrieval will be retained only if it improves the error-code cases without materially reducing general retrieval quality.

## 5. Answer coverage versus trustworthiness

### Options considered

1. Allow the language model to supplement the manuals with general knowledge.
2. Answer only when the selected manual provides sufficient supporting evidence.

### Initial decision

Restrict answers to information supported by the selected official manual. If the evidence is missing or insufficient, return a clear refusal or limitation statement.

### Business trade-off

Strict grounding means the system will answer fewer questions. However, the answers it does provide will be easier to verify, which is more important for a manual-based support tool than maximizing response rate.

### Technical trade-off

Grounded generation and refusal logic reduce unsupported claims, but require evidence thresholds and careful prompt design. A threshold that is too strict may reject answerable questions; one that is too permissive may allow plausible but unsupported answers.

### How the decision will be validated

The final evaluation will contain answerable and unanswerable questions. In addition to Recall@3, 20 of the 50 evaluation responses will be manually reviewed for faithfulness: every substantive claim in the answer must be supported by the cited section of the selected manual.

## 6. RAG versus model fine-tuning

### Options considered

1. Retrieval-augmented generation (RAG) over the manuals.
2. Fine-tune a model on manual-derived question-and-answer pairs.
3. Place entire manuals directly in the prompt for every question.

### Initial decision

Use RAG with model metadata and page or section references.

### Business trade-off

RAG allows manuals to be added or replaced without retraining a model and makes evidence visible to the user. Fine-tuning could alter answer style or behaviour, but would require additional training data and would not by itself provide reliable citations.

### Technical trade-off

RAG introduces retrieval errors and requires document chunking, indexing, and ranking. Fine-tuning adds data-preparation and training complexity, while full-document prompting may be simple for a small prototype but becomes inefficient and makes retrieval quality difficult to measure independently.

### How the decision will be validated

The implementation will report retrieval and answer quality separately. Recall@3 will measure whether the supporting section is retrieved, while manual faithfulness review will measure whether the generated answer remains supported by that section.

## 7. Decisions intentionally deferred

The following decisions will be revisited after the retrieval and answering pipeline works:

- Final user-interface framework.
- Local-only versus hosted deployment.
- Measured latency and cost per question.
- Scaling beyond the five selected models.
- Final chunk size, overlap, retrieval depth, and reranking configuration.

These items require implementation evidence and should not be presented as final conclusions at this stage.

## 8. Immediate implementation implications

The first prototype should:

1. Store brand, model, document name, page number, and section metadata for every chunk.
2. Require a supported model before retrieval.
3. Filter by model before ranking candidate passages.
4. Return the top three passages with page or section references.
5. Test the two model-specific `E30` cases before adding answer generation.
6. Add grounded answer generation and refusal behaviour only after model-filtered retrieval works correctly.

