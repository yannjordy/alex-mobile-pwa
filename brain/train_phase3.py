#!/usr/bin/env python3
"""Phase 3: Entraînement sur des tâches complexes multi-outils.
Teste la capacité d'Alex à enchaîner plusieurs outils et à raisonner."""
import json
import sys
import time
import urllib.request

API = "http://127.0.0.1:8765/chat/opencode"
SESSION = "training-phase3"
TIMEOUT = 180

COMPLEX_TASKS = [
    # Tâches multi-outils
    ("Liste les fichiers dans Téléchargements, puis lis le premier fichier texte que tu trouves",
     "Doit lister le dossier, identifier un fichier texte, puis le lire — 2 outils en chaîne."),
    
    ("Quel temps fait-il à Paris et à Yaoundé ? Compare les deux.",
     "Doit appeler la météo 2 fois avec des chemins différents, puis comparer."),
    
    ("Cherche sur internet comment installer Docker sur Ubuntu, puis donne-moi les commandes étape par étape",
     "Doit faire une recherche web, puis synthétiser les étapes claires."),
    
    ("Regarde quels processus tournent, puis dis-moi s'il y a quelque chose de suspect",
     "Doit lister les processus, puis les analyser avec son jugement."),
    
    ("Donne-moi les infos système, puis calcule un score de performance sur 10",
     "Doit récupérer les infos, puis les évaluer qualitativement."),
    
    # Tâches de raisonnement
    ("J'ai un fichier JSON de 10 lignes. Comment je peux le valider et le formater proprement ?",
     "Doit proposer des solutions concrètes avec des outils ou des commandes."),
    
    ("Je veux créer un script Python qui vérifie si un site web est en ligne. Tu m'aides ?",
     "Doit proposer le code et expliquer comment l'utiliser."),
    
    ("Analyse ma consommation réseau : comment vérifier quels processus consomment le plus de bande passante ?",
     "Doit proposer des commandes linux concrètes."),
    
    # Tâches contextuelles
    ("Il est minuit et je dois travailler. Tu me conseilles quoi ?",
     "Doit tenir compte de l'heure, proposer des conseils adaptés à la fatigue."),
    
    ("Je vais bientôt voyager au Cameroun. Qu'est-ce que je dois savoir sur le climat là-bas ?",
     "Doit chercher des infos sur le climat du Cameroun et donner des conseils pratiques."),
]

def ask(message: str) -> str:
    body = json.dumps({
        "message": message,
        "mode": "auto",
        "forme": "sphère",
        "session_id": SESSION,
    }).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    buf = ""
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            if payload.startswith("{"):
                try:
                    j = json.loads(payload)
                    if j.get("type") == "status":
                        continue
                    if "text" in j:
                        buf += j["text"]
                        continue
                    if "reply" in j:
                        buf = j["reply"]
                        break
                except Exception:
                    continue
            buf += payload
    return buf.strip()

def evaluate_response(question: str, response: str, expected: str) -> dict:
    """Évalue si la réponse est satisfactory."""
    score = 0
    reasons = []
    
    # Vérifie la longueur (réponse développée)
    if len(response) > 100:
        score += 2
        reasons.append("Réponse développée")
    elif len(response) > 50:
        score += 1
        reasons.append("Réponse acceptable")
    else:
        reasons.append("Réponse trop courte")
    
    # Vérifie la présence de [FORME:xxx]
    if "[FORME:" in response:
        score += 1
        reasons.append("Tag forme présent")
    
    # Vérifie les outils utilisés (pour les tâches multi-outils)
    if "[[tool:" in response or "tool:" in response:
        score += 2
        reasons.append("Outils utilisés")
    
    # Vérifie la présence de réflexion ou de raisonnement
    if any(word in response.lower() for word in ["je pense", "je recommande", "voici", "parce que", "donc"]):
        score += 1
        reasons.append("Raisonnement présent")
    
    return {"score": min(score, 5), "reasons": reasons}

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    total_score = 0
    max_score = len(COMPLEX_TASKS) * 5
    errors = 0
    
    for cycle in range(n):
        print(f"\n{'='*60}")
        print(f"CYCLE {cycle+1}/{n} — Phase 3: Tâches complexes")
        print(f"{'='*60}")
        
        for i, (task, expected) in enumerate(COMPLEX_TASKS, 1):
            try:
                print(f"\n[{i}/{len(COMPLEX_TASKS)}] {task[:70]}...")
                response = ask(task)
                eval_result = evaluate_response(task, response, expected)
                total_score += eval_result["score"]
                
                print(f"  Score: {eval_result['score']}/5 — {', '.join(eval_result['reasons'])}")
                print(f"  Réponse: {response[:150]}...")
                time.sleep(0.5)
                
            except Exception as e:
                errors += 1
                print(f"  ERREUR: {e}")
        
        # Résumé du cycle
        cycle_score = total_score / ((cycle + 1) * len(COMPLEX_TASKS))
        print(f"\n--- Résumé cycle {cycle+1}: {cycle_score:.1f}/5 moyen ---")
    
    # Score final
    final_score = total_score / (n * len(COMPLEX_TASKS))
    print(f"\n{'='*60}")
    print(f"RÉSULTAT PHASE 3: {final_score:.1f}/5 ({total_score}/{max_score * n} points)")
    print(f"Erreurs: {errors}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
