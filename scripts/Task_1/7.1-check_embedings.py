import sys
import os
import utils
import torch
from faiss import read_index

model_out: torch.Tensor = utils.load_object("./data/dense_index/model_output.pkl")

print(model_out.size())

# obj = utils.load_object("./data/dense_index/tokenized_corpus_final_result_00_cleaned_chunked.pkl")

# input_ids: torch.Tensor = obj["input_ids"]
# attention_mask: torch.Tensor = obj["attention_mask"]
# print("obj['input_ids'] : ", input_ids.size())
# print("obj['attention_mask'] : ", attention_mask.size())

# print(input_ids[0:3])

# input_ids[0:3] = torch.zeros(3, input_ids.size(1))

# print(input_ids[0:3])
# print(input_ids)
