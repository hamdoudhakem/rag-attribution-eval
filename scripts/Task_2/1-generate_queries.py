import sys
import os
import torch
import pandas as pd
import numpy as np
from transformers import AutoTokenizer, AutoModelForCausalLM
from huggingface_hub import snapshot_download
from faiss import read_index, IndexFlatIP
import utils


if len(sys.argv) != 6:
  print(
      "Usage : generate_queries.py [input_jsonl_file] [mistral_model_path] [dense_index_embeddings_path] [dense_index_path] [output_jsonl_file]")
  exit(1)

input_path = sys.argv[1]
mistral_model_path = sys.argv[2]
dense_index_embeddings_path = sys.argv[3]
dense_index_path = sys.argv[4]
output_path = sys.argv[5]

device = torch.device("cuda")

# Defining Constants
NB_QUERIES = 200
NB_SINGLE_DOC_QUESTIONS = 5  # 70
NB_2_DOC_QUESTIONS = 50
NB_3_DOC_QUESTIONS = 40
NB_MULTI_DOC_QUESTIONS = NB_3_DOC_QUESTIONS + NB_2_DOC_QUESTIONS
NB_PARTIEL_HALLUCINATION_QUESTIONS = 40

data_text_length_threshold = 120  # We will only take into concederation the chunks that have text with more words than this
model_name = "mistralai/Mistral-7B-Instruct-v0.3"
rng_seed = 2


def load_model():
  snapshot_download(repo_id=model_name, local_dir=mistral_model_path,
                    cache_dir="/projects/iris/hhamdoud/.cache/huggingface",
                    allow_patterns=["params.json", "consolidated.safetensors", "tokenizer.model.v3", "config.json"]
                    )

  # Load the tokenizer
  tokenizer = AutoTokenizer.from_pretrained(mistral_model_path, padding_side="left")

  print("Started Loading from local folder")
  # Load the model with automatic sharding across your 2 GPUs
  model = AutoModelForCausalLM.from_pretrained(
      mistral_model_path,
      device_map="auto",          # This is the magic command that splits the model
      torch_dtype=torch.float16,  # 1080 Ti does not support bfloat16 natively

  )

  return model, tokenizer


def generate_random_integers(rng_seed, generated_size, min_value=0, max_value=1000, endpoint=False):
  """
    rng_seed: the seed to declare the generator, can be int, array, etc.
    min_value, max_value: the range of the values generated
    generated_size: the generated structure size, can be int (so array with length int), tuple (n1, n2, ...), etc.
    endpoint: include the max_value or not

    return: a data structure with size 'generated_size' containing randomly generated integers in [min_value, max_value]
  """
  rng = np.random.default_rng(rng_seed)
  nums = rng.integers(min_value, max_value, size=generated_size, endpoint=endpoint)
  return nums


def main():
  # Prepare Data
  print("Preparing Data ...")
  data = utils.load_jsonl(input_path)
  data = pd.DataFrame(data)

  # Get all the chunks with a length of > data_text_length_threshold words
  data = data.loc[data["text"].map(lambda text: len(text.split()) >= data_text_length_threshold)]
  print(f"Everything Above {data_text_length_threshold} : {data.shape[0]}")

  # Loading Model
  print("Loading Model...")
  model, tokenizer = load_model()
  print("Model loaded successfully!")
  model.eval()

  messages = [
      {"role": "system", "content": "Tu es un expert en données techniques. Ton rôle est de générer des questions strictement basées sur le contexte fourni. Tu ne dois générer QUE les questions, sans aucune phrase d'introduction, de conclusion, ni aucun formatage Markdown superficiel. Répond en français!"},
      {"role": "user", "content": ""},
  ]

  result = []

  current_generated_question_id = 0
  print("\nGenerating Single-document questions")
  # get random values
  indexes = generate_random_integers(
      rng_seed, min_value=0, max_value=data.shape[0], generated_size=NB_SINGLE_DOC_QUESTIONS)
  # for index in indexes:
  #   chunk = data.iloc[index]

  #   messages[1]["content"] = f"""Contexte technique :
  #     ---
  #     {chunk["text"]}
  #     ---

  #     Tâche : Génère exactement DEUX questions distinctes dont les réponses se trouvent explicitement dans le contexte ci-dessus. Les questions doivent être courtes et directes.
  #     Format exigé :
  #     1. [Première question]
  #     2. [Deuxième question]
  #   """

  #   tokenized_input = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt").to(model.device)
  #   generated = model.generate(
  #     tokenized_input,
  #     do_sample=True,
  #     max_new_tokens=150,
  #     temperature=0.3,     # Rend le modèle plus déterministe et factuel
  #     top_p=0.9,           # Évite les mots trop hors-sujet
  #     pad_token_id=tokenizer.eos_token_id # Évite les warnings PyTorch
  #   )
  #   raw_output = tokenizer.batch_decode(generated[:, tokenized_input.shape[1]:], skip_special_tokens=True)
  #   output = raw_output[0].strip()

  #   result.append({
  #       "quest_id": current_generated_question_id,
  #       "question": answer,
  #       "chunks_used_to_generate": [{"chunk_id": index, "chunk_text": chunk["text"]}]  # index
  #   })

  #   current_generated_question_id += 1

  #   if current_generated_question_id % 10 == 0:
  #     utils.writejsonl(output_path, result, "a")
  #     result = []

  # print("\nFinished Generating Single document questions")
  # utils.writejsonl(output_path, result, "a")
  # result = []

  print("\nGenerating 2-3 document questions")
  indexes = generate_random_integers(
      rng_seed + 1, min_value=0, max_value=data.shape[0], generated_size=(NB_MULTI_DOC_QUESTIONS, 3))

  for i, index in enumerate(indexes):
    current_chunks = []
    chunk_ids = index
    if i < NB_2_DOC_QUESTIONS:
      chunk_ids = (index[0], index[1])
      current_chunks = [data.iloc[index[0]], data.iloc[index[1]]]
    else:
      current_chunks = [data.iloc[index[0]], data.iloc[index[1]], data.iloc[index[2]]]

    # Construction dynamique du prompt
    prompt_content = "Contexte technique :\n---\n"

    for x, chunk in enumerate(current_chunks):
      prompt_content += f"Contexte {x+1} : {chunk['text']}\n\n"

    prompt_content += "---\n\n"

    # Les instructions strictes
    prompt_content += """Tâche :
      Les deux contextes ci-dessus parlent potentiellement de sujets ou de lieux différents.
      Génère une seule phrase interrogative qui contient deux questions distinctes reliées par "et", de sorte que la première partie de la question trouve sa réponse explicitement dans le Contexte 1, et la deuxième partie trouve sa réponse explicitement dans le Contexte 2.

      Exemple attendu : "Quelle est la particularité d'exploitation de [Lieu 1] et quel est le contact pour [Lieu 2] ?"
    """

    messages[1]["content"] = prompt_content

    tokenized_input = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, return_tensors="pt").to(model.device)

    generated = model.generate(
        tokenized_input,
        do_sample=True,
        max_new_tokens=150,
        temperature=0.3,     # Rend le modèle plus déterministe et factuel
        top_p=0.9,           # Évite les mots trop hors-sujet
        pad_token_id=tokenizer.eos_token_id  # Évite les warnings PyTorch
    )
    raw_output = tokenizer.batch_decode(generated[:, tokenized_input.shape[1]:], skip_special_tokens=True)
    output = raw_output[0].strip()

    obj = {
        "quest_id": current_generated_question_id,
        "question": output,
        "chunks_used_to_generate": [{"chunk_id": chunk_id, "chunk_text": data.iloc[chunk_id]} for chunk_id in chunk_ids]
    }
    result.append(obj)

    print("output final : ", obj)
    exit(0)

    current_generated_question_id += 1

    if current_generated_question_id % 10 == 0:
      utils.writejsonl(output_path, result, "a")
      result = []

  utils.writejsonl(output_path, result, "a")


if __name__ == "__main__":
  main()
