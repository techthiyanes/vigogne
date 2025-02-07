#! /usr/bin/env python
# coding=utf-8

import logging
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import bitsandbytes as bnb
import datasets
import numpy as np
import torch
import transformers
from datasets import DatasetDict, load_dataset
from peft import LoraConfig, TaskType, get_peft_model, get_peft_model_state_dict, prepare_model_for_int8_training
from transformers import AutoModelForCausalLM, AutoTokenizer, HfArgumentParser, LlamaTokenizer, Trainer, TrainingArguments

from utils import print_trainable_parameters

logger = logging.getLogger(__name__)

IGNORE_INDEX = -100
DEFAULT_PAD_TOKEN = "[PAD]"
DEFAULT_EOS_TOKEN = "</s>"
DEFAULT_BOS_TOKEN = "</s>"
DEFAULT_UNK_TOKEN = "</s>"

# Original English prompt
# PROMPT_DICT = {
#     "prompt_input": (
#         "Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.\n\n"
#         "### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n### Response:\n"
#     ),
#     "prompt_no_input": (
#         "Below is an instruction that describes a task. Write a response that appropriately completes the request.\n\n"
#         "### Instruction:\n{instruction}\n\n### Response:\n"
#     ),
# }
# French prompt translated by chatgpt
PROMPT_DICT = {
    "prompt_input": (
        "Ci-dessous se trouve une instruction qui décrit une tâche, associée à une entrée qui fournit un contexte supplémentaire. Écrivez une réponse qui complète correctement la demande.\n\n"
        "### Instruction:\n{instruction}\n\n### Entrée:\n{input}\n\n### Réponse:\n"
    ),
    "prompt_no_input": (
        "Ci-dessous se trouve une instruction qui décrit une tâche. Écrivez une réponse qui complète correctement la demande.\n\n"
        "### Instruction:\n{instruction}\n\n### Réponse:\n"
    ),
}


def generate_prompt(example):
    return (
        PROMPT_DICT["prompt_input"].format_map(example)
        if example["input"]
        else PROMPT_DICT["prompt_no_input"].format_map(example)
    )


@dataclass
class ModelArguments:
    # Base model parameters
    model_name_or_path: Optional[str] = field(default=None)
    # LoRA parameters
    lora_r: int = field(default=8, metadata={"help": "Lora rank."})
    lora_alpha: int = field(default=16, metadata={"help": "Lora alpha."})
    lora_dropout: float = field(default=0.05, metadata={"help": "Lora dropout."})
    target_modules: List[str] = field(
        default_factory=lambda: ["q_proj", "v_proj"], metadata={"help": "Names of the modules to apply Lora to."}
    )


@dataclass
class DataArguments:
    train_file: Optional[str] = field(default=None, metadata={"help": "Path to the training file."})
    eval_file: Optional[str] = field(default=None, metadata={"help": "Path to the evaluation file."})
    model_max_length: Optional[int] = field(
        default=None, metadata={"help": "Maximum sequence length. Sequences will be right padded (and possibly truncated)."}
    )
    model_max_length_percentile: Optional[int] = field(
        default=95, metadata={"help": "Percentile of the example length. Used to determin `model_max_length`."}
    )
    preprocessing_num_workers: Optional[int] = field(
        default=None, metadata={"help": "The number of processes to use for the preprocessing."}
    )


@dataclass
class VigogneTrainingArguments(TrainingArguments):
    optim: str = field(default="adamw_torch", metadata={"help": "Optimizer to use."})
    fp16: bool = field(
        default=True, metadata={"help": "Whether to use fp16 16-bit (mixed) precision training instead of 32-bit training."}
    )


# Modified from: https://github.com/bofenghuang/stanford_alpaca/blob/eb5b171d9b103a12a8e14e0edca9cbc45fe1d512/train.py#L166-L182
# Almost same to transformers.DataCollatorForSeq2Seq
@dataclass
class DataCollatorForSupervisedDataset(object):
    """Collate examples for supervised fine-tuning."""

    tokenizer: transformers.PreTrainedTokenizer
    pad_to_multiple_of: Optional[int] = None

    def __call__(self, instances: Sequence[Dict]) -> Dict[str, torch.Tensor]:
        # dtype = torch.long
        # input_ids, labels = tuple([torch.LongTensor(instance[key]) for instance in instances] for key in ("input_ids", "labels"))
        input_ids, labels = tuple([instance[key] for instance in instances] for key in ("input_ids", "labels"))

        if self.pad_to_multiple_of is not None:
            max_length_index, max_length = max(enumerate([len(input_ids_) for input_ids_ in input_ids]), key=lambda x: x[1])
            # n_padding = ((max_length // self.pad_to_multiple_of) + 1) * self.pad_to_multiple_of - max_length
            n_padding = math.ceil(max_length / self.pad_to_multiple_of) * self.pad_to_multiple_of - max_length
            # Pad the longest example to pad_to_multiple_of * N
            input_ids[max_length_index].extend([self.tokenizer.pad_token_id] * n_padding)
            labels[max_length_index].extend([IGNORE_INDEX] * n_padding)

        input_ids = [torch.LongTensor(input_ids_) for input_ids_ in input_ids]
        labels = [torch.LongTensor(labels_) for labels_ in labels]

        input_ids = torch.nn.utils.rnn.pad_sequence(input_ids, batch_first=True, padding_value=self.tokenizer.pad_token_id)
        labels = torch.nn.utils.rnn.pad_sequence(labels, batch_first=True, padding_value=IGNORE_INDEX)

        return dict(
            input_ids=input_ids,
            labels=labels,
            attention_mask=input_ids.ne(self.tokenizer.pad_token_id),
        )


# Copied from https://github.com/bofenghuang/stanford_alpaca/blob/eb5b171d9b103a12a8e14e0edca9cbc45fe1d512/train.py#L75-L95
def smart_tokenizer_and_embedding_resize(
    special_tokens_dict: Dict,
    tokenizer: transformers.PreTrainedTokenizer,
    model: transformers.PreTrainedModel,
):
    """Resize tokenizer and embedding.
    Note: This is the unoptimized version that may make your embedding size not be divisible by 64.
    """
    num_new_tokens = tokenizer.add_special_tokens(special_tokens_dict)
    model.resize_token_embeddings(len(tokenizer))

    if num_new_tokens > 0:
        input_embeddings = model.get_input_embeddings().weight.data
        output_embeddings = model.get_output_embeddings().weight.data

        input_embeddings_avg = input_embeddings[:-num_new_tokens].mean(dim=0, keepdim=True)
        output_embeddings_avg = output_embeddings[:-num_new_tokens].mean(dim=0, keepdim=True)

        input_embeddings[-num_new_tokens:] = input_embeddings_avg
        output_embeddings[-num_new_tokens:] = output_embeddings_avg


def train():
    # HF parser
    parser = HfArgumentParser((ModelArguments, DataArguments, VigogneTrainingArguments))
    model_args, data_args, training_args = parser.parse_args_into_dataclasses()

    # Setup logging
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if training_args.should_log:
        # The default of training_args.log_level is passive, so we set log level at info here to have that default.
        transformers.utils.logging.set_verbosity_info()

    log_level = training_args.get_process_log_level()
    logger.setLevel(log_level)
    datasets.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.enable_default_handler()
    transformers.utils.logging.enable_explicit_format()

    # Log on each process the small summary:
    logger.warning(
        f"Process rank: {training_args.local_rank}, device: {training_args.device}, n_gpu: {training_args.n_gpu}"
        + f"distributed training: {bool(training_args.local_rank != -1)}, 16-bits training: {training_args.fp16}"
    )
    # Set the verbosity to info of the Transformers logger (on main process only):
    logger.info(f"Model parameters {model_args}")
    logger.info(f"Training/evaluation parameters {training_args}")

    # todo: better handle
    device_map = "auto"
    world_size = int(os.environ.get("WORLD_SIZE", 1))
    ddp = world_size != 1
    if ddp:
        device_map = {"": int(os.environ.get("LOCAL_RANK") or 0)}

    # Load model and tokenizer
    model = AutoModelForCausalLM.from_pretrained(
        model_args.model_name_or_path,
        load_in_8bit=True,
        device_map=device_map,
    )

    # todo: better handle
    tokenizer_class = LlamaTokenizer if "llama" in model_args.model_name_or_path else AutoTokenizer
    tokenizer = tokenizer_class.from_pretrained(
        model_args.model_name_or_path,
        padding_side="right",
        use_fast=False,
    )

    if tokenizer.pad_token is None:
        # llama has no pad token
        smart_tokenizer_and_embedding_resize(
            special_tokens_dict=dict(pad_token=DEFAULT_PAD_TOKEN),
            tokenizer=tokenizer,
            model=model,
        )
    if "llama" in model_args.model_name_or_path:
        tokenizer.add_special_tokens(
            {
                "eos_token": DEFAULT_EOS_TOKEN,
                "bos_token": DEFAULT_BOS_TOKEN,
                "unk_token": DEFAULT_UNK_TOKEN,
            }
        )

    # Freeze the model parameters
    # Cast the small parameters (e.g. layernorm) to fp32 for stability
    model = prepare_model_for_int8_training(model)

    lora_config = LoraConfig(
        r=model_args.lora_r,
        lora_alpha=model_args.lora_alpha,
        target_modules=model_args.target_modules,
        lora_dropout=model_args.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    print_trainable_parameters(model)

    # Load data
    raw_datasets = DatasetDict()
    if data_args.train_file is not None:
        ext = data_args.train_file.rsplit(".", 1)[-1]
        raw_datasets["train"] = load_dataset(ext, data_files=data_args.train_file)["train"]
    else:
        raise ValueError("You have not specified any train file")
    if data_args.eval_file is not None:
        ext = data_args.eval_file.rsplit(".", 1)[-1]
        raw_datasets["eval"] = load_dataset(ext, data_files=data_args.eval_file)["train"]
    # logger.info(raw_datasets)

    # Determine model_max_length for truncation
    model_max_length = data_args.model_max_length

    def get_example_length(example):
        user_prompt = generate_prompt(example)
        example["example_length"] = len(tokenizer(user_prompt + example["output"] + tokenizer.eos_token)["input_ids"])
        return example

    if model_max_length is None:
        with training_args.main_process_first(desc="dataset map tokenization"):
            train_example_lengths = raw_datasets["train"].map(
                get_example_length,
                num_proc=data_args.preprocessing_num_workers,
                remove_columns=next(iter(raw_datasets.values())).column_names,
                desc="get example lengths",
            )["example_length"]
        # Take percentile of max length
        model_max_length = math.ceil(np.percentile(train_example_lengths, data_args.model_max_length_percentile))
        logger.info(
            f"`model_max_length` has been set to the {data_args.model_max_length_percentile}th percentile of training example lengths: {model_max_length}"
        )

    # Tokenize data
    def preprocess_function(example):
        # Format prompt
        user_prompt = generate_prompt(example)

        # Get prompt length for masking
        len_user_prompt_tokens = len(tokenizer(user_prompt, truncation=True, max_length=model_max_length)["input_ids"])

        # Tokenize
        # todo: need eos?
        input_ids = tokenizer(
            user_prompt + example["output"] + tokenizer.eos_token, truncation=True, max_length=model_max_length
        )["input_ids"]
        # Mask prompt
        labels = [IGNORE_INDEX] * len_user_prompt_tokens + input_ids[len_user_prompt_tokens:]

        # Tokenize
        # input_ids = tokenizer(user_prompt + example["output"] + tokenizer.eos_token, truncation=True, return_tensors="pt")["input_ids"][0]
        # labels = input_ids.clone()
        # Mask prompt
        # labels[:len_user_prompt_tokens] = IGNORE_INDEX

        return {"input_ids": input_ids, "labels": labels}

    with training_args.main_process_first(desc="dataset map tokenization"):
        preprocessed_dataset = raw_datasets.map(
            preprocess_function,
            num_proc=data_args.preprocessing_num_workers,
            remove_columns=next(iter(raw_datasets.values())).column_names,
            desc="preprocess data set",
        )

    # Init trainer
    trainer = Trainer(
        model=model,
        train_dataset=preprocessed_dataset["train"],
        eval_dataset=preprocessed_dataset["eval"] if data_args.eval_file is not None else None,
        args=training_args,
        data_collator=DataCollatorForSupervisedDataset(
            tokenizer=tokenizer, pad_to_multiple_of=8 if training_args.fp16 else None
        ),
    )

    # Silence the warnings. Please re-enable for inference!
    model.config.use_cache = False

    old_state_dict = model.state_dict
    model.state_dict = (lambda self, *_, **__: get_peft_model_state_dict(self, old_state_dict())).__get__(model, type(model))

    if torch.__version__ >= "2" and sys.platform != "win32":
        model = torch.compile(model)

    trainer.train()

    model.save_pretrained(training_args.output_dir)


if __name__ == "__main__":
    train()
