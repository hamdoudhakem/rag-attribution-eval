import math
import sys
import utils
import json
import os
import re
from thefuzz import fuzz

if len(sys.argv) != 3:
  print("Usage: python create_chunks.py [Jsonl_file_path] [output_jsonl_file_path]")
  exit(0)

input_file = sys.argv[1]
output_dir = sys.argv[2]

default_chunk_length = 130
min_chunk_length = 20
topics = [
    "voie",
    "caténaire",
    "matériel roulant",
    "signalisation",
    "incident",
    "rail"
]


def separate_text_into_words(text: str, tables_spans):
  """
    separate the text into words and each table row will be considered a single word.

    returns: 

      worded_text : list of words
      phrases_indeces : contains 2 lists. A list of "." indexes in worded_text, then another list for "," indexes.
  """
  worded_text: list[str] = []
  previous_table_end = 0

  for table_span in tables_spans:
    # Utilisation de .split() (sans argument) pour gérer proprement
    # les espaces multiples et sauts de ligne sans créer de chaînes vides ""
    worded_text += text[previous_table_end:table_span["start"]].split()

    # Sécurisation des données du tableau
    for row_index, row_data in table_span["table"].items():
      # on force la valeur en string ou JSON pour éviter les crashs si listes imbriquées
      data_str = json.dumps(row_data, ensure_ascii=False) if isinstance(row_data, (dict, list)) else str(row_data)
      worded_text.append(f"\"{row_index}\":{data_str}")

    previous_table_end = table_span["end"]

  worded_text += text[previous_table_end:].split()

  phrases_indices = [[], []]
  for index, word in enumerate(worded_text):
    if "." in word:
      phrases_indices[0].append(index)
    elif "," in word:
      phrases_indices[1].append(index)

  return worded_text, phrases_indices


def get_min_closest(array, key):
  try:
    return min(array, key=key)
  except:
    return None


def get_closest_phrase_index(phrases_indices, end_index, start_index=None, max_gap=15):
  point_candidates = [p for p in phrases_indices[0] if (start_index is None or p > start_index)]
  comma_candidates = [p for p in phrases_indices[1] if (start_index is None or p > start_index)]
  if not comma_candidates and not point_candidates:
    return None

  closest_point = get_min_closest(point_candidates, key=lambda p: abs(p - end_index))
  if closest_point is None or abs(closest_point - end_index) > max_gap:
    closest_comma = get_min_closest(comma_candidates, key=lambda p: abs(p - end_index))
    if closest_comma is None or abs(closest_comma - end_index) <= max_gap:
      return None
    else:
      return closest_comma

  return closest_point


def get_chunk_text(previous_chunk_end_index: int, worded_text: list[str], phrases_indices: list[list[int]]):
  start_index = previous_chunk_end_index
  end_index = min(start_index + default_chunk_length, len(worded_text))
  max_gap = 15

  in_phrase = False
  closest = get_closest_phrase_index(phrases_indices, end_index, start_index, max_gap)

  if closest is not None and closest > start_index:
    # +1 pour inclure le mot qui contient la ponctuation (le "." ou la ",")
    end_index = closest + 1
    in_phrase = True

  # avoid empty chunk
  if end_index <= start_index:
    end_index = min(start_index + default_chunk_length, len(worded_text))

  # avoid cutting inside unclosed parentheses
  temp_chunk_str = " ".join(worded_text[start_index:end_index])

  # Si on a ouvert plus de parenthèses qu'on en a fermé...
  if temp_chunk_str.count("(") > temp_chunk_str.count(")"):
    remainder = worded_text[end_index:]
    # On cherche le prochain mot qui contient la parenthèse fermante
    for idx, word in enumerate(remainder):
      if ")" in word:
        end_index += idx + 1
        break

  # clip it's max value
  end_index = min(end_index, len(worded_text))
  worded_chunk = worded_text[start_index:end_index]

  return worded_chunk, end_index


def get_chunk_topic(worded_chunk: list[str], title: str):
  if not topics:
    return "incident"

  chunk_text = " ".join(worded_chunk).lower()
  title_text = title.lower()

  topic_scores = {topic: 0 for topic in topics}
  for topic in topics:
    topic_scores[topic] += chunk_text.count(topic)

  if max(topic_scores.values()) == 0:
    for topic in topics:
      for word in chunk_text.split():
        score = fuzz.partial_ratio(word, topic)
        if score > topic_scores[topic]:
          topic_scores[topic] = score

      for word in title_text.split():
        score = fuzz.partial_ratio(word, topic)
        if score > topic_scores[topic]:
          topic_scores[topic] = score

  best_topic = max(topic_scores, key=topic_scores.get)

  if topic_scores[best_topic] == 0:
    return "non-affilier"

  return best_topic


def main():
  res = []
  count_id = 0
  docs = utils.load_jsonl(input_file)
  print("Loaded File!")

  print("Started Chunking docs...")
  for doc in docs:
    tables_spans = utils.find_json_objects_with_spans(doc["text"])
    worded_text, phrases_indices = separate_text_into_words(doc["text"], tables_spans)

    text_length = len(worded_text)
    previous_chunk_end_index = 0

    # Ne s'arréter que a la fin du texte
    while previous_chunk_end_index < text_length:
      worded_chunk, end_index = get_chunk_text(previous_chunk_end_index, worded_text, phrases_indices)

      # Sécurité anti-boucle infinie
      if end_index <= previous_chunk_end_index:
        break

      # If a chunk is too small, then fuse it with the previous chunk if possible
      if len(worded_chunk) < min_chunk_length and count_id > 0 and res[count_id - 1]["doc_id"] == doc.get("doc_id", ""):
        res[count_id - 1]["text"] += f" {" ".join(worded_chunk)}"
      else:
        # Create a new Chunk
        chunk = {
            "id": count_id,
            "doc_id": doc.get("doc_id", ""),
            "source": doc.get("source", ""),
            "doc_title": doc.get("title", ""),
            "topic": get_chunk_topic(worded_chunk, doc.get("title", "")),
            "url": doc.get("url", ""),
            "text": " ".join(worded_chunk),
        }

        res.append(chunk)
        count_id += 1

      previous_chunk_end_index = end_index
  print("Finished Docs Chunking!")

  utils.writejsonl(output_dir, res)
  print(f"Extraction terminée. {count_id} chunks sauvegardés dans {output_dir}")


if __name__ == "__main__":
  main()
