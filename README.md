<p align="center" width="100%">
<img src="./assets/vigogne_logo.png" alt="Vigogne" style="width: 40%; min-width: 300px; display: block; margin: auto;">
</p>

# Vigogne 🦙: French Instruction-following Models

[![Code License](https://img.shields.io/badge/Code%20License-Apache_2.0-green.svg)](https://github.com/bofenghuang/vigogne/blob/main/LICENSE)
[![Data License](https://img.shields.io/badge/Data%20License-CC%20By%20NC%204.0-red.svg)](https://github.com/bofenghuang/vigogne/blob/main/DATA_LICENSE)

*The vigogne (French name for vicuña) is a South American camelid native to the Andes Mountains. It is closely related to the llama, alpaca, and guanaco.*

This repository contains code for reproducing the [Stanford Alpaca](https://github.com/tatsu-lab/stanford_alpaca) in French 🇫🇷 using [low-rank adaptation (LoRA)](https://arxiv.org/abs/2106.09685) provided by 🤗 Hugging Face's [PEFT](https://github.com/huggingface/peft) library. In addition to the LoRA technique, we also use [LLM.int8()](https://arxiv.org/abs/2208.07339) provided by [bitsandbytes](https://github.com/TimDettmers/bitsandbytes) to quantize pretrained language models (PLMs) to int8. Combining these two techniques allows us to fine-tune PLMs on a single consumer GPU such as RTX 4090.

This project is based on [LLaMA](https://github.com/facebookresearch/llama), [Stanford Alpaca](https://github.com/tatsu-lab/stanford_alpaca), [**Alpaca-Lora**](https://github.com/tloen/alpaca-lora), [Cabrita](https://github.com/22-hours/cabrita) and [Hugging Face](https://huggingface.co/docs/transformers/main_classes/trainer). In addition, we adapted the [training script](https://github.com/bofenghuang/vigogne/blob/main/finetune.py) to fine-tune on more models such as [BLOOM](https://huggingface.co/bigscience/bloom-7b1) and [mT5](https://huggingface.co/google/mt5-xxl). We also share the [translated dataset](https://github.com/bofenghuang/vigogne/blob/main/data/vigogne_data_cleaned.json) and the trained [vigogne-lora-7b](https://huggingface.co/bofenghuang/vigogne-lora-7b) and [vigogne-lora-bloom-7b1](https://huggingface.co/bofenghuang/vigogne-lora-bloom-7b1) weights.

**Usage and License Notices**: Same as [Stanford Alpaca](https://github.com/tatsu-lab/stanford_alpaca), Vigogne is intended and licensed for research use only. The dataset is CC BY NC 4.0 (allowing only non-commercial use) and models trained using the dataset should not be used outside of research purposes.

💡 *The screencast below shows the current 🦙 Vigogne-LoRA-7B model running on Apple M1 Pro using 4GB of weights (no sped up).*

![](./assets/screencast.gif)

## Table of Contents

- [Setup](#setup)
- [Play with 🦙 Vigogne models](#play-with--vigogne-models)
- [Try it out on your own PC](#try-it-out-on-your-own-pc)
- [Data](#data)
- [Training](#training)
- [Example outputs](#example-outputs)
- [Bias, Risks, and Limitations](#bias-risks-and-limitations)
- [Next steps](#next-steps)

## Setup

Install dependencies

```bash
pip install -r requirements.txt
```

## Play with 🦙 Vigogne models

**User Notice**: Facebook has not made the official LLaMA model weights open source, although various third-party download links are available online, such as `decapoda-research/llama-7b-hf` in the HuggingFace model library. It should be noted that the use of these links may not comply with Facebook's policies. Due to the reasons mentioned above, the project cannot release the complete weights of fine-tuned models. However, only the LoRA weights can be provided, which can be considered as a "patch" for the original LLaMA model.

The fine-tuned instruction-following vigogne models are available on 🤗 Hugging Face:

- Fine-tuned LLaMA-7B model: [bofenghuang/vigogne-lora-7b](https://huggingface.co/bofenghuang/vigogne-lora-7b)
- Fine-tuned LLaMA-13B model: [bofenghuang/vigogne-lora-13b](https://huggingface.co/bofenghuang/vigogne-lora-13b)
- Fine-tuned LLaMA-30B model: [bofenghuang/vigogne-lora-30b](https://huggingface.co/bofenghuang/vigogne-lora-30b)
- Fine-tuned BLOOM-7B1 model: [bofenghuang/vigogne-lora-bloom-7b1](https://huggingface.co/bofenghuang/vigogne-lora-bloom-7b1)
- Fine-tuned OPT-6.7B model: [bofenghuang/vigogne-lora-opt-6.7b](https://huggingface.co/bofenghuang/vigogne-lora-opt-6.7b)

You can infer these models by using the following Google Colab Notebook.

<a href="https://colab.research.google.com/github/bofenghuang/vigogne/blob/main/infer.ipynb" target="_blank"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

You can also run a Gradio demo using the following command:

```bash
./demo.py \
    --base_model_name_or_path <name/or/path/to/hf/llama/7b/model> \
    --lora_model_name_or_path bofenghuang/vigogne-lora-7b
```

## Try it out on your own PC

The Vigogne models can now be easily deployed on PCs, thanks to the excellent tools created by the community. The following steps provide detailed instructions on how to combine Vigogne-LoRA weights with the original LLaMA model, quantize the resulting model to 4-bit, and finally deploy it on your own PC using [llama.cpp](https://github.com/ggerganov/llama.cpp).

**Note: the models will be quantized into 4-bit, so the performance might be worse than the non-quantized version. The responses are random due to the generation hyperparameters.**

Please ensure that the following requirements are met prior to running:

- As the models are currently fully loaded into memory, you will need adequate disk space to save them and sufficient RAM to load them. You will need at least 13GB of RAM to quantize the 7B model. For more information, refer to this [link](https://github.com/ggerganov/llama.cpp#memorydisk-requirements).
- It's best to use Python 3.9 or Python 3.10, as sentencepiece has not yet published a wheel for Python 3.11.

### 1. Clone and build llama.cpp repo

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make
```

### 2. Combine Vigogne-LoRA weights with the corresponding original LLaMA model

```bash
# combine
python ../scripts/export_state_dict_checkpoint.py \
    --base_model_name_or_path <name/or/path/to/hf/llama/7b/model> \
    --lora_model_name_or_path "bofenghuang/vigogne-lora-7b" \
    --output_dir ./models/7B

# download the tokenizer.model file
wget -P ./models https://huggingface.co/bofenghuang/vigogne-lora-7b/resolve/main/tokenizer.model

# check the files
tree models
# models
# ├── 7B
# │   ├── consolidated.00.pth
# │   └── params.json
# └── tokenizer.model
```

### 3. Quantize the combined model

```bash
# convert the 7B model to ggml FP16 format
python convert-pth-to-ggml.py ./models/7B/ 1

# further quantize the model to 4-bit
python quantize.py 7B
```

### 4. Run the inference

```bash
# ./main -h for more information
./main -m ./models/7B/ggml-model-q4_0.bin --color -ins -c 2048 --temp 0.1 -n 256
```

## Data

We translated the original [alpaca_data.json](https://github.com/tatsu-lab/stanford_alpaca/blob/main/alpaca_data.json) to French using `gpt-3.5-turbo` by the chat completion API.

You can also translate it to other languages using the [translation script](https://github.com/bofenghuang/vigogne/blob/main/scripts/translate_data.py). Don't forget to modify your [translation prompt](https://github.com/bofenghuang/vigogne/blob/e6ae25fc0569ca85c25529a6d06122b35426aa2d/scripts/translate_data.py#L47-L57).

The translation may have compromised the accuracy of certain tasks, such as generating rhyming words or correcting grammar (discussed [here](https://github.com/tloen/alpaca-lora/pull/127)). We warmly welcome PRs to help clean up this dataset!

The following command shows how to estimate the price for translating the full dataset.

```bash
./scripts/translate_data.py estimate_price \
    --input_json_file data/alpaca_data_cleaned.json \
    --ratio_output_input 1.0 \
    --model gpt-3.5-turbo-0301 \
    --price_per_thousand_tokens 0.002
```

You can translate the dataset using the following command.

```bash
# Specify your OpenAI API key
export OPENAI_API_KEY=xx

./scripts/translate_data.py process_data \
    --input_json_file data/alpaca_data_cleaned.json \
    --output_json_file data/vigogne_data_cleaned.json \
    --model gpt-3.5-turbo \
    --max_parallel_requests 32
```

## Training

### Fine-tuning LLaMA-7B model

The following command shows how to fine-tune LLaMA-7B model using a single GPU.

```bash
python finetune.py \
    --model_name_or_path <name/or/path/to/hf/llama/7b/model> \
    --train_file "data/vigogne_data_cleaned.json" \
    --output_dir "outputs/llama-7b-ft-vigogne-lora" \
    --run_name "llama-7b-ft-vigogne-lora" \
    --overwrite_output_dir \
    --model_max_length_percentile 95 \
    --preprocessing_num_workers 4 \
    --dataloader_num_workers 1 \
    --lora_r 8 \
    --lora_alpha 16 \
    --lora_dropout 0.05 \
    --target_modules "q_proj" "v_proj" \
    --per_device_train_batch_size 16 \
    --per_device_eval_batch_size 8 \
    --gradient_accumulation_steps 8 \
    --num_train_epochs 3 \
    --learning_rate 3e-4 \
    --warmup_steps 100 \
    --logging_steps 25 \
    --save_strategy "steps" \
    --save_steps 200 \
    --save_total_limit 3 \
    --report_to "tensorboard" "wandb"
```

### Fine-tuning LLaMA-30B model

The following command shows how to fine-tune LLaMA-30B model using multi GPUs.

```bash
WORLD_SIZE=2 torchrun --nproc_per_node=2 --master_port=29001 finetune.py \
    --model_name_or_path <name/or/path/to/hf/llama/30b/model> \
    --train_file "data/vigogne_data_cleaned.json" \
    --output_dir "outputs/llama-30b-ft-vigogne-lora" \
    --run_name "llama-30b-ft-vigogne-lora" \
    --overwrite_output_dir \
    --model_max_length_percentile 95 \
    --preprocessing_num_workers 4 \
    --dataloader_num_workers 1 \
    --lora_r 8 \
    --lora_alpha 16 \
    --lora_dropout 0.05 \
    --target_modules "q_proj" "v_proj" \
    --per_device_train_batch_size 4 \
    --per_device_eval_batch_size 2 \
    --gradient_accumulation_steps 16 \
    --num_train_epochs 3 \
    --learning_rate 3e-4 \
    --warmup_steps 100 \
    --logging_steps 25 \
    --save_strategy "steps" \
    --save_steps 200 \
    --save_total_limit 3 \
    --report_to "tensorboard" "wandb"
```

### Fine-tuning BLOOM-7B1 model

The following command shows how to fine-tune [bigscience/bloom-7b1](https://huggingface.co/bigscience/bloom-7b1) model using a single GPU.

```bash
python finetune.py \
    --model_name_or_path "bigscience/bloom-7b1" \
    --train_file "data/vigogne_data_cleaned.json" \
    --output_dir "outputs/bloom-7b1-ft-vigogne" \
    --run_name "bloom-7b1-ft-vigogne" \
    --overwrite_output_dir \
    --model_max_length_percentile 95 \
    --preprocessing_num_workers 4 \
    --dataloader_num_workers 1 \
    --lora_r 16 \
    --lora_alpha 32 \
    --lora_dropout 0.05 \
    --target_modules "query_key_value" \
    --per_device_train_batch_size 16 \
    --per_device_eval_batch_size 8 \
    --gradient_accumulation_steps 8 \
    --num_train_epochs 3 \
    --learning_rate 3e-4 \
    --warmup_steps 100 \
    --logging_steps 25 \
    --save_strategy "steps" \
    --save_steps 200 \
    --save_total_limit 3 \
    --report_to "tensorboard" "wandb"
```

### Fine-tuning OPT-6.7B model

The following command shows how to fine-tune [facebook/opt-6.7b](https://huggingface.co/facebook/opt-6.7b) model using a single GPU.

```bash
python finetune.py \
    --model_name_or_path "facebook/opt-6.7b" \
    --train_file "data/vigogne_data_cleaned.json" \
    --output_dir "outputs/opt-6b7-ft-vigogne" \
    --run_name "opt-6b7-ft-vigogne" \
    --overwrite_output_dir \
    --model_max_length_percentile 95 \
    --preprocessing_num_workers 4 \
    --dataloader_num_workers 1 \
    --lora_r 16 \
    --lora_alpha 32 \
    --lora_dropout 0.05 \
    --target_modules "q_proj" "v_proj" \
    --per_device_train_batch_size 16 \
    --per_device_eval_batch_size 8 \
    --gradient_accumulation_steps 8 \
    --num_train_epochs 3 \
    --learning_rate 3e-4 \
    --warmup_steps 100 \
    --logging_steps 25 \
    --save_strategy "steps" \
    --save_steps 200 \
    --save_total_limit 3 \
    --report_to "tensorboard" "wandb"
```

## Example outputs

Répondez à la question suivante : Les pratiques artistiques transforment-elles le monde ?

- **Vigogne-LoRA-7B**: Les pratiques d'art peuvent transformer le monde en créant des œuvres qui évoquent des sentiments, des idées et des émotions. Elles peuvent également être utilisées pour créer des Œuvres d'Art Vivant qui sont des œuvre vivantes qui peuvent être utilisés pour créé des expériences et des conversations. Les praticiens d'arts peuvent également utiliser leurs pratiques pour créerer des œufs d'âme, des êtres vivants créés à partir de matériaux naturels, qui peuvent avoir un impact sur la façon dont les gens pensent et ressentent le monde.

<details><summary>Other models</summary>

- **Alpaca-LoRA**: Yes, artistic practices can transform the world. Art can be used to express ideas, explore new perspectives, and create dialogue. Art can also be used to inspire and motivate people to take action, and to create positive change in their communities.

- **text-davinci-003**: Oui, les pratiques artistiques peuvent transformer le monde. Les artistes peuvent utiliser leur art pour exprimer leurs opinions et leurs idées, et ces idées peuvent avoir un impact sur la société et le monde. Les artistes peuvent également utiliser leur art pour sensibiliser le public à des sujets importants et pour encourager le changement. Les pratiques artistiques peuvent donc être un puissant outil pour transformer le monde.

</details>

---

Expliquez la différence entre DoS et phishing en français.

- **Vigogne-LoRA-7B**: Le DoS (Denial of Service) est une attaque informatique qui consiste à bloquer ou à interrompre l'accès à un service ou à un système informatique. Le phishing est une technique de fraude qui consisterait à obtenir des informations sensibles d'un utilisateur en lui demandant de fournir des renseignements, tels que des mots de passe ou des numéros de carte de crédit.

<details><summary>Other models</summary>

- **Alpaca-LoRA**: In French, the difference between a DDoS attack and phishing is that a DDoS attack is an attempt to overwhelm a system with a large amount of traffic, while phishing is an attempt to steal personal information by posing as a trusted source.

- **text-davinci-003**:

DoS (Denial of Service) est une attaque qui vise à rendre indisponible des services web ou réseau en saturant un serveur ou un réseau avec des requêtes. Elle peut aussi être utilisée pour perturber un réseau en envoyant des paquets mal formés ou en le surchargant.

Phishing est une forme d'escroquerie en ligne visant à voler des informations personnelles telles que des mots de passe et des numéros de carte de crédit en incitant les victimes à fournir leurs informations sur des faux sites Web ou des emails frauduleux.

</details>

---

Résumez le texte suivant en une seule phrase.

La science des données est l'étude des données afin d'en extraire des informations significatives pour les entreprises. Il s'agit d'une approche pluridisciplinaire qui combine des principes et des pratiques issus des domaines des mathématiques, des statistiques, de l'intelligence artificielle et du génie informatique, en vue d'analyser de grands volumes de données. Cette analyse aide les scientifiques des données à poser des questions et à y répondre, comme Que s'est-il passé, Pourquoi cela s'est-il passé, Que va-t-il se passer et Que peut-on faire avec des résultats.

- **Vigogne-LoRA-7B**: Le scientifique des données utilise des données pour analyser et extraire de l’information pour aider les entrepreneurs à posent des questions, répondre à des questions existantes et prendre des décisions.

<details><summary>Other models</summary>

- **Alpaca-LoRA**: La science des données est l'étude des données afin d'en extraire des informations significatives pour les entreprises.

- **text-davinci-003**: La science des données combine des principes et des pratiques issus des domaines des mathématiques, des statistiques, de l'intelligence artificielle et du génie informatique pour analyser de grands volumes de données afin d'en extraire des informations significatives pour les entreprises.

</details>

---

Écrivez une fonction qui prend une liste de chaînes de caractères et renvoie une liste sans doublons.

- **Vigogne-LoRA-7B**:

```python
def remove_duplicates(lst):
    result = []
    for item in lst:
        if item not in result:
            result.append(item)
    return result
```

<details><summary>Other models</summary>

- **Alpaca-LoRA**:

```python
def remove_duplicates(list):
    seen = set()
    return [x for x in list if x not in seen]
```

- **text-davinci-003**:

```python
def remove_duplicates(liste):
  new_list = []
  for item in liste:
    if item not in new_list:
      new_list.append(item)
  return new_list

liste = ["a", "b", "c", "a", "d", "e", "f", "c"]
print(remove_duplicates(liste)) # ['a', 'b', 'c', 'd', 'e', 'f']
```

</details>

## Bias, Risks, and Limitations

Vigogne is still under development, and there are many limitations that have to be addressed. Please note that it is possible that the model generates harmful or biased content, incorrect information or generally unhelpful answers.

## Next steps

- Collect more and cleaner French instruction-following data
