from rank_bm25 import BM25Okapi
import pickle
import utils
import sys
import os
import re

if len(sys.argv) != 4:
  print(
      "Usage: python create_inverted_index.py [input_jsonl_file] [output_tokinized_corpus_pkl_file] [output_bm25_inverted_index_pkl_file]")
  exit(0)

input_file_path = sys.argv[1]
output_tokenized_corpus_pkl_path = sys.argv[2]
output_bm25_inverted_index_pkl_path = sys.argv[3]

corpus = utils.load_jsonl(input_file_path)

tokenized_corpus = utils.load_object(output_tokenized_corpus_pkl_path)
if tokenized_corpus is None:
  tokenized_corpus = [chunk["text"] for chunk in corpus]
  utils.save_object(tokenized_corpus, output_tokenized_corpus_pkl_path)

# print("Before :\n", tokenized_corpus[0].split())

# Cleans text
for doc_tokens_index in range(len(tokenized_corpus)):
  new_token = utils.clean_text_for_bm25(tokenized_corpus[doc_tokens_index])

  tokenized_corpus[doc_tokens_index] = new_token
print("Prepared Data!")

# split each doc into "words"
tokenized_corpus = [chunk.split() for chunk in tokenized_corpus]

# print("After : \n", tokenized_corpus[0])

bm25 = BM25Okapi(tokenized_corpus)
print("Created Index!")

saved_file_path = output_bm25_inverted_index_pkl_path
utils.save_object(bm25, saved_file_path)

print(f"Saved inverted Index to disk as : {saved_file_path}!")
