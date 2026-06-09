# Internship Roadmap — RAG Attribution for Rail Maintenance (SNCF)

## Overall goal

Build a **domain-specific benchmark** for sentence-level RAG attribution applied to **rail maintenance documentation**. The intern produces a reusable French-language dataset, evaluates existing attribution systems, and develops an improved method.

**Total duration:** 4-5 months (20 weeks)  
**Profile:** M1 student in NLP / Computer Science (no railway engineering background required)  
**Language stack:** Python, HuggingFace, `evalllm2026-rag-attribution` toolkit  
**CLI:** `rag-eval` (evaluation, generation, baselines already implemented)

---

## Why rail maintenance?

| Argument                 | Detail                                                                                                                                        |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| High-stakes domain       | Maintenance errors can cause accidents — hallucination detection is safety-critical                                                           |
| Rich public corpus       | ERA, UIC, SNCF Réseau, ART, and EU regulatory bodies publish extensive technical documentation                                                |
| French language          | SNCF documentation is predominantly in French — directly relevant to the project                                                              |
| Factual, claim-rich text | Maintenance standards contain precise numerical tolerances, inspection frequencies, and procedures — attribution is meaningful and verifiable |
| Expert scarcity          | Domain expertise is hard to access, making automatic annotation strategies essential and scientifically interesting                           |
| Practical relevance      | SNCF and railway operators are active users of LLM-assisted tools for maintenance support                                                     |

---

## Document sources (all publicly accessible)

| Source                                        | Content                                                                     | URL                                                                                             |
| --------------------------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| ERA (European Union Agency for Railways)      | Technical specifications for interoperability (TSI), safety reports         | era.europa.eu                                                                                   |
| UIC (Union Internationale des Chemins de fer) | Leaflets on track maintenance, rolling stock, infrastructure                | uic.org (selected free publications)                                                            |
| ART (Autorité de Régulation des Transports)   | French regulatory decisions, infrastructure access rules                    | [link](https://www.autorite-transports.fr/le-ferroviaire/les-avis-et-decisions-du-ferroviaire/) |
| SNCF Réseau                                   | Reference network statement, infrastructure management documents            | sncf-reseau.fr                                                                                  |
| Wikipedia (FR)                                | Articles on rail infrastructure, signalling systems, maintenance techniques | fr.wikipedia.org                                                                                |

---

## Domain taxonomy (guides query design and annotation)

Maintenance documentation in rail covers five major topics, each with distinct attribution challenges:

| Topic                              | Example query                                                                             | Attribution difficulty                                      |
| ---------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| **Track geometry**                 | "Quelles sont les tolérances d'écartement des rails en voie principale ?"                 | Medium — precise numerical values, single source            |
| **Catenary and OHL**               | "Quelle est la fréquence d'inspection des fils de contact en zone à forte densité ?"      | Hard — multi-source synthesis across TSI and national rules |
| **Rolling stock maintenance**      | "Quels contrôles sont requis avant remise en service après intervention sur les bogies ?" | Hard — procedural, multi-step, cross-document               |
| **Signalling and ERTMS**           | "Comment la supervision de vitesse est-elle assurée en cas de défaut ETCS niveau 2 ?"     | Very hard — highly technical, risk of hallucination         |
| **Incident and defect management** | "Quelles sont les procédures à appliquer en cas de détection d'une fissure sur un rail ?" | Medium — safety-critical, well-documented                   |

---

## Task 1 — Corpus construction (Weeks 1–3)

**Objective:** Build a clean, structured document collection covering the five maintenance topics.

**Work:**

- Download and normalize documents from ERA, UIC, ART, SNCF Réseau, and Wikipedia (FR)
- Chunk documents into paragraphs of 150–300 words with metadata: `{doc_id, title, source, date, topic, text, url}`
- Deduplicate (content hash) and filter: remove purely administrative or legal-boilerplate sections
- Build a BM25 retrieval index (`rank_bm25`) and a dense retrieval index (`sentence-transformers/paraphrase-multilingual-mpnet-base-v2`) for later query answering
- Tag each document chunk with its **topic** (track / catenary / rolling stock / signalling / incident) — automatic via keyword matching, then manually spot-checked

**Validation gate — Task 1 is complete when:**

```
corpus/
├── documents.jsonl          # ≥ 600 chunks, schema: {doc_id, title, source, date, topic, text, url}
├── corpus_stats.md          # token distribution, source breakdown, topic balance table
├── retrieval_index_bm25/    # BM25 index
└── retrieval_index_dense/   # dense index
```

- [ ] BM25 top-5 retrieval manually verified for 10 test queries (all 5 topics covered)
- [ ] No chunk shorter than 80 tokens or longer than 400 tokens
- [ ] Topic distribution: no topic < 10% of total corpus

---

## Task 2 — Query and RAG answer generation (Weeks 3–5)

**Objective:** Produce realistic `input.jsonl` records covering a range of attribution difficulty levels.

**Work:**

Design **200 queries** across three difficulty types:

| Type                          | Description                                                                                 | Target count |
| ----------------------------- | ------------------------------------------------------------------------------------------- | ------------ |
| **A — Single-source**         | Answer fully grounded in one document (e.g., a specific tolerance value)                    | 70           |
| **B — Multi-source**          | Answer synthesizes 2–3 documents (e.g., procedure + regulation + norm)                      | 90           |
| **C — Partial hallucination** | Generator adds a plausible but unsupported claim (e.g., an invented frequency or threshold) | 40           |

Query generation process:

1. For each document chunk, ask an LLM (`gpt-4o-mini` or `mistral-7b-instruct`) to generate 2–3 technical questions whose answer is contained in the chunk
2. Human filter: keep only unambiguous, realistic maintenance questions (discard trivial or decontextualised ones)
3. For Type C: after generation, manually inject one hallucinated sentence into the answer (e.g., replace a real tolerance value with a plausible wrong one)

For each query, retrieve the top-5 documents using a hybrid BM25 + dense fusion, then generate a 3–5 sentence answer with `rag-eval generate`.

**Validation gate — Task 2 is complete when:**

```
dataset/
├── input.jsonl              # 200 records, JSONL, schema-validated
└── query_catalog.md         # type distribution (A/B/C), topic coverage (5 topics), generation model used
```

- [ ] `python -c "from rag_attribution.data.io import read_jsonl_list; ..."` passes on all 200 records
- [ ] Manual review of 20 randomly sampled records: answers are fluent and plausible maintenance responses
- [ ] Type C records: hallucinated sentence is not detectable without document lookup (blind check by a colleague)

---

## Task 3 — Annotation (Weeks 6–9)

**Objective:** Produce ground truth with two complementary strategies; measure and compare their quality.

This is the methodological core of the internship. Expert knowledge is scarce, so both strategies are designed to be usable without a railway engineer.

---

### Strategy A — Automatic annotation (no expert required)

1. **Generation-time citation**: re-generate each answer with a structured prompt that forces the LLM to cite `doc_id` for each sentence. Example prompt suffix:

   > "For each sentence of your answer, add the tag `[SOURCE: doc_id]` citing the document you used. If the sentence is based on general knowledge not found in the documents, write `[SOURCE: none]`."

2. **NLI verification pass**: for each (sentence, doc) pair, run `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` and compute the entailment probability. Accept the LLM citation if entailment ≥ 0.5, else flag as uncertain.

3. **Conflict tagging**: records where LLM citation ≠ NLI decision are tagged `conflict=True` → this is the **hard subset**.

---

### Strategy B — Non-expert human annotation

Design a simple annotation interface (Label Studio or a structured spreadsheet):

- Annotator sees: the query, the answer sentence, and the top-5 document chunks side by side
- Task: tick which documents (if any) contain the information expressed in the sentence
- **No railway expertise needed** — annotators judge information containment, not technical correctness

**Annotation guidelines cover:**

- What counts as attribution (direct support) vs. topical relevance (not sufficient)
- Numerical values: if the sentence states "tolerance = 6mm" and the document states "tolerance = 6mm", it is attributed; if the document says "tolerance ≤ 8mm", it is not
- Multi-source: both documents must be ticked if both contribute distinct facts
- General knowledge sentences: tag as `[]` (no attribution)

**Recruit annotators:** 2–3 other M1 students. Train with 20 worked examples. Target: 150 records annotated (50 per annotator with overlap on 30 for IAA).

Measure **inter-annotator agreement** (Cohen's κ per sentence, Krippendorff's α globally). Adjudicate disagreements by majority vote.

**Expert validation (optional, if access available):** Submit 20 Type C records (hallucination cases) to a railway engineering contact (e.g., via SNCF-IRIT partnership) to confirm that the injected hallucinations are indeed unattested in the documents.

---

**Validation gate — Task 3 is complete when:**

```
dataset/
├── ground_truth_auto.jsonl     # Strategy A labels for all 200 records
├── ground_truth_human.jsonl    # Strategy B labels for 150 records (adjudicated)
└── annotation_report.md        # IAA scores, conflict rate, hard subset size
```

- [ ] Inter-annotator κ ≥ 0.60 on shared records (otherwise: revise guidelines and re-annotate)
- [ ] Strategy A vs. Strategy B agreement measured on the 150-record overlap
- [ ] Hard subset identified: records where auto ≠ human (target 15–20%)
- [ ] Type C hallucination detection rate reported separately

---

## Task 4 — Baseline evaluation (Weeks 9–12)

**Objective:** Establish reference scores for the benchmark and identify systematic failure modes.

**Systems to evaluate:**

| System                   | Method                                             | Notes                                           |
| ------------------------ | -------------------------------------------------- | ----------------------------------------------- |
| Random                   | Attribute to a random subset of docs               | Lower bound                                     |
| Rank-1                   | Always attribute to the top-ranked doc             | Simple heuristic                                |
| Keyword overlap          | Jaccard ≥ threshold                                | Already in `rag-eval baseline --method keyword` |
| NLI cross-encoder        | mDeBERTa-v3-base-mnli-xnli                         | Already in `rag-eval baseline --method nli`     |
| Embedding similarity     | Cosine(sentence_emb, doc_emb)                      | `paraphrase-multilingual-mpnet-base-v2`         |
| LLM-as-judge (zero-shot) | Prompt `mistral-7b-instruct` to decide attribution | `rag-eval generate` with attribution template   |
| LLM-as-judge (few-shot)  | Same with 5 in-context examples from annotated set | Manual prompt engineering                       |

**New metric to implement (extends the toolkit):**

**Rank-weighted F1**: documents retrieved at rank 1 are more likely to have been used by the generator than documents at rank 5. Weight attribution matches by inverse rank:

```
weighted_TP = Σ  (1/rank_d)  for d in gold ∩ pred
weighted_FP = Σ  (1/rank_d)  for d in pred \ gold
weighted_FN = Σ  (1/rank_d)  for d in gold \ pred

Weighted Precision = weighted_TP / (weighted_TP + weighted_FP)
Weighted Recall    = weighted_TP / (weighted_TP + weighted_FN)
Weighted F1        = harmonic mean
```

Implement in `src/rag_attribution/evaluation/metrics.py` and expose via `rag-eval evaluate --rank-weighted`.

**Evaluation slices:**

- All records (auto labels) / all records (human labels)
- By query type: A (single-source) / B (multi-source) / C (hallucination)
- By topic: track / catenary / rolling stock / signalling / incident
- Hard subset only (auto ≠ human labels)

**Validation gate — Task 4 is complete when:**

```
results/
├── baseline_results_table.md    # systems × metrics × slices
├── error_analysis.md            # 30 failure cases with error type taxonomy
└── results/*.json               # raw rag-eval output per system
```

- [ ] All 7 systems scored on both ground truth versions
- [ ] Rank-weighted F1 implemented, tested (`pytest tests/unit/test_metrics.py`), and integrated into the CLI
- [ ] Error taxonomy defined with at least 4 categories (e.g., paraphrase, numerical hallucination, multi-source confusion, topic drift)
- [ ] Worst-performing topic and query type identified

---

## Task 5 — Improved attribution method (Weeks 12–17)

**Objective:** Develop one attribution system that outperforms all baselines on the human-annotated test set.

Based on Task 4 error analysis, the intern selects **one direction**. Three candidates:

---

### Direction A — Sentence-level NLI with passage decomposition

**Hypothesis:** full-document NLI is noisy because maintenance documents contain many irrelevant passages. Compare each answer sentence against individual document _sentences_ rather than full chunks, then aggregate by maximum score.

Implementation: split each retrieved document chunk into sentences → run NLI on (doc_sentence, answer_sentence) pairs → attribute if max entailment score ≥ threshold. Expected gain on Type B (multi-source) and long documents.

---

### Direction B — Domain-adapted prompting with chain-of-thought

**Hypothesis:** a general LLM does not know what "attribution" means in a maintenance context. A structured domain-specific prompt outperforms generic zero-shot.

Prompt structure:

1. "What specific technical claim does this sentence make? (value, procedure, standard reference, or general statement)"
2. "For each retrieved document: does it contain evidence for this claim? (direct / indirect / none)"
3. "List the doc_ids with direct evidence."

Compare: zero-shot vs. 5-shot vs. 10-shot, and small model (`mistral-7b`) vs. large model (`gpt-4o`). Expected gain on Type C (hallucination detection).

---

### Direction C — Fine-tuning a small model on the annotated dataset

**Hypothesis:** 150 annotated records are sufficient to fine-tune a small cross-encoder for domain-specific attribution.

Fine-tune `MiniLM-L6-H768` (or `mDeBERTa-v3-base`) on the 150 human-annotated records using LoRA (via `peft`). Input: `[CLS] doc_text [SEP] sentence_text [SEP]` → binary entailment label. Evaluate on a held-out 30-record test split. Expected gain on all query types; tests whether in-domain supervision compensates for small data size.

---

**Validation gate — Task 5 is complete when:**

```
attribution/
├── {method}_system.py           # reproducible, runnable standalone script
├── {method}_results.json        # rag-eval output
└── ablation_table.md            # ablation confirming each design choice
```

- [ ] Chosen system beats best baseline by ≥ 3 points Micro F1 on human-annotated test set
- [ ] Ablation shows each component contributes positively
- [ ] System is reproducible: re-run by a colleague with a single command produces the same scores ± 0.5 F1

---

## Task 6 — Analysis, report, and toolkit contribution (Weeks 17–20)

**Objective:** Document findings, release the dataset, and contribute the rank-weighted F1 metric as a pull request to the main toolkit.

**Work:**

- Write a 15–20 page technical report (internship format)
- Structured error taxonomy for the rail maintenance domain (with worked examples per category)
- PR to the `evalllm2026-rag-attribution` repository:
  - `rank_weighted_f1` in `evaluation/metrics.py`
  - Corresponding tests in `tests/unit/test_metrics.py`
  - CLI flag `--rank-weighted` in `eval_cmd.py`
- Publish the dataset on HuggingFace Hub under CC-BY-SA:
  - `input.jsonl` (200 records), `ground_truth_human.jsonl` (150 records), `ground_truth_auto.jsonl` (200 records)
  - Dataset card with domain description, annotation protocol, known limitations
- Draft a 4-page paper targeting a workshop (EvalLLM2027, TALN, or EMNLP Findings)

**Validation gate — Task 6 is complete when:**

- [ ] Technical report submitted and approved by supervisor
- [ ] Rank-weighted F1 PR merged, CI green
- [ ] Dataset published on HuggingFace Hub with model card
- [ ] Paper draft submitted for supervisor review

---

## Timeline summary

| Weeks | Task                   | Key deliverable                        | Validation criterion                            |
| ----- | ---------------------- | -------------------------------------- | ----------------------------------------------- |
| 1–3   | T1: Corpus             | `documents.jsonl` (≥ 600 chunks)       | BM25 retrieval spot-check passes                |
| 3–5   | T2: Query & generation | `input.jsonl` (200 records)            | Schema validation + manual review of 20 records |
| 6–9   | T3: Annotation         | `ground_truth_human.jsonl`, IAA report | κ ≥ 0.60, hard subset identified                |
| 9–12  | T4: Baselines          | Baseline table, error taxonomy         | 7 systems scored, rank-weighted F1 in toolkit   |
| 12–17 | T5: Improved system    | System code, ablation table            | +3 Micro F1 vs. best baseline, reproducible     |
| 17–20 | T6: Report & release   | Report, HF dataset, PR                 | All gates closed                                |

---

## What makes it feasible without a railway engineer

| Challenge                                  | Mitigation strategy                                                                                            |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| Technical vocabulary                       | Annotation guidelines focus on information containment, not technical correctness — no domain expertise needed |
| Expert annotations unavailable             | Strategy A (automatic) provides complete labels; human annotation validates a 150-record subset                |
| Hallucination verification                 | Type C records inject controlled, verifiable hallucinations — detectability does not require expert knowledge  |
| Long technical documents                   | BM25 + dense hybrid retrieval ensures relevant passages are surfaced; chunking limits document length          |
| Numerical claims (tolerances, frequencies) | Exact-match rule in annotation guidelines: numbers must match exactly to count as attributed                   |

---

## Optional extensions

- **Cross-document consistency check:** detect when two retrieved documents contradict each other on the same claim (e.g., different tolerance values for the same rail type) — a signal of corpus quality issues or regulatory revision
- **Temporal attribution:** maintenance standards are revised over time; evaluate whether the RAG system correctly attributes to the most recent version of a norm
- **Safety-critical sentence detection:** classify sentences by their safety impact (safety-critical / operational / administrative) and report attribution accuracy separately — missed attribution on safety-critical sentences is more costly than on administrative ones
