#!/usr/bin/env python3
"""Phase 5: Entraînement sur les scénarios d'automatisation.
Teste la capacité d'Alex à programmer des tâches et des rappels intelligents."""
import json
import sys
import time
import urllib.request

API = "http://127.0.0.1:8765/chat/opencode"
SESSION = "training-phase5"
TIMEOUT = 120

# Scénarios d'automatisation
AUTOMATION_SCENARIOS = [
    # Changement de fond d'écran
    ("Change mon fond d'écran dans 5 minutes",
     "Doit programmer une tâche de type wallpaper avec le bon délai."),
    
    ("Programme un changement de fond d'écran pour 20h",
     "Doit programmer une tâche pour l'heure spécifiée."),
    
    # Activation Bluetooth
    ("Active le bluetooth dans 10 minutes",
     "Doit programmer une tâche de type bluetooth avec action 'on'."),
    
    ("Désactive le bluetooth à 22h",
     "Doit programmer une tâche de type bluetooth avec action 'off'."),
    
    # Lancement d'application
    ("Lance Discord dans 5 minutes",
     "Doit programmer une tâche de type app avec le nom 'discord'."),
    
    ("Ouvre Firefox à 19h",
     "Doit programmer une tâche de type app avec le nom 'firefox'."),
    
    # Volume
    ("Mets le volume à 50% dans 15 minutes",
     "Doit programmer une tâche de type volume avec le bon niveau."),
    
    ("Baisse le volume à 30% à 22h",
     "Doit programmer une tâche de type volume avec le bon niveau."),
    
    # Rappels intelligents
    ("Rappelle moi dans 30 minutes de sortir la poubelle",
     "Doit créer un rappel intelligent avec le bon délai."),
    
    ("Rappelle moi à 18h de appeler maman",
     "Doit créer un rappel intelligent pour l'heure spécifiée."),
    
    # Tâches multiples
    ("À 20h, active le bluetooth et lance Discord",
     "Doit programmer deux tâches séparées pour la même heure."),
    
    # Gestion des tâches
    ("Liste mes tâches programmées",
     "Doit lister les tâches existantes."),
    
    ("Supprime la tâche de fond d'écran",
     "Doit supprimer la tâche spécifiée."),
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

def evaluate_automation(question: str, response: str, expected: str) -> dict:
    """Évalue si la réponse est satisfactory pour une automatisation."""
    score = 0
    reasons = []
    
    # Vérifie la présence de [FORME:xxx]
    if "[FORME:" in response:
        score += 1
        reasons.append("Tag forme présent")
    
    # Vérifie la confirmation de programmation
    if any(word in response.lower() for word in ["programmée", "programmé", "planifiée", "planifié", "rappel programmé"]):
        score += 2
        reasons.append("Confirmation de programmation")
    
    # Vérifie la présence d'une heure ou d'un délai
    if any(word in response for word in ["à ", "dans ", "pour "]):
        score += 1
        reasons.append("Heure ou délai mentionné")
    
    # Vérifie la longueur (réponse développée)
    if len(response) > 100:
        score += 1
        reasons.append("Réponse développée")
    
    return {"score": min(score, 5), "reasons": reasons}

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    total_score = 0
    max_score = len(AUTOMATION_SCENARIOS) * 5
    errors = 0
    
    for cycle in range(n):
        print(f"\n{'='*60}")
        print(f"CYCLE {cycle+1}/{n} — Phase 5: Automatisations")
        print(f"{'='*60}")
        
        for i, (scenario, expected) in enumerate(AUTOMATION_SCENARIOS, 1):
            try:
                print(f"\n[{i}/{len(AUTOMATION_SCENARIOS)}] {scenario[:70]}...")
                response = ask(scenario)
                eval_result = evaluate_automation(scenario, response, expected)
                total_score += eval_result["score"]
                
                print(f"  Score: {eval_result['score']}/5 — {', '.join(eval_result['reasons'])}")
                print(f"  Réponse: {response[:150]}...")
                time.sleep(0.5)
                
            except Exception as e:
                errors += 1
                print(f"  ERREUR: {e}")
        
        # Résumé du cycle
        cycle_score = total_score / ((cycle + 1) * len(AUTOMATION_SCENARIOS))
        print(f"\n--- Résumé cycle {cycle+1}: {cycle_score:.1f}/5 moyen ---")
    
    # Score final
    final_score = total_score / (n * len(AUTOMATION_SCENARIOS))
    print(f"\n{'='*60}")
    print(f"RÉSULTAT PHASE 5: {final_score:.1f}/5 ({total_score}/{max_score * n} points)")
    print(f"Erreurs: {errors}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
