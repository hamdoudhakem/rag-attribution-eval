import numpy as np
from rank_bm25 import BM25Okapi
import pickle
import utils
import sys
import os
import re

index: BM25Okapi = utils.load_object("./data/inverted index/inverted_index_docs_dataset_chunked.pkl")
corpus: list[list[str]] = utils.load_object("./data/inverted index/tokenized_docs_dataset_chunked.pkl")

print("BM25 Index corpus size: ", index.corpus_size)
print("True Corpus size: ", len(corpus))

# Weird text at this part
# print(corpus[147875])

query = """
Article 202. Consignes temporaires Lorsque l'élaboration d’une consigne temporaire est nécessaire et qu’elle concerne un ou plusieurs opérateurs ferroviaires (par exemple, neutralisation ou modification provisoire d’une installation de sécurité suite à incident), l'établissement local du service chargé de la gestion des circulations :  la transmet par télécopie ou courriel (envoyé avec demande d'accusé de réception) au correspondant de l’opérateur ferroviaire chargé de la documentation, et conserve la trace de ces envois,  en cas d’urgence et en particulier en dehors des jours et heures ouvrables, prend en outre les dispositions utiles pour que la consigne temporaire soit : o transmise par télécopie ou courriel (dans les mêmes conditions que cidessus) au responsable d'astreinte désigné par l'opérateur ferroviaire, l'établissement local du service chargé de la gestion des circulations conservant la
"""

query = utils.clean_text_for_bm25(query).split()

docs = index.get_top_n(query, corpus, 5)
for i, doc in enumerate(docs):
  print(f"{i} - {doc}\n")
