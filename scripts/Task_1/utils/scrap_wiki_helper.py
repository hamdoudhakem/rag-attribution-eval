import re
import pandas as pd
import wikipediaapi
from wikipediaapi._page import BaseWikipediaPage

from io import StringIO
import requests
from bs4 import Tag, BeautifulSoup as bs
from thefuzz import process  # maybe I will do some fuzzy matching using fuzz.partial_ratio()

from utils import env_variables


def get_page_json(page: BaseWikipediaPage, doc_id: str, route: str, user_agent: str):
  """
  return this structure representing the page :

    {
      "doc_id": ...,
      "title": ...,
      "source": "wikipedia",
      "url": ...,
      "route": ...,
      "route_depth": ...,
      "html_raw": ...,
      "wiki-api_text": ...,
      "text": ..., # contains the inserted tables on json format
      "sections": ...
    }  
  """

  # request the page full HTML code to be able to locate the tables
  response = requests.get(page.fullurl, headers={
      "User-Agent": user_agent,
      "From": f"{env_variables.CONTACT_EMAIL}",
  })
  response.encoding = "utf-8"

  text_with_tables_added = get_text_with_tables(page.text, response)
  sections_json = get_section_json_dict(page)

  return {
      "doc_id": doc_id,
      "title": page.title,
      "source": "wikipedia",
      "url": page.fullurl,
      "route": route,
      "route_depth": len(route.split("/")),
      "html_raw": response.text,
      "wiki-api_text": page.text,
      "text": text_with_tables_added,
      "sections": sections_json
  }


def get_text_with_tables(text: str, request_reponse: requests.Response) -> str:
  try:
    # Séparation du texte de toute la page en paragraphes
    paragraphs = text.split('\n')
    paragraphs = [p for p in paragraphs if len(p.strip()) > 0]

    # obtention de tous les tables avec "bs" et en "DataFrame"
    soup = bs(request_reponse.content, 'html.parser')
    tables = soup.find_all('table', class_='wikitable')[::-1]

    fake_file = StringIO(request_reponse.text)
    dfs = pd.read_html(fake_file, attrs={"class": "wikitable"}, flavor="bs4")[::-1]

    # if there are no paragraphs, jus return the tables as text
    if len(paragraphs) == 0:
      for df in dfs:
        text += f"\n{clean_df_table_to_json(df)}"
      return text

    # returns the text with the tables inserted
    for i, tab in enumerate(tables):
      text = insert_table_in_correct_position(tab, text, paragraphs, dfs[i])

  except Exception as e:
    # This would mainly happen because of the read_html() not finding any table
    print(f"Error in \"get_text_with_tables\", Page Name : {soup.title.string} of type :", str(e))

  return text


def insert_table_in_correct_position(tab: Tag, text: str, paragraphs: list[str], df: pd.DataFrame):
  try:
    # find the paragraph preceding the table
    html_text = tab.find_previous("p").text

    # Nettoyage de base du texte HTML pour aider le fuzzy
    previous_paragraph_text = re.sub(r'\[.*?\]', '', html_text)  # Enlever les [1], [N 1], etc.
    previous_paragraph_text = previous_paragraph_text.replace('\xa0', ' ')  # Enelver les charactére bizarre

    # Fuzzy Match avec chaque paragraph de la page
    (best_match, score) = process.extractOne(previous_paragraph_text, paragraphs)

    # On s'assure que les deux paragraphes ont à peu près la même taille.
    longueur_html = len(previous_paragraph_text)
    longueur_match = len(best_match)
    ratio_taille = min(longueur_html, longueur_match) / max(longueur_html, longueur_match)

    # Inserer le tableau si ces le bon paragraph
    if score >= 90 and ratio_taille > 0.75:
      match_index = text.find(best_match)
      text = text[:match_index + longueur_match] + \
          f"\n{clean_df_table_to_json(df)}\n" + text[match_index + longueur_match:]
    else:
      # it's pasted at the end if we don't know which paragraph preceds it
      text = text + f"\n{clean_df_table_to_json(df)}"
  except:
    # it's pasted at the end if There are no paragraphs preceding it (or any problems)
    text = text + f"\n{clean_df_table_to_json(df)}"

  return text


def get_section_json_dict(page: BaseWikipediaPage | wikipediaapi.WikipediaPageSection):
  """
    returns an object like this:    
    {
      "summary": ...,
      "sections" {
        "section_title1": {
          "level":...,
          "text":...,
          "sections":{
            ...
          }
        },
        "section_title2": {
          ...
        },
      }
    }
  """

  json_dict = {}

  if isinstance(page, BaseWikipediaPage):
    json_dict["summary"] = page._summary
  else:
    json_dict["level"] = page.level
    json_dict["text"] = page.text

  if len(page.sections) == 0:
    return json_dict

  json_dict["sections"] = {}
  for sec in page.sections:
    json_dict["sections"][sec.title] = get_section_json_dict(sec)

  return json_dict


def clean_df_table_to_json(df: pd.DataFrame):
  """
   replace the index column (the one with 0,1,...) with
   the actuel table index column (so if the table speaks about birds for exemple
   I will have at the start of each row the actuel bird type or name).

   return: a json version of the table
  """

  # get rid if the index column added by df (so {"0":{"row1":...}} becomes {"row1":{...}})
  index_col = df[df.keys()[0]]

  if index_col.is_unique:
    df = df.set_index(index_col)
    df = df.drop(index_col.name, axis=1)
    return df.to_json(orient="index", force_ascii=False)

  return df.to_json(orient="index", force_ascii=False)


def find_matches_in_text(text: str, pattern_str: str):
  """
    returns list of indexes as spans [start_index, end_index[
    of the matched pattern in the text. 

    example: [(2,6),(13,17)]
  """
  matches = []

  offset = 0
  pattern = re.compile(pattern_str)
  while m := re.search(pattern, text):
    span = m.span()
    matches.append((span[0] + offset, span[1] + offset))
    text = text[span[1] - 1:]
    offset += span[1] - 1

  return matches
