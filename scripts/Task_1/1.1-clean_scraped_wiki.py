import re
import sys
import utils as utils
import os

if len(sys.argv) != 2:
  print("Usage: python clean_scraped_wiki.py [Jsonl_file_NAME] - (example: final_result_00)")
  exit(0)

file_name = sys.argv[1]
# Nettoyer l'extension si l'utilisateur la met par erreur
file_name = file_name.replace(".jsonl", "")
file_path = os.path.join("./data", f"{file_name}.jsonl")

keys_to_copy = [
    "title",
    "url",
    "route",
    "route_depth",
    "html_raw",
    "wiki-api_text",
    "text",
    "sections",
]


def clean_text(text):
  """
    Clean up the text:
      - Remove the references
      - Remove everything from 'Notes et références' or 'Voir aussi' onwards
  """

  if not isinstance(text, str):
    return text

  # ### Get rid of the references
  matches = utils.find_matches_in_text(text, r"\[.*?\]")
  for start, end in reversed(matches):
    text = text[:start] + text[end:]

  # ### Get rid of the part 'Notes et références' or 'Voir aussi' onwards
  # Find the earliest occurrence of either phrase
  idx1 = text.find("Notes et références")
  idx2 = text.find("Voir aussi")

  # Get the minimum index (earliest occurrence)
  indices = [i for i in [idx1, idx2] if i != -1]

  if not indices:
    return text  # neither phrase found, keep all text

  # Return text up to the earliest phrase
  return text[:min(indices)]


res = utils.load_jsonl(file_path)

for index in range(len(res)):
  res[index] = {
      "doc_id": index,
      "source": "wikipedia",
      **{k: res[index].get(k) for k in keys_to_copy},
  }

  # Clean the text field
  if "text" in res[index]:
    res[index]["text"] = clean_text(res[index]["text"])

output_path = os.path.join("./data", f"{file_name}_cleaned.jsonl")
utils.writejsonl(output_path, res)
