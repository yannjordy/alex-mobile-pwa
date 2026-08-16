#!/usr/bin/env python3
"""Phase 4: Entraînement sur des conversations longues et contextuelles.
Teste la capacité d'Alex à maintenir le contexte sur plusieurs échanges."""
import json
import sys
import time
import urllib.request

API = "http://127.0.0.1:8765/chat/opencode"
SESSION = "training-phase4"
TIMEOUT = 120

# Conversations longues avec contexte à maintenir
LONG_CONVERSATIONS = [
    # Conversation 1: Projet de développement
    [
        ("Je travaille sur un projet Python", 
         "Doit poser des questions sur le projet, montrer de l'intérêt."),
        ("C'est un assistant vocal comme Siri",
         "Doit demander plus de détails, comparer avec des assistants existants."),
        ("Il doit pouvoir contrôler la maison",
         "Doit proposer des idées d'intégration, des protocoles (MQTT, etc.)."),
        ("Comment tu gères la reconnaissance vocale ?",
         "Doit expliquer des options (Whisper, Vosk, etc.) avec des avantages/inconvénients."),
    ],
    
    # Conversation 2: Dépannage technique
    [
        ("Mon PC rame énormément",
         "Doit demander des détails (OS, RAM, processus) avant de proposer des solutions."),
        ("C'est Ubuntu 22.04 avec 8Go de RAM",
         "Doit proposer des commandes spécifiques à Ubuntu pour diagnostiquer."),
        ("J'ai 90% de RAM utilisée",
         "Doit expliquer comment identifier les processus gourmands et proposer des solutions."),
        ("c'est Chrome qui mange toute la RAM",
         "Doit proposer des alternatives ou des astuces pour réduire la consommation."),
    ],
    
    # Conversation 3: Aide à l'apprentissage
    [
        ("Je veux apprendre le machine learning",
         "Doit proposer un parcours d'apprentissage structuré."),
        ("Je connais déjà Python",
         "Doit adapter les ressources en conséquence (pas de débutant Python)."),
        ("Je préfère les vidéos que les livres",
         "Doit recommander des chaînes YouTube, des cours en ligne."),
        ("Tu peux me donner un petit projet pour commencer ?",
         "Doit proposer un projet simple et concret avec des étapes claires."),
    ],
    
    # Conversation 4: Conseil personnalisé
    [
        ("J'ai un entretien d'embauche la semaine prochaine",
         "Doit montrer de l'empathie et proposer des conseils pratiques."),
        ("C'est pour un poste de développeur full-stack",
         "Doit proposer des questions techniques fréquentes et des conseils."),
        ("Je suis un peu stressé",
         "Doit normaliser le stress, proposer des techniques de relaxation."),
        ("Merci pour tes conseils, je me sens mieux",
         "Doit encourager et proposer un suivi si besoin."),
    ],
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

def evaluate_conversation(conversation: list) -> dict:
    """Évalue la qualité d'une conversation longue."""
    scores = []
    
    for i, (user_msg, expected_behavior) in enumerate(conversation):
        response = ask(user_msg)
        
        score = 0
        reasons = []
        
        # Vérifie la longueur (réponse développée)
        if len(response) > 150:
            score += 2
            reasons.append("Réponse développée")
        elif len(response) > 80:
            score += 1
            reasons.append("Réponse acceptable")
        else:
            reasons.append("Réponse trop courte")
        
        # Vérifie la présence de [FORME:xxx]
        if "[FORME:" in response:
            score += 1
            reasons.append("Tag forme présent")
        
        # Vérifie le contexte (référence à la conversation précédente)
        if i > 0:
            prev_user_msg = conversation[i-1][0].lower()
            if any(word in response.lower() for word in prev_user_msg.split()[:3]):
                score += 1
                reasons.append("Contexte maintenu")
        
        # Vérifie la pertinence
        if any(word in response.lower() for word in ["je pense", "je recommande", "voici", "parce que"]):
            score += 1
            reasons.append("Raisonnement présent")
        
        scores.append({"score": min(score, 5), "reasons": reasons, "response": response[:200]})
        
        print(f"  [{i+1}] Q: {user_msg[:50]}...")
        print(f"      Score: {min(score, 5)}/5 — {', '.join(reasons)}")
        print(f"      A: {response[:100]}...")
        time.sleep(0.5)
    
    avg_score = sum(s["score"] for s in scores) / len(scores)
    return {"avg_score": avg_score, "details": scores}

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    total_score = 0
    max_score = len(LONG_CONVERSATIONS) * 5
    errors = 0
    
    for cycle in range(n):
        print(f"\n{'='*60}")
        print(f"CYCLE {cycle+1}/{n} — Phase 4: Conversations longues")
        print(f"{'='*60}")
        
        for conv_idx, conversation in enumerate(LONG_CONVERSATIONS, 1):
            print(f"\n[Conversation {conv_idx}/{len(LONG_CONVERSATIONS)}]")
            try:
                result = evaluate_conversation(conversation)
                total_score += result["avg_score"]
                print(f"  Score moyen conversation: {result['avg_score']:.1f}/5")
            except Exception as e:
                errors += 1
                print(f"  ERREUR: {e}")
        
        # Résumé du cycle
        cycle_score = total_score / ((cycle + 1) * len(LONG_CONVERSATIONS))
        print(f"\n--- Résumé cycle {cycle+1}: {cycle_score:.1f}/5 moyen ---")
    
    # Score final
    final_score = total_score / (n * len(LONG_CONVERSATIONS))
    print(f"\n{'='*60}")
    print(f"RÉSULTAT PHASE 4: {final_score:.1f}/5 ({total_score}/{max_score * n} points)")
    print(f"Erreurs: {errors}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
