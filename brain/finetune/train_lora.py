#!/usr/bin/env python3
"""
Fine-tuning LoRA de SmolLM2-135M sur CPU pour spécialiser Alex.
Utilise transformers + peft + bitsandbytes (quantification 8-bit CPU).
Entraînement : ~30-60 min sur CPU.
"""

import json
import os
import sys
from pathlib import Path

# ─── Configuration ──────────────────────────────────────────────────────────
BASE_MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
OUTPUT_DIR = Path(__file__).parent / "smollm-alex-lora"
DATASET_PATH = Path(__file__).parent / "alex_training_data.jsonl"
MERGE_PATH = Path(__file__).parent / "smollm-alex-merged"
GGUF_PATH = Path(__file__).parent / "smollm-alex.gguf"

os.environ["TOKENIZERS_PARALLELISM"] = "false"


def load_dataset(path):
    data = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    print(f"[train] Dataset chargé : {len(data)} exemples")
    return data


def format_chat(example, tokenizer):
    """Formate les messages au format chat template SmolLM2."""
    messages = example["messages"]
    # Appliquer le chat template du tokenizer
    text = tokenizer.apply_chat_template(messages, tokenize=False)
    return {"text": text}


def train():
    print("[train] ===== Début du fine-tuning LoRA de SmolLM2-135M =====")
    print(f"[train] Modèle de base : {BASE_MODEL}")
    print(f"[train] Dataset : {DATASET_PATH}")

    # ─── Imports ────────────────────────────────────────────────────────
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        TrainingArguments,
        Trainer,
        DataCollatorForSeq2Seq,
    )
    from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
    from datasets import Dataset

    # ─── Tokenizer ──────────────────────────────────────────────────────
    print("[train] Chargement du tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # ─── Modèle ─────────────────────────────────────────────────────────
    print("[train] Chargement du modèle en float32 (CPU)...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype="float32",
        device_map=None,  # CPU
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = False  # Désactive le cache pendant l'entraînement
    print(f"[train] Modèle chargé : {model.num_parameters():,} paramètres")

    # ─── LoRA Config ────────────────────────────────────────────────────
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.1,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    print(f"[train] Paramètres entraînables (LoRA) : {model.num_parameters(only_trainable=True):,}")

    # ─── Dataset ────────────────────────────────────────────────────────
    raw_data = load_dataset(DATASET_PATH)
    dataset = Dataset.from_list(raw_data)
    dataset = dataset.map(lambda x: format_chat(x, tokenizer))
    dataset = dataset.train_test_split(test_size=0.1, seed=42)

    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=512,
            padding="max_length",
        )

    tokenized_train = dataset["train"].map(tokenize_function, batched=True)
    tokenized_eval = dataset["test"].map(tokenize_function, batched=True)

    # ─── Training Arguments ─────────────────────────────────────────────
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        overwrite_output_dir=True,
        num_train_epochs=3,
        per_device_train_batch_size=2,
        per_device_eval_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        warmup_steps=10,
        logging_steps=5,
        eval_steps=20,
        save_steps=50,
        evaluation_strategy="steps",
        save_strategy="steps",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        push_to_hub=False,
        report_to="none",
        dataloader_num_workers=0,
        fp16=False,
        bf16=False,
        optim="adamw_torch",
        max_grad_norm=1.0,
    )

    data_collator = DataCollatorForSeq2Seq(tokenizer, model=model, padding=True)

    # ─── Trainer ────────────────────────────────────────────────────────
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_eval,
        data_collator=data_collator,
        tokenizer=tokenizer,
    )

    # ─── Entraînement ───────────────────────────────────────────────────
    print("[train] Début de l'entraînement (CPU — peut prendre 30-60 min)...")
    trainer.train()

    # ─── Sauvegarde LoRA ────────────────────────────────────────────────
    print(f"[train] Sauvegarde du modèle LoRA dans {OUTPUT_DIR}")
    trainer.save_model()
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print(f"[train] ✅ Fine-tuning LoRA terminé !")

    # ─── Fusion LoRA → Modèle complet ───────────────────────────────────
    print("[train] Fusion des poids LoRA avec le modèle de base...")
    merged_model = model.merge_and_unload()
    print(f"[train] Sauvegarde du modèle fusionné dans {MERGE_PATH}")

    # ─── Conversion en GGUF ─────────────────────────────────────────────
    print("[train] Conversion en GGUF pour Ollama...")
    try:
        from transformers import LlamaTokenizerFast
        # La conversion GGUF nécessite llama.cpp — on va sauvegarder en
        # format safetensors et laisser l'utilisateur convertir
        merged_model.save_pretrained(str(MERGE_PATH))
        tokenizer.save_pretrained(str(MERGE_PATH))
        print(f"[train] ✅ Modèle fusionné sauvegardé dans {MERGE_PATH}")
        print(f"\n[train] Pour convertir en GGUF et utiliser avec Ollama :")
        print(f"  cd {MERGE_PATH.parent}")
        print(f"  pip install gguf")
        print(f"  python -m gguf.convert {MERGE_PATH} --outfile {GGUF_PATH}")
        print(f"  ollama create smollm-alex -f Modelfile")
        print(f"\n[train] Ou utilise directement le dossier safetensors avec 🤗 Transformers.")
    except Exception as e:
        print(f"[train] Avertissement conversion : {e}")
        merged_model.save_pretrained(str(MERGE_PATH))
        tokenizer.save_pretrained(str(MERGE_PATH))

    print(f"\n[train] ===== Entraînement terminé avec succès ! =====")
    return True


if __name__ == "__main__":
    train()
