import os
import json
import re
import sys
import utils

if len(sys.argv) != 3:
  print(
      "Usage: python convert_sncf_corpus_to_jsonl.py [input_folder_path] (example: files/corpus_OP) [output_file_path]")
  exit(0)

folder_path = sys.argv[1]
output_file_path = sys.argv[2]
if not output_file_path.endswith(".jsonl"):
  print("The output file needs to be in JSONL format!")
  exit(0)


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


def is_table_value(s):
  """
  Détermine si une ligne isolée ressemble à une cellule de tableau SNCF.
  Accepte : "-" , "2570" , "710m" , "135t", "1"
  """
  return bool(re.match(r'^\s*(?:-|\d+(?:[.,]\d+)?[a-zA-Z]{0,3})\s*$', s))


def reconstruct_vertical_tables(text):
  """
  Détecte les colonnes de tableaux éclatées verticalement et les convertit en JSON.
  Puis fusionne les colonnes adjacentes.
  """
  lines = text.split('\n')
  new_lines = []

  # --- PASSE 1 : Détection des colonnes ---
  i = 0
  while i < len(lines):
    line = lines[i].strip()

    if not line:
      new_lines.append(lines[i])
      i += 1
      continue

    # On anticipe : est-ce que les lignes suivantes sont des valeurs ?
    j = i + 1
    values = []
    while j < len(lines):
      next_line = lines[j].strip()
      if not next_line:
        j += 1
        continue  # On ignore les espaces vides
      if is_table_value(next_line):
        values.append(next_line)
        j += 1
      else:
        break

    # S'il y a au moins 2 valeurs consécutives, la ligne actuelle EST un en-tête !
    if len(values) >= 2 and len(line) < 100:
      obj = {line: values}
      new_lines.append("JSON_TABLE_START")
      new_lines.append(json.dumps(obj, ensure_ascii=False))
      new_lines.append("JSON_TABLE_END")
      i = j  # On fait un bond pour sauter toutes les valeurs qu'on a déjà capturées
    else:
      new_lines.append(lines[i])
      i += 1

  # --- PASSE 2 : Fusion horizontale des tableaux ---
  merged_text = []
  in_table = False
  current_table = {}

  for line in new_lines:
    s_line = line.strip()

    if s_line == "JSON_TABLE_START":
      in_table = True
    elif s_line == "JSON_TABLE_END":
      pass  # On gère la fermeture quand un vrai texte réapparaît
    elif in_table:
      if s_line.startswith('{') and s_line.endswith('}'):
        # Extraction du JSON
        try:
          data = json.loads(s_line)
          for k, v in data.items():
            new_key = k
            counter = 1
            # Si la colonne existe déjà, on la renomme au lieu de l'écraser
            while new_key in current_table:
              new_key = f"{k}_{counter}"
              counter += 1
            current_table[new_key] = v
        except:
          pass
      elif not s_line:
        pass  # On maintient le tableau ouvert s'il y a juste un saut de ligne
      else:
        # On est tombé sur du texte normal, on clôture et sauvegarde le tableau !
        merged_text.append(json.dumps(current_table, ensure_ascii=False))
        merged_text.append(line)  # On rajoute le texte normal qui a coupé le tableau
        in_table = False
        current_table = {}
    else:
      merged_text.append(line)

  # Si le document se termine en plein milieu d'un tableau
  if in_table and current_table:
    merged_text.append(json.dumps(current_table, ensure_ascii=False))

  return '\n'.join(merged_text)


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


def main():
  input_dir = folder_path
  output_file = output_file_path

  if not os.path.exists(input_dir):
    print(f"Erreur : Le dossier '{input_dir}' n'existe pas.")
    sys.exit(1)

  result_docs = []
  current_doc_id = 0

  for filename in os.listdir(input_dir):
    if not filename.endswith('.txt'):
      continue

    filepath = os.path.join(input_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
      raw_text = f.read()

    # Traitement complet
    title, clean_text = process_document(raw_text)

    # Création de l'objet selon le Schéma exact demandé
    doc = {
        "doc_id": current_doc_id,
        "title": title,
        "source": "Réseau SNCF",
        "url": f"local://{filename}",
        "text": clean_text
    }

    result_docs.append(doc)
    current_doc_id += 1
    # print(f"Done with file {filename}!")

  # Ecriture dans le JSONL final
  utils.writejsonl(output_file, result_docs)

  print(f"✅ Conversion réussie : {current_doc_id} fichiers traités et sauvegardés dans {output_file}")


if __name__ == "__main__":
  main()
