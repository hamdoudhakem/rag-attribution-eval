import json
import os
import pickle
import re


def load_jsonl(path: str):
  with open(path, "r", encoding="utf-8") as f:
    return [json.loads(line) for line in f]


def writejsonl(path: str, obj_iter, write_mode="w", newline="\n"):
  with open(path, write_mode, encoding="utf-8", newline=newline) as f:
    for item in obj_iter:
      json_dict = json.dumps(item, ensure_ascii=False)
      f.write(json_dict + "\n")


def find_json_objects_with_spans(text):
  decoder = json.JSONDecoder()
  results = []
  i = 0

  while i < len(text):
    start = text.find("{", i)
    if start == -1:
      break

    try:
      obj, end = decoder.raw_decode(text[start:])
      results.append({
          "start": start,
          "end": start + end,
          "table": obj,
      })
      i = start + end
    except json.JSONDecodeError:
      i = start + 1

  return results


def save_object(obj, path):
  try:
    with open(path, "wb") as f:
      pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)
    print("Object Saved To disk!")
  except Exception as e:
    print("Failed to save object: ", str(e))


def load_object(path):
  try:
    with open(path, "rb") as f:
      return pickle.load(f)
  except Exception as e:
    return None


def clean_text_for_bm25(text: str):
  """
    Cleans text by using 'lower case', deleting paenthesis and
    '.' and ',' without harming the decimal numbers. Also fixing 
    'characterised' text like "F e u i l l e"
  """

  # Fixes text like "F e u i l l e"
  def fix_single_character_passages(text: str):
    text_array = [val.strip() for val in text.split() if val.strip()]
    if len(text_array) == 0:
      return text

    new_text_array = []

    current_word_index = -1
    new_word = True
    authorised_single_chars = ['a', 'à']

    for i in range(len(text_array)):
      char_or_word = text_array[i]
      if len(char_or_word) == 1 and char_or_word.isalpha() and char_or_word not in authorised_single_chars or char_or_word[0] == "'":
        if new_word:
          new_text_array.append("")
          current_word_index += 1
          new_word = False

        new_text_array[current_word_index] += char_or_word
      else:
        new_text_array.append(char_or_word)
        current_word_index += 1
        new_word = True

    return " ".join(new_text_array)

  new_token = text.lower()
  new_token = new_token.replace("(", "").replace(")", "")
  new_token = re.sub(r"(\.|,)(\s|$)", lambda m: m.group(2), new_token)
  new_token = fix_single_character_passages(new_token)

  return new_token
