"""Phase 9 : Entraînement Alex sur la sécurité système et la protection."""
import json
import os

TRAINING_DATA_PATH = os.path.join(os.path.dirname(__file__), "finetune", "alex_training_data.jsonl")


def load_examples():
    examples = []
    if os.path.exists(TRAINING_DATA_PATH):
        with open(TRAINING_DATA_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        examples.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return examples


def save_examples(examples):
    os.makedirs(os.path.dirname(TRAINING_DATA_PATH), exist_ok=True)
    with open(TRAINING_DATA_PATH, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")


def make_example(user_msg, assistant_msg, tool_calls, tools_used, context):
    messages = [{"role": "user", "content": user_msg}]
    tc = []
    for name, args in tool_calls:
        tc.append({"type": "function", "function": {"name": name, "arguments": args}})
    assistant_entry = {"role": "assistant", "content": assistant_msg}
    if tc:
        assistant_entry["tool_calls"] = tc
    messages.append(assistant_entry)
    return {"messages": messages, "tools_used": tools_used, "context": context}


SECURITY_SCAN_EXAMPLES = [
    make_example(
        "Fais un scan de sécurité complet",
        "Je lance un scan complet de sécurité du système.",
        [("scan_systeme", {})],
        ["scan_systeme"],
        "Scan sécurité complet"
    ),

    make_example(
        "Y a-t-il des menaces sur ma machine ?",
        "Je vérifie les menaces potentielles.",
        [("scanner_malveillance", {})],
        ["scanner_malveillance"],
        "Détection menaces"
    ),

    make_example(
        "Vérifie l'intégrité de mes fichiers système",
        "Je vérifie l'intégrité des fichiers critiques.",
        [("verifier_integrite", {})],
        ["verifier_integrite"],
        "Intégrité fichiers"
    ),

    make_example(
        "Protège ton système contre les intrusions",
        "Je vais appliquer les mesures de protection.",
        [("proteger_systeme", {"niveau": "standard"})],
        ["proteger_systeme"],
        "Protection proactive"
    ),
]

PORT_MONITORING_EXAMPLES = [
    make_example(
        "Quels ports sont ouverts sur ma machine ?",
        "Voici les ports actuellement ouverts.",
        [("surveiller_ports", {})],
        ["surveiller_ports"],
        "Surveillance ports"
    ),

    make_example(
        "Y a-t-il des connexions suspectes ?",
        "Je vérifie les connexions actives.",
        [("surveiller_ports", {})],
        ["surveiller_ports"],
        "Connexions suspectes"
    ),

    make_example(
        "Bloque les IP qui tentent de pirater mon SSH",
        "Je vais bloquer les IP avec trop de tentatives.",
        [("proteger_systeme", {"niveau": "ssh"})],
        ["proteger_systeme"],
        "Blocage IP SSH"
    ),
]

FIREWALL_EXAMPLES = [
    make_example(
        "Mon firewall est-il actif ?",
        "Je vérifie l'état du firewall.",
        [("verifier_firewall", {})],
        ["verifier_firewall"],
        "Vérification firewall"
    ),

    make_example(
        "Configure le firewall pour n'ouvrir que le strict nécessaire",
        "Je vais configurer le firewall avec les règles minimales.",
        [("proteger_systeme", {"niveau": "strict"})],
        ["proteger_systeme"],
        "Configuration firewall stricte"
    ),
]

UPDATE_EXAMPLES = [
    make_example(
        "Y a-t-il des mises à jour de sécurité ?",
        "Je vérifie les mises à jour de sécurité disponibles.",
        [("verifier_mises_a_jour", {})],
        ["verifier_mises_a_jour"],
        "Mises à jour sécurité"
    ),

    make_example(
        "Installe les mises à jour de sécurité critiques",
        "Je vais installer les mises à jour de sécurité.",
        [("executer_commande", {"commande": "sudo apt update && sudo apt upgrade -y"})],
        ["executer_commande"],
        "Installation updates sécurité"
    ),
]

HISTORY_EXAMPLES = [
    make_example(
        "Montre-moi l'historique de sécurité",
        "Voici l'historique des événements de sécurité.",
        [("historique_securite", {"lignes": 20})],
        ["historique_securite"],
        "Historique sécurité"
    ),

    make_example(
        "Y a-t-il eu des alertes récemment ?",
        "Je vérifie les alertes de sécurité récentes.",
        [("historique_securite", {"lignes": 10})],
        ["historique_securite"],
        "Alertes récentes"
    ),
]

ANTIVIRUS_EXAMPLES = [
    make_example(
        "Scanne les processus pour détecter les cryptominers",
        "Je lance un scan ciblé sur les cryptominers.",
        [("scanner_malveillance", {})],
        ["scanner_malveillance"],
        "Scan cryptominers"
    ),

    make_example(
        "Y a-t-il des backdoors sur ma machine ?",
        "Je recherche les backdoors et connexions suspectes.",
        [("scanner_malveillance", {})],
        ["scanner_malveillance"],
        "Scan backdoors"
    ),

    make_example(
        "Nettoie les fichiers temporaires suspects",
        "Je vais nettoyer les fichiers temporaires potentiellement dangereux.",
        [("executer_commande", {"commande": "sudo rm -rf /tmp/.hidden* /tmp/*.sh /dev/shm/* 2>/dev/null; echo 'Nettoyage terminé'"})],
        ["executer_commande"],
        "Nettoyage fichiers suspects"
    ),
]


def train():
    print("Phase 9 : Entrainement Securite Systeme")
    print("=" * 60)

    existing = load_examples()
    print(f"Exemples existants : {len(existing)}")

    new_examples = (
        SECURITY_SCAN_EXAMPLES + PORT_MONITORING_EXAMPLES +
        FIREWALL_EXAMPLES + UPDATE_EXAMPLES + HISTORY_EXAMPLES +
        ANTIVIRUS_EXAMPLES
    )
    existing.extend(new_examples)
    save_examples(existing)

    print(f"Nouveaux exemples : {len(new_examples)}")
    print(f"Total : {len(existing)}")
    print(f"\nDetail :")
    print(f"  - Scan securite : {len(SECURITY_SCAN_EXAMPLES)} exemples")
    print(f"    - Scan complet, menaces, integrite, protection")
    print(f"  - Surveillance ports : {len(PORT_MONITORING_EXAMPLES)} exemples")
    print(f"    - Ports ouverts, connexions suspectes, blocage IP")
    print(f"  - Firewall : {len(FIREWALL_EXAMPLES)} exemples")
    print(f"    - Etat firewall, configuration stricte")
    print(f"  - Mises a jour : {len(UPDATE_EXAMPLES)} exemples")
    print(f"    - Verification, installation updates securite")
    print(f"  - Historique : {len(HISTORY_EXAMPLES)} exemples")
    print(f"    - Historique evenements, alertes recentes")
    print(f"  - Antivirus : {len(ANTIVIRUS_EXAMPLES)} exemples")
    print(f"    - Cryptominers, backdoors, nettoyage")
    print("\nAlex peut maintenant :")
    print("  - Scanner le systeme en continu (24/7)")
    print("  - Detecter les menaces et processus suspects")
    print("  - Surveiller les ports et connexions")
    print("  - Verifier et renforcer le firewall")
    print("  - Bloquer les IP malveillantes")
    print("  - Verifier l'integrite des fichiers systeme")
    print("  - Installer les mises a jour de securite")
    print("  - Tenir un historique de securite")
    print("\nTermine !")


if __name__ == "__main__":
    train()
