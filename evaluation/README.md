# Evaluation Guide

This directory contains the fixed evaluation data, executable evaluation scripts, and recorded outputs for the Washing Machine Manual Assistant. Retrieval, answer behaviour, and answer faithfulness are evaluated separately so that a successful search result is not mistaken for a correct final answer.

## Evaluation-set composition

[`formal_evaluation_50.csv`](formal_evaluation_50.csv) contains 50 cases fixed before the recorded run.

| Category | Cases | Expected behaviour |
| --- | ---: | --- |
| Answerable manual questions | 35 | Retrieve valid evidence and answer with a citation. |
| Manual-unanswerable questions | 5 | Refuse because the selected manual lacks sufficient evidence. |
| Unsupported models | 5 | Refuse before retrieval or generation. |
| Missing-model requests | 5 | Request a supported exact model rather than guessing. |

The answerable set covers all five supported models. It includes a model-isolation test in which similar `E30` codes have different meanings in the Zanussi ZWG1120M and Gaggenau WM260164 manuals. A corresponding request without an exact model must be refused.

## Metrics

### Retrieval Recall at 3

An answerable case is a hit when at least one valid evidence chunk appears in the first three retrieved passages. `acceptable_evidence_chunk_ids` can contain more than one valid passage when the same answer is supported by the labelled passage or a neighbouring section. The reported denominator is the 35 answerable cases.

### Behaviour accuracy

Each case has an explicit expected behaviour: answer with a citation, refuse for missing manual evidence, refuse an unsupported model, or refuse missing model information. `behavior_pass` records whether the observed status matches that expectation.

### Manual faithfulness

Twenty answerable cases are marked for manual review. A reviewer compares every substantive statement in the generated response with the cited passage and records `PASS` only when the answer is fully supported. This measure evaluates generation separately from retrieval.

## Recorded results

| Measure | Result |
| --- | ---: |
| Retrieval Recall at 3 | 35/35 (100%) |
| Answerable cases completed | 35/35 |
| Correct refusals or routing behaviour | 15/15 (100%) |
| Overall behaviour checks | 50/50 (100%) |
| Manually reviewed faithfulness | 20/20 (100%) |
| Provider usage | 37,055 tokens |
| Estimated provider cost | USD 0.00575937 |

The cost is approximately USD 0.000115 per evaluation case when amortised across all 50 cases, or USD 0.000165 per generated answer across the 35 provider calls.

## Files

| File | Purpose |
| --- | --- |
| `formal_evaluation_50.csv` | Fixed questions, expected behaviours, valid evidence labels, and faithfulness-review selection. |
| `formal_retrieval_results_50.csv` | Retrieval-only output. Generation fields remain blank by design. |
| `formal_results_50.csv` | Recorded retrieval, generation, refusal, usage, and manual-review results. |
| `smoke_test.csv` | Small, fast regression set used during development. |
| `run_formal_evaluation.py` | Runs retrieval-only or full grounded-answer evaluation and writes the result CSV. |
| `run_smoke_retrieval.py` | Reports Recall@3 on answerable smoke cases. |
| `run_smoke_answering.py` | Checks local answer, refusal, and citation behaviour. |

## Reproducing the checks

From the repository root with the project environment active:

```bash
python evaluation/run_smoke_retrieval.py
python evaluation/run_smoke_answering.py
python evaluation/run_formal_evaluation.py
python -m unittest discover -s tests -p "test_*.py"
```

A full hosted-generation run requires a private `OPENROUTER_API_KEY` and incurs provider usage. The retrieval-only run and automated browser suite do not require paid requests. The browser suite uses a deterministic local provider-compatible test server.

## Interpretation and limitations

The recorded results demonstrate internal correctness on this fixed dataset; they do not establish production accuracy. The set is small and was designed within the same project, so it may underrepresent unexpected phrasing and failure modes. Faithfulness review covers 20 of 35 generated answers and uses one manual reviewer. The terminology map is also tuned to the current five manuals. Stronger evidence would require a hidden test set, independent reviewers, new user phrasing, additional languages, and repeated evaluation whenever a manual or model is added.
