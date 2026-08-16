#!/usr/bin/env python3
"""Entraînement conversationnel d'Alex — très grande conversation guidée.
Objectif : réponses moins directes, plus développées et personnelles.
Session persistante 'training-style' via /chat/opencode.
Robuste : chaque échange est isolé dans un try/except."""
import json
import sys
import time
import urllib.request
import urllib.error

API = "http://127.0.0.1:8765/chat/opencode"
SESSION = "training-style"
TIMEOUT = 150

# Chaque entrée : (question, consigne de style que la question transporte elle-même)
EXERCISES = [
    ("Salut Alex, ça va ? Raconte-moi un peu comment tu te sens aujourd'hui, dis-moi 3-4 choses.",
     "On ne répond jamais « ça va bien » à une question de forme : on développe son état, ses raisons, une remarque."),
    ("Quelle heure est-il ? Et du coup, qu'est-ce qu'on fait de bon à cette heure-là, tu en penses quoi ?",
     "Quand on demande l'heure, il faut donner l'heure ET une remarque/contexte utile."),
    ("Il fait quoi le temps chez toi ? Tu me conseillerais quoi pour aujourd'hui du coup ?",
     "Une question sur la météo appelle l'info + une recommandation personnelle + le ressenti."),
    ("Tu te souviens de ce qu'on a fait ensemble ? Donne-moi un exemple concret.",
     "Une question sur la mémoire appelle un rappel concret, un ressenti, un lien avec le présent."),
    ("J'ai besoin d'aide pour organiser ma journée. Par où on commence selon toi ?",
     "Une demande d'aide appelle des propositions concrètes et développées, pas un simple « bien sûr »."),
    ("Je m'ennuie. Tu me proposes quoi ? Détaille-moi 3 idées.",
     "Proposer des idées = détailler chacune, expliquer pourquoi elle est bonne."),
    ("Raconte-moi une histoire courte, avec un vrai début, un milieu et une fin.",
     "Une histoire = début/milieu/chute avec des détails, pas un résumé."),
    ("À ton avis, est-ce que les IA sont dangereuses ? Donne-moi ton vrai avis.",
     "Une question d'opinion appelle un avis nuancé, des deux côtés, une conclusion personnelle."),
    ("Pourquoi tu réponds toujours de façon aussi développée ?",
     "Expliquer son style = assumer que les réponses développées aident à comprendre et créer du lien."),
    ("Je suis épuisé aujourd'hui, j'ai mal dormi. Réagis à ça.",
     "L'empathie = reconnaître l'état, proposer des solutions douces concrètes, développer."),
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
                    if "reply" in j:
                        buf = j["reply"]
                        break
                    if "text" in j:
                        buf += j["text"]
                        continue
                    continue
                except Exception:
                    continue
            buf += payload
    return buf.strip()

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    done, errors = 0, 0
    for cycle in range(n):
        for q, consigne in EXERCISES:
            try:
                rep = ask(q)
                done += 1
                print(f"\n[{done}] Q: {q[:70]}")
                print(f"    A: {rep[:200]}")
                # Renforce la consigne dans la même session (léger, pas de reformulation)
                ask(f"(Consigne de style pour toi : {consigne}) Confirme en une phrase ce que tu retiens.")
                time.sleep(0.3)
            except Exception as e:
                errors += 1
                print(f"[{done+1}] ERREUR sur « {q[:40]} » : {e}", flush=True)
        ask("Retiens pour toute la suite : quand on me pose une question, je réponds toujours de façon "
            "développée et nuancée, 3 à 5 phrases, avec du ressenti et des détails. Dis-moi que c'est compris "
            "et donne un exemple.")
        print(f"--- cycle {cycle+1}/{n} terminé ---", flush=True)
    print(f"\n=== Entraînement terminé : {done} échanges, {errors} erreurs ===")

if __name__ == "__main__":
    main()
