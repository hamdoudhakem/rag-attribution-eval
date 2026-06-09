import math
import random
import sys
import json
import time

import pandas as pd
from bs4 import BeautifulSoup as bs
import wikipediaapi
from wikipediaapi import WikipediaPage
from wikipediaapi._page import BaseWikipediaPage

from utils import env_variables, get_page_json

if len(sys.argv) != 3:
  print("Usage: scrap_wiki.py [num_tasks] [task_index]")
  exit(0)

num_tasks = int(sys.argv[1])
task_index = int(sys.argv[2])

# Initial Setup
# # without this the libraries like "lxml" won't seem to work
# chemin_venv = "/home/hhamdoud/.local/lib/python3.12/site-packages"
# if chemin_venv not in sys.path:
#   sys.path.insert(0, chemin_venv)
#   print(f"\n[!] Task{task_index} : Chemin forcé ajouté : {chemin_venv}")

root_link = "https://fr.wikipedia.org/wiki/Catégorie:Transport_ferroviaire_en_France"
user_agent = f'Mozilla/5.0 ({env_variables.CONTACT_EMAIL})'
root_page_title = "Catégorie:Transport ferroviaire en France"
max_sleep_time = 4  # max seconds between calls API calls


def scrap(page: WikipediaPage, route=root_page_title, count_id=0, level=0, max_level=3) -> list:
  doc_id = f"{task_index}.{count_id}"

  # end case : if it's a page
  if page.ns != wikipediaapi.Namespace.CATEGORY:
    time.sleep(random.randint(1, int(max_sleep_time / 2)))

    page_data = get_page_json(page, doc_id, route, user_agent)
    print(f"Task {task_index} : At level {level}, Took care of the page :\"{page_data['title']}\"")
    return [page_data]

  # if it's over the max_level, we stop here even if it's a catégorie page
  if page.ns == wikipediaapi.Namespace.CATEGORY and level >= max_level:
    print(f"Task {task_index} : Hit the max level limit at {level}, simplified the catégorie :\"{page.title}\"")

    return [{
        "doc_id": doc_id,
        "title": page.title,
        "source": "wikipedia",
        "url": page.fullurl,
        "route": route,
        "route_depth": len(route.split("/")),
        "wiki-api_text": page.text,
    }]

  # recursive case : if it's a catégorie and we still are below the max_level
  json_pages = []

  for c in page.categorymembers.values():
    time.sleep(random.randint(1, int(max_sleep_time)))

    scrapped_pages = scrap(
        c,
        f"{route}/{c.title}",
        count_id,
        level=level + 1,
        max_level=max_level
    )
    json_pages += scrapped_pages

    count_id += len(scrapped_pages)

  print(f"Task {task_index} : At level {level}, Took care of the catégorie :\"{page.title}\" pages")
  return json_pages


def scrap_from_root(page: WikipediaPage, start_index, end_index, root_name, max_level):
  i = 0
  json_pages = []
  # this number needs to be bigger than the num of docs.
  # the goal is to have the ids have a chronological order (if not, then it can be set to 0)
  count_id = 10**7
  for c in page.categorymembers.values():
    if i >= start_index and i < end_index:
      new_pages = scrap(c, f"{root_name}/{c.title}", count_id, level=1, max_level=max_level)
      json_pages += new_pages

      count_id += len(new_pages)

    i += 1

  return json_pages


############## MAIN FUNCTION ##############
def main():
  wiki_root = wikipediaapi.Wikipedia(
      user_agent=f'Mozilla/5.0 ({env_variables.CONTACT_EMAIL}) Chrome/147.0.0.0 Safari/537.36',
      language='fr',
      extract_format=wikipediaapi.ExtractFormat.WIKI
  )

  page_root = wiki_root.page("Catégorie:Transport ferroviaire en France")

  # SLURM Multi-Task Management Code
  categorymembers_root = page_root.categorymembers
  members_per_task = int(len(categorymembers_root) / num_tasks)

  start_index = task_index * members_per_task
  end_index = (task_index + 1) * members_per_task

  if task_index == num_tasks - 1:
    end_index = len(categorymembers_root.values())

  # Call the scraping method
  final_dict = scrap_from_root(
      page_root,
      start_index,
      end_index,
      "Catégorie:Transport ferroviaire en France",
      max_level=math.inf
  )

  # Writing the final result
  with open(f"./final_result_0{task_index}.jsonl", "a", encoding="utf-8", newline="\n") as f:
    for item in final_dict:
      json_dict = json.dumps(item, ensure_ascii=False)
      f.write(json_dict + "\n")

  return


main()
