import requests
import time
import pandas as pd
import wikipediaapi
import os
from utils import env_variables

# variables d'environnement
root_link = "https://fr.wikipedia.org/wiki/Catégorie:Transport_ferroviaire_en_France"
user_agent = f'Mozilla/5.0 ({env_variables.CONTACT_EMAIL}) Chrome/147.0.0.0 Safari/537.36'
root_page_title = "Catégorie:Transport ferroviaire en France"
wait_time = 1.5  # second

# On prépare le fichier CSV
csv_file_path = "./related_pages_stream.csv"
pd.DataFrame(columns=["title", "url", "route"]).to_csv(csv_file_path, index=False, encoding="utf-8")

# titles to Skip
prohibited_titles = ["Commune desservie", "culture populaire"]


def not_in_prohibited(title):
  for prohibited_title in prohibited_titles:
    if prohibited_title in title:
      return False

  return True


def scrap_from_root(page: wikipediaapi.WikipediaPage, route: str, visited_categories=None):
  # Initialisation du set pour éviter les boucles infinies de catégories
  if visited_categories is None:
    visited_categories = set()

  related_pages = []

  # On marque cette catégorie comme visitée
  visited_categories.add(page.title)

  for c in page.categorymembers.values():
    if c.ns != wikipediaapi.Namespace.CATEGORY:
      # Construction manuelle de l'URL -> ZERO APPEL API SUPPLÉMENTAIRE
      manual_url = f"https://fr.wikipedia.org/wiki/{c.title.replace(' ', '_')}"

      page_data = {
          "title": c.title,
          "url": manual_url,
          "route": route
      }
      related_pages.append(page_data)

      # Sauvegarde immédiate en mode "append" (ajout à la fin du fichier)
      # Ça protège tes données en cas de crash sans surcharger la RAM
      df = pd.DataFrame([page_data])
      df.to_csv(csv_file_path, mode='a', header=False, index=False, encoding="utf-8")

    else:
      # Éviter de looper en boucle sur les méme catégories
      if c.title not in visited_categories and not_in_prohibited(c.title):

        time.sleep(wait_time)
        print(f"Exploration de la catégorie : {c.title}")

        new_pages = scrap_from_root(c, f"{route}/{c.title}", visited_categories)
        related_pages.extend(new_pages)

  return related_pages


############## MAIN FUNCTION ##############
def main():
  wiki_root = wikipediaapi.Wikipedia(
      user_agent=user_agent,
      language='fr',
      extract_format=wikipediaapi.ExtractFormat.WIKI
  )

  page_root = wiki_root.page(root_page_title)

  print("Début du scraping allégé...")
  related_pages = scrap_from_root(page_root, root_page_title)

  print(f"Terminé ! {len(related_pages)} pages trouvées et sauvegardées dans {csv_file_path}.")


if __name__ == "__main__":
  main()
