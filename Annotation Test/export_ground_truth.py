#!/usr/bin/env python3
"""
Export annotations to ground-truth JSONL files.

Output (one file per annotated run):
    annotation_tool/output/ground_truth_cd2c6375.jsonl
    annotation_tool/output/ground_truth_51ab33a6.jsonl

Each line follows the standard ground-truth schema:
    {"query_id": "...", "sentences": [
        {"sentence_id": "...", "sentence_text": "...", "attributed_doc_ids": ["doc__pN", ...]},
        ...
    ]}

A sentence's attributed_doc_ids = doc_ids of pages where the human clicked "Attribué".
Empty list means the sentence has no attribution (hallucinated / general knowledge).

Run:
    cd annotation_tool
    python export_ground_truth.py
"""

import json
import pathlib
import sys

BASE_DIR   = pathlib.Path(__file__).parent.resolve()
DATA_DIR   = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

ANNOTATION_DATA_FILE = DATA_DIR / "annotation_data.json"
ANNOTATIONS_FILE     = DATA_DIR / "annotations.json"


def export():
    if not ANNOTATION_DATA_FILE.exists():
        sys.exit(f"ERROR: {ANNOTATION_DATA_FILE} not found. Run prepare_data.py first.")
    if not ANNOTATIONS_FILE.exists():
        sys.exit(f"ERROR: {ANNOTATIONS_FILE} not found. No annotations yet.")

    with open(ANNOTATION_DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    with open(ANNOTATIONS_FILE, encoding="utf-8") as f:
        annotations = json.load(f)

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Build: run_id -> qid -> [groups ordered by page_rank]
    run_qid_groups: dict[str, dict[str, list]] = {}
    for group in data["groups"]:
        (run_qid_groups
            .setdefault(group["run_id"], {})
            .setdefault(group["qid"], [])
            .append(group))

    for run_id, qid_map in run_qid_groups.items():
        run_ann = annotations.get(run_id, {})
        warnings = []
        records  = []

        for qid, groups in qid_map.items():
            qid_ann  = run_ann.get(qid, {})
            sentences = groups[0]["sentences"]  # same list for all page groups

            result_sentences = []
            for sent in sentences:
                sid = sent["sid"]
                attributed_doc_ids = []

                for group in groups:
                    pr     = str(group["page_rank"])
                    pr_ann = qid_ann.get(pr, {})

                    if sid not in pr_ann:
                        warnings.append(
                            f"  NOT ANNOTATED: {run_id}/{qid}/rank{group['page_rank']}/{sid}"
                        )
                    elif pr_ann[sid]:
                        attributed_doc_ids.append(group["doc_id"])

                result_sentences.append({
                    "sentence_id":        sid,
                    "sentence_text":      sent["text"],
                    "attributed_doc_ids": attributed_doc_ids,
                })

            records.append({"query_id": qid, "sentences": result_sentences})

        # Write JSONL
        out_file = OUTPUT_DIR / f"ground_truth_{run_id}.jsonl"
        with open(out_file, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        total_s  = sum(len(r["sentences"]) for r in records)
        attrib   = sum(1 for r in records for s in r["sentences"] if s["attributed_doc_ids"])
        no_att   = total_s - attrib

        print(f"\n{run_id}:")
        print(f"  Output    : {out_file}")
        print(f"  Queries   : {len(records)}")
        print(f"  Sentences : {total_s}  ({attrib} attributed, {no_att} not attributed)")

        if warnings:
            print(f"  WARNINGS  : {len(warnings)} sentence-page pairs not yet annotated")
            for w in warnings[:15]:
                print(w)
            if len(warnings) > 15:
                print(f"  ... and {len(warnings) - 15} more")
        else:
            print("  All annotations complete — no warnings.")

    print()


if __name__ == "__main__":
    export()
