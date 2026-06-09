import os
import json
import re
import sys
import utils

if len(sys.argv) != 3:
  print(
      "Usage: python convert_sncf_corpus_to_jsonl.py [input_TXT_file_path] [output_TXT_file_path]")
  exit(0)

input_file_path = sys.argv[1]
output_file_path = sys.argv[1]


def clean_gibberish(text):
  """
  Supprime les blocs de texte "sans sens" (gibberish).
  On coupe par \n\n, et si un bloc est majoritairement composé de symboles, on le supprime.
  """
  blocks = text.split('\n\n')
  good_blocks = []

  for block in blocks:
    letters_count = sum(c.isalpha() for c in block)
    total_chars = len(block.replace(' ', '').replace('\n', ''))

    if total_chars > 0:
      ratio = letters_count / total_chars
      # Si moins de 20% de lettres et présence de symboles bizarres
      if ratio < 0.2 and any(char in block for char in "%&#<>={}();"):
        continue
    good_blocks.append(block)

  return '\n\n'.join(good_blocks)


def reconstruct_vertical_tables(text):
  """
  Trouve les suites de nombres (avec \n) précédées d'un mot d'en-tête et les transforme en JSON.
  Fusionne ensuite les objets JSON qui se suivent en un seul gros tableau.
  """
  # Regex : Un en-tête (1 à 60 caractères), puis une suite d'au moins 2 valeurs séparées par \n
  # Une valeur est : un tiret "-", ou un nombre suivi potentiellement de décimales et d'une unité courte ("m", "t")
  value_re = r'\s*(?:-|\d+(?:[.,]\d+)?[a-zA-Z]{0,3})\s*'
  pattern = r'(?m)^([A-Za-zÀ-ÿ0-9\s/-]{1,60})\n((?:' + value_re + r'\n){1,}' + value_re + r')(?=\n|$)'

  def table_replacer(match):
    header = match.group(1).strip()
    raw_values = match.group(2)
    values = [v.strip() for v in raw_values.split('\n') if v.strip()]
    obj = {header: values}
    return f"\nJSON_TABLE_START\n{json.dumps(obj, ensure_ascii=False)}\nJSON_TABLE_END\n"

  text = re.sub(pattern, table_replacer, text)

  # 2. Fusion des colonnes adjacentes en un seul objet JSON
  lines = text.split('\n')
  new_lines = []
  i = 0
  while i < len(lines):
    line = lines[i].strip()

    if line == "JSON_TABLE_START":
      i += 1
      try:
        merged_obj = json.loads(lines[i].strip())
        i += 2  # On saute la ligne JSON et la ligne END

        # Regarder si les lignes suivantes sont aussi des tableaux
        while i < len(lines):
          next_line = lines[i].strip()
          if not next_line:  # On ignore les lignes vides entre deux tableaux
            i += 1
            continue

          if next_line == "JSON_TABLE_START":
            i += 1
            next_obj = json.loads(lines[i].strip())

            # Sécurité : Si l'en-tête existe déjà (ex: deux colonnes "1"), on l'ajoute sans écraser
            for k, v in next_obj.items():
              if k in merged_obj:
                merged_obj[k + "_bis"] = v
              else:
                merged_obj[k] = v

            i += 2  # On saute le JSON et le END
          else:
            break

        # On insère l'objet fusionné proprement
        new_lines.append(json.dumps(merged_obj, ensure_ascii=False))
        continue
      except Exception:
        pass
    else:
      new_lines.append(lines[i])
    i += 1

  return '\n'.join(new_lines)


def process_document(raw_text):
  """
  Applique la pipeline complète de nettoyage.
  """
  # 0. NETTOYAGE CRITIQUE : Supprimer les balises avant tout parsing
  text = re.sub(r'\\s*', '', raw_text)

  # 1. EXTRACTION DU TITRE (Avant le premier \n\n)
  parts = text.split('\n\n')
  title_candidate = parts[0].strip()

  bad_patterns = ["N°\nA\nB\nC\nD", "Dates\nEdition", "A\nB\nC"]

  if any(p in title_candidate for p in bad_patterns) or len(title_candidate) < 5 or title_candidate.count('\n') > 5:
    title = "Titre inconnu"
  else:
    title = title_candidate.replace('\n', ' ').strip()
    title = re.sub(r'\s{2,}', ' ', title)
    text = text[len(parts[0]):].lstrip()

  # 2. SUPPRESSION DU SOMMAIRE (Logique intelligente basée sur les points de suite)
  sommaire_match = re.search(r'(?i)^Sommaire\s*$', text, flags=re.MULTILINE)
  if sommaire_match:
    # On cherche dans les 4000 caractères suivants la dernière occurrence de "....."
    search_area = text[sommaire_match.end():sommaire_match.end()+4000]
    last_dot_match = list(re.finditer(r'\.{5,}', search_area))
    if last_dot_match:
      end_idx = sommaire_match.end() + last_dot_match[-1].end()
      next_newline = text.find('\n', end_idx)
      if next_newline != -1:
        end_idx = next_newline
      # On coupe le sommaire
      text = text[:sommaire_match.start()] + text[end_idx:]

  # 3. SUPPRESSION DU GIBBERISH
  text = clean_gibberish(text)

  # 4. SUPPRESSION DES SÉQUENCES DE CARACTÈRES PARASITES
  text = re.sub(r'_{3,}', ' ', text)      # _____ multiples
  text = re.sub(r'\.{3,}', ' ', text)     # ..... multiples
  text = re.sub(r'-{3,}', ' ', text)      # ----- multiples (préserve les "-" uniques des tableaux)
  text = re.sub(r'={3,}', ' ', text)      # ===== multiples
  text = re.sub(r'(¾[\s\n]*){2,}', ' ', text)  # ¾¾¾

  # 5. RECONSTRUCTION DES TABLEAUX VERTICAUX
  text = reconstruct_vertical_tables(text)

  # 6. REMPLACEMENT / SUPPRESSION DE CARACTÈRES SPÉCIAUX
  text = text.replace('', '-')
  text = text.replace('⇑', '')
  text = text.replace('⇓', '')
  text = text.replace('¿', '?')

  # 7. SÉPARATEURS INVISIBLES (Line/Paragraph separators des PDF)
  text = text.replace('\u2028', ' ').replace('\u2029', '\n')

  # 8. SUPPRESSION DES ESPACES MULTIPLES
  text = re.sub(r' {2,}', ' ', text)

  # 9. RÈGLE D'OR : REMPLACEMENT FINAL DES SAUTS DE LIGNE
  # Plus aucune occurrence de plus d'un "\n"
  text = re.sub(r'\n{2,}', '\n', text)

  return title, text.strip()


with open(input_file_path, "r", encoding="utf-8") as f:
  text = f.read()

title, text = process_document(text)

with open(output_file_path, "w", encoding="utf-8") as f:
  f.write(text)
