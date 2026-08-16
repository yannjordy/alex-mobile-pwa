# Pipeline de fine-tuning LoRA pour smollm-alex

## Quand ta connexion sera rapide

```bash
# 1. Installer les dépendances
cd ~/Documents/alex-assistant
brain/.venv/bin/pip install transformers datasets peft accelerate sentencepiece

# 2. Générer le dataset (déjà fait)
brain/.venv/bin/python brain/finetune/create_dataset.py

# 3. Lancer l'entraînement LoRA (30-60 min sur CPU)
brain/.venv/bin/python brain/finetune/train_lora.py

# 4. Convertir en GGUF pour Ollama
brain/.venv/bin/pip install gguf
python -m gguf.convert brain/finetune/smollm-alex-merged \
  --outfile brain/finetune/smollm-alex.gguf

# 5. Créer le modèle Ollama
cd brain/finetune
ollama create smollm-alex -f Modelfile.smollm-alex

# 6. Utiliser le nouveau modèle
export ALEX_LOCAL_MODEL="smollm-alex"
# ou modifier main.py -> MODEL = "smollm-alex"
```

## Ce que fait le fine-tuning

Le dataset contient :
- **28 exemples d'utilisation d'outils** (WiFi, BLE, MCP, fichiers, code)
- **Conversations naturelles** avec le style Alex
- **Instructions d'auto-programmation** (lecture/écriture de code)
- **Mode non-censuré** avec réponses complètes
- **Patterns d'interaction** (PROPOSAL, STATE, SHAPE)
