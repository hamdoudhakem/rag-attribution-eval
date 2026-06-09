import re
import sys
import utils

if len(sys.argv) != 3:
  print("Usage: python clean_datasets_artifacts.py [input_jsonl] [output_jsonl_path]")
  exit(0)

input_jsonl_path = sys.argv[1]
output_jsonl_path = sys.argv[2]


def clean_text(text: str):
  # Sécurité : vérifier que le champ n'est pas vide ou None
  if not isinstance(text, str):
    return text

  # To Suerveille :
  # 1. Suppression des séquences Unicode échappées (ex: littéralement "\u0017")
  # Cette Regex cible précisément les 6 caractères de texte formant \u0000 jusqu'à \u001F
  cleaned = re.sub(r'\\u00[0-1][0-9a-fA-F]', '', text)

  # 2. Caractères de contrôle ASCII purs (Invisibles) -> SUPPRESSION
  cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', cleaned)

  # 3. Caractères "Zéro-largeur" et BOM (Invisibles) -> SUPPRESSION
  cleaned = re.sub(r'[\u200B-\u200D\uFEFF]', '', cleaned)

  # 4. Caractères de remplacement (erreurs d'encodage) -> SUPPRESSION
  cleaned = re.sub(r'\uFFFD', '', cleaned)

  # 5. Espaces "exotiques" (insécables \xa0, etc.) -> REMPLACEMENT PAR ESPACE NORMAL
  cleaned = re.sub(r'[\xa0\u2000-\u200A\u202F\u205F\u3000]', ' ', cleaned)

  # 6. Nettoyage final : compacte les espaces multiples et enlève les bordures
  cleaned = re.sub(r' +', ' ', cleaned).strip()

  # To Suerveille :
  # 7. Nettoyage des clés JSON vides qui pourraient résulter de l'étape 4
  # Transforme {"": ["16h", "07h"]} en {["16h", "07h"]} pour alléger le texte
  # cleaned = cleaned.replace('"": ', '')

  return cleaned


def main():
  docs = utils.load_jsonl(input_jsonl_path)

  print("Started Cleaning...")
  for doc in docs:
    doc["title"] = clean_text(doc["title"])
    doc["text"] = clean_text(doc["text"])
  print("Dataset Cleaned!")

  utils.writejsonl(output_jsonl_path, docs)


if __name__ == "__main__":
  main()
