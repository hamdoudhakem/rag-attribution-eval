import utils
import sys

if len(sys.argv) != 4:
  print("Usage: python merge_jsonl_datasets.py [first_jsonl] [second_jsonl] [output_file_path]")
  exit(0)

first_jsonl_path = sys.argv[1]
second_jsonl_path = sys.argv[2]
output_file_path = sys.argv[3]

if not first_jsonl_path.endswith(".jsonl") or not second_jsonl_path.endswith(".jsonl") or not output_file_path.endswith(".jsonl"):
  print("The files needs to be valid, existing JSONL format files!")
  exit(0)

first_jsonl: list[dict] = utils.load_jsonl(first_jsonl_path)
second_jsonl: list[dict] = utils.load_jsonl(second_jsonl_path)
print("Loaded files!")

res = first_jsonl + second_jsonl

fields_to_keep = ["title", "source", "url", "text"]  # and "doc_id" that I will add directly

print("Adapting doc_ids and fields...")
for index in range(len(res)):
  tmp_obj = {
      "doc_id": index,
      "source": "",
      "title": "",
      "url": "",
      "text": "",
  }

  # Delete non-generic fields
  for key in res[index].keys():
    if key in fields_to_keep:
      tmp_obj[key] = res[index][key]

  res[index] = tmp_obj

print("Adapted doc_ids and fields!")

utils.writejsonl(output_file_path, res)
print("Savec Merged JSONL!")
