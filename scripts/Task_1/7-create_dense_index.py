import sys
import os
import torch
import faiss
from faiss import write_index, read_index
from transformers import AutoTokenizer, AutoModel
import utils
from typing import Union

if len(sys.argv) != 5:
  print(
      "Usage: python create_dense_index.py [input_jsonl_file] [output_tokenized_corpus_pkl_file] [output_embeddings_pkl_file] [output_index_file]")
  exit(0)

input_jsonl_path = sys.argv[1]
output_tokinized_corpus_pkl_path = sys.argv[2]
output_embeddings_pkl_path = sys.argv[3]
index_output_path = sys.argv[4]

corpus = utils.load_jsonl(input_jsonl_path)
device = torch.device("cuda")
BATCH_SIZE = 300

# Mean Pooling - Take attention mask into account for correct averaging


def mean_pooling(model_output, attention_mask):
  token_embeddings = model_output[0]  # First element of model_output contains all token embeddings
  input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
  return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)


def embed(model, encoded_input):
  input_ids: torch.Tensor = encoded_input["input_ids"]
  attention_mask: torch.Tensor = encoded_input["attention_mask"]

  result = torch.zeros(input_ids.size(0), 768)  # 768  is the embedding dim of our current model

  nb_chunks = input_ids.size(0)
  index = 0
  start_index = 0
  end_index = BATCH_SIZE if nb_chunks > BATCH_SIZE else nb_chunks

  while start_index < end_index:
    batch_obj = {
        "input_ids": input_ids[start_index:end_index],
        "attention_mask": attention_mask[start_index:end_index]
    }

    # Compute token embeddings
    with torch.no_grad():
      model_output = model(**batch_obj)

    # Perform pooling. In this case, mean pooling
    chunks_embeddings = mean_pooling(model_output, batch_obj['attention_mask'])

    result[start_index:end_index] = chunks_embeddings

    index += 1
    start_index = index * BATCH_SIZE
    end_index = (index + 1) * BATCH_SIZE if (index + 1) * BATCH_SIZE < nb_chunks else nb_chunks

  return result


print("Downloading the model")

############## Load model from HuggingFace Hub ##############
tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')
model = AutoModel.from_pretrained('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')

model = model.to(device)

# # Sentences we want sentence embeddings for
chunks = [chunk["text"] for chunk in corpus]

############## Tokenize chunks ##############
print("Started Tokenizing the text!")
encoded_input = utils.load_object(output_tokinized_corpus_pkl_path)
if encoded_input is None:
  encoded_input = tokenizer(chunks, padding=True, truncation=True, return_tensors='pt')
  utils.save_object(encoded_input, output_tokinized_corpus_pkl_path)
print("Tokenized the text!")

encoded_input = encoded_input.to(device)

############## Embeddings ##############
print("Started Embedding !")
chunk_embeddings: torch.Tensor = utils.load_object(output_embeddings_pkl_path)
if chunk_embeddings is None:
  chunk_embeddings = embed(model, encoded_input)
  utils.save_object(chunk_embeddings, output_embeddings_pkl_path)

print("Chunks embedded and saved! With DIM : ", chunk_embeddings.size())

chunk_embeddings = chunk_embeddings.cpu()

############## Faiss Index creation ##############
print("Creating the Index")
if not os.path.exists(index_output_path):
  index = faiss.IndexFlatIP(chunk_embeddings.size(1))   # build the index
  index.add(chunk_embeddings)                        # add vectors to the index
  print(index.ntotal)
  print(f"Writing the index of type 'IndexFlatIP' to disk ({index_output_path})")
  write_index(index, index_output_path)
else:
  index: faiss.IndexFlatIP = read_index(index_output_path)

print("Index Loaded!")

print("Sanity Check Start")
k = 4                          # we want to see 4 nearest neighbors
D, I = index.search(chunk_embeddings[:5], k)

print(I)
print(D)
