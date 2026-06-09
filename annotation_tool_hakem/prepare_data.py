#!/usr/bin/env python3
"""
Prepare annotation data for the manual annotation tool.

Steps:
  1. Fetch task2_v3_organizer.jsonl from HPC via scp (skipped if already present).
  2. Load the two output files to annotate (cd2c6375, 51ab33a6) from local disk.
  3. Merge into annotation_data.json — one "group" per (run_id, qid, page_rank).

Run once before starting the annotation server:
    cd annotation_tool
    python prepare_data.py
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys

BASE_DIR = pathlib.Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
PROJECT_ROOT = BASE_DIR.parent
TASK2_INPUTS_DIR = PROJECT_ROOT / "data" / "task2_inputs"

HPC_HOST = "occidata-cluster.irit.fr"
HPC_BASE = "/projects/iris/jmoreno/Attribution/evalllm2026RAGAttributionEval"
HPC_ORGANIZER = f"{HPC_HOST}:{HPC_BASE}/data/task2/task2_v3_organizer.jsonl"

# Only these two files will be manually annotated
RUN_IDS = ["cd2c6375", "51ab33a6"]


def fetch_organizer(dest: pathlib.Path, hpc_src: str) -> None:
    print(f"Fetching {hpc_src} …")
    result = subprocess.run(["scp", hpc_src, str(dest)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: scp failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"  saved to {dest}")


def load_organizer(path: pathlib.Path) -> dict:
    """Returns dict keyed by uid (=qid) → full record."""
    records = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            records[r["uid"]] = r
    return records


def build_groups(run_id: str, output_file: pathlib.Path, organizer: dict) -> list:
    with open(output_file, encoding="utf-8") as f:
        data = json.load(f)

    groups = []
    for result in data["results"]:
        qid = result["qid"]
        question = result["question"]
        retrieved = result["retrieved"]
        sentences = [{"sid": s["sid"], "text": s["text"]} for s in result["answer_sentences"]]

        org = organizer.get(qid)
        if org is None:
            print(f"  WARNING: qid {qid} not in organizer file — skipping", file=sys.stderr)
            continue

        text_content = org.get("text_content", [])

        for i, page in enumerate(retrieved):
            doc_name = page["doc_name"]
            page_number = page["page"]
            doc_id = f"{doc_name}__p{page_number}"
            page_text = text_content[i] if i < len(text_content) else ""

            if not page_text:
                print(f"  WARNING: no text_content for {run_id}/{qid}/rank{i} ({doc_name} p{page_number})")

            groups.append({
                "run_id": run_id,
                "qid": qid,
                "page_rank": i,
                "doc_name": doc_name,
                "page_number": page_number,
                "doc_id": doc_id,
                "question": question,
                "page_text": page_text,
                "sentences": sentences,
            })

    return groups


def main():
    parser = argparse.ArgumentParser(description="Prepare annotation data")
    parser.add_argument(
        "--hpc-base", default=HPC_BASE,
        help="HPC project base path (default: %(default)s)",
    )
    parser.add_argument(
        "--force-scp", action="store_true",
        help="Re-fetch organizer file even if already present locally",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    (BASE_DIR / "output").mkdir(exist_ok=True)

    # Step 1: organizer file
    organizer_local = DATA_DIR / "task2_v3_organizer.jsonl"
    if not organizer_local.exists() or args.force_scp:
        hpc_src = f"{HPC_HOST}:{args.hpc_base}/data/task2/task2_v3_organizer.jsonl"
        fetch_organizer(organizer_local, hpc_src)
    else:
        print(f"Using cached organizer file: {organizer_local}")

    organizer = load_organizer(organizer_local)
    print(f"Organizer loaded: {len(organizer)} records")

    # Step 2 & 3: build groups for each run
    all_groups = []
    for run_id in RUN_IDS:
        output_file = TASK2_INPUTS_DIR / run_id / "output.json"
        if not output_file.exists():
            print(f"ERROR: {output_file} not found", file=sys.stderr)
            sys.exit(1)
        groups = build_groups(run_id, output_file, organizer)
        sentences_total = sum(len(g["sentences"]) for g in groups) // max(len(groups) // len(set(g["qid"] for g in groups)), 1)
        # unique sentences per run (sentences list same across page groups of same qid)
        unique_qids = list(dict.fromkeys(g["qid"] for g in groups))
        n_sentences = sum(
            len(next(g for g in groups if g["qid"] == q)["sentences"])
            for q in unique_qids
        )
        print(f"{run_id}: {len(groups)} groups ({len(unique_qids)} questions, {n_sentences} sentences)")
        all_groups.extend(groups)

    # Write annotation_data.json
    out_file = DATA_DIR / "annotation_data.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"groups": all_groups}, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {out_file} ({len(all_groups)} groups)")

    # Initialize annotations.json if absent
    annotations_file = DATA_DIR / "annotations.json"
    if not annotations_file.exists():
        with open(annotations_file, "w", encoding="utf-8") as f:
            json.dump({}, f)
        print(f"Initialized empty {annotations_file}")
    else:
        print(f"Existing annotations preserved: {annotations_file}")

    print("\nReady. Start the server with:  python server.py")


if __name__ == "__main__":
    main()
