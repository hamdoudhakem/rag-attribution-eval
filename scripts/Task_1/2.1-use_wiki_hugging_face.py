import sys
import utils
import os
import pandas as pd
from datasets import load_dataset, load_from_disk

if len(sys.argv) != 5:
  print(
      "Usage : python use_wiki_hugging_face.py [wiki_HF_path] [target_page_titles_in_csv] [output_jsonl_file] [remaining_unfound_pages_txt]")
  exit(1)

wiki_HF_path = sys.argv[1]
titles_csv_path = sys.argv[2]
output_path = sys.argv[3]
remaining_titles_path = sys.argv[4]

##### Save or Load The Wiki dataset from disk #####
if not os.path.exists(wiki_HF_path):
  cache_dir = "./.cache/huggingface/datasets"
  os.makedirs(cache_dir)
  ds = load_dataset("wikimedia/wikipedia", "20231101.fr", cache_dir=cache_dir)
  ds.save_to_disk(wiki_HF_path)
else:
  ds = load_from_disk(wiki_HF_path)

ds = ds["train"]
print("Dataset size :", len(ds))
print(type(ds))

# Getting the The titles of the pages that I will need to search for
titles_df = pd.read_csv(titles_csv_path)
titles = [val for val in titles_df["title"].values]


# Loop through all wiki/huggingface pages to get the pages that I needed
docs = []
docs_count = 0
for i, d in enumerate(ds):
  if d["title"] in titles:
    docs.append({
        "doc_id": docs_count,
        "wiki_HF_id": d["id"],
        "title": d["title"],
        "source": "wikipedia",
        "url": d["url"],
        "text": d["text"]
    })

    docs_count += 1
    titles.remove(d["title"])

    if docs_count % 30 == 0:
      print(f"{int(docs_count/30)} - Writing 30 new entries")
      utils.writejsonl(output_path, docs, write_mode="a")
      docs = []

utils.writejsonl(output_path, docs, write_mode="a")
print(f"Ended with a document count of {docs_count + 1}")

with open(remaining_titles_path, "w", encoding="utf-8") as f:
  f.write(f"Ended with a document count of {docs_count + 1}.\n")
  f.write(f"Remaining unfound titles count is {len(titles)}, and they are :\n")
  for i, title in enumerate(titles):
    f.write(f"{i + 1} - {title}\n")
