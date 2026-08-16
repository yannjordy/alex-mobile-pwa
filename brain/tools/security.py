"""Outil de sécurité système - Protecteur 24/7 pour Alex."""
import os
import subprocess
import time
import hashlib
import json
from pathlib import Path
from . import tool

SECURITY_LOG = Path.home() / ".alex-security" / "security.log"
SECURITY_CONFIG = Path.home() / ".alex-security" / "config.json"
KNOWN_HASHES = Path.home() / ".alex-security" / "known_hashes.json"
THREATS_DB = Path.home() / ".alex-security" / "threats.json"

def _ensure_dirs():
    SECURITY_LOG.parent.mkdir(parents=True, exist_ok=True)

def _log_security(event_type, message, severity="info"):
    _ensure_dirs()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{severity.upper()}] {event_type}: {message}\n"
    with open(SECURITY_LOG, "a") as f:
        f.write(line)

def _load_config():
    _ensure_dirs()
    if SECURITY_CONFIG.exists():
        return json.loads(SECURITY_CONFIG.read_text())
    default = {
        "auto_scan": True,
        "port_monitor": True,
        "firewall_check": True,
        "threat_alerts": True,
        "scan_interval": 3600,
        "monitored_ports": [22, 80, 443, 3306, 5432, 8080, 8443],
        "blocked_ips": [],
        "allowed_ips": ["127.0.0.1", "::1"],
    }
    SECURITY_CONFIG.write_text(json.dumps(default, indent=2))
    return default

def _run_cmd(cmd, timeout=30):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", 1
    except Exception as e:
        return str(e), 1


@tool("scan_systeme",
      "Effectue un scan complet de sécurité du système. Détecte les menaces, vérifie les ports, le firewall et les processus suspects.")
def scan_systeme() -> str:
    """Scan complet de sécurité."""
    _log_security("SCAN", "Scan de sécurité lancé")
    config = _load_config()
    results = []

    # 1. Vérifier les ports ouverts
    output, rc = _run_cmd("ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null")
    open_ports = []
    for line in output.splitlines():
        if "LISTEN" in line:
            parts = line.split()
            for part in parts:
                if ":" in part and part[0].isdigit():
                    try:
                        port = int(part.split(":")[-1])
                        open_ports.append(port)
                    except:
                        pass
    suspicious_ports = [p for p in open_ports if p not in config.get("monitored_ports", []) and p > 1024]
    if suspicious_ports:
        results.append(f"⚠️ Ports suspects ouverts : {', '.join(map(str, suspicious_ports))}")
        _log_security("PORT", f"Ports suspects : {suspicious_ports}", "warning")
    else:
        results.append(f"✅ Ports : {len(open_ports)} ports ouverts (tous normaux)")

    # 2. Vérifier le firewall
    output, rc = _run_cmd("sudo ufw status 2>/dev/null || sudo iptables -L -n 2>/dev/null | head -20")
    if "active" in output.lower() or "Chain" in output:
        results.append("✅ Firewall actif")
    else:
        results.append("⚠️ Firewall potentiellement inactif")
        _log_security("FIREWALL", "Firewall inactif ou non détecté", "warning")

    # 3. Vérifier les processus suspects
    output, rc = _run_cmd("ps aux --sort=-%cpu | head -15")
    suspicious_procs = []
    for line in output.splitlines():
        lower = line.lower()
        if any(s in lower for s in ["nc ", "ncat", "netcat", "socat", "cryptominer", "xmrig", "minerd"]):
            suspicious_procs.append(line.strip()[:80])
    if suspicious_procs:
        results.append(f"🚨 Processus suspects détectés :")
        for p in suspicious_procs[:3]:
            results.append(f"  - {p}")
        _log_security("PROCESS", f"Processus suspects : {len(suspicious_procs)}", "critical")
    else:
        results.append("✅ Aucun processus suspect détecté")

    # 4. Vérifier les connexions entrantes
    output, rc = _run_cmd("ss -tnp 2>/dev/null | grep ESTAB | wc -l")
    established = int(output) if output.isdigit() else 0
    if established > 50:
        results.append(f"⚠️ {established} connexions actives (anormalement élevé)")
        _log_security("CONNECTIONS", f"{established} connexions actives", "warning")
    else:
        results.append(f"✅ {established} connexions actives (normal)")

    # 5. Vérifier les fichiers système modifiés récemment
    output, rc = _run_cmd("find /etc -mmin -60 -type f 2>/dev/null | head -10")
    if output:
        modified = output.splitlines()
        results.append(f"⚠️ {len(modified)} fichiers /etc modifiés récemment")
        _log_security("FILES", f"Fichiers /etc modifiés : {len(modified)}", "warning")
    else:
        results.append("✅ Aucune modification récente dans /etc")

    # 6. Vérifier les updates de sécurité
    output, rc = _run_cmd("apt list --upgradable 2>/dev/null | grep -i security | wc -l")
    security_updates = int(output) if output.isdigit() else 0
    if security_updates > 0:
        results.append(f"⚠️ {security_updates} mises à jour de sécurité disponibles")
        _log_security("UPDATE", f"{security_updates} updates sécurité", "info")
    else:
        results.append("✅ Système à jour")

    # 7. Vérifier l'espace disque
    output, rc = _run_cmd("df -h / | tail -1 | awk '{print $5}'")
    usage = output.replace("%", "")
    if usage.isdigit() and int(usage) > 90:
        results.append(f"⚠️ Disque quasi plein ({usage}%)")
        _log_security("DISK", f"Disque à {usage}%", "warning")
    else:
        results.append(f"✅ Espace disque : {usage}% utilisé")

    # 8. Vérifier les comptes à haut privilège
    output, rc = _run_cmd("grep -E ':0:' /etc/passwd | wc -l")
    root_users = int(output) if output.isdigit() else 0
    if root_users > 1:
        results.append(f"⚠️ {root_users} comptes root détectés")
        _log_security("ACCOUNTS", f"{root_users} comptes root", "warning")
    else:
        results.append("✅ Un seul compte root")

    report = "🔒 RAPPORT DE SÉCURITÉ\n" + "=" * 40 + "\n" + "\n".join(results)
    return report


@tool("surveiller_ports",
      "Surveille les ports ouverts en temps réel et détecte les nouvelles connexions.")
def surveiller_ports() -> str:
    """Surveillance des ports."""
    _log_security("PORT_SCAN", "Scan des ports en cours")
    output, rc = _run_cmd("ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null")
    lines = []
    for line in output.splitlines():
        if "LISTEN" in line:
            lines.append(line.strip()[:100])

    output2, _ = _run_cmd("ss -tnp 2>/dev/null | grep ESTAB | head -20")
    active = []
    for line in output2.splitlines():
        if "ESTAB" in line:
            active.append(line.strip()[:100])

    report = f"🔌 PORTS OUVERTS ({len(lines)}) :\n"
    for l in lines[:15]:
        report += f"  {l}\n"
    report += f"\n📡 CONNEXIONS ACTIVES ({len(active)}) :\n"
    for a in active[:15]:
        report += f"  {a}\n"
    return report


@tool("verifier_firewall",
      "Vérifie l'état du firewall et les règles actives.")
def verifier_firewall() -> str:
    """Vérification firewall."""
    _log_security("FIREWALL", "Vérification firewall")
    output, rc = _run_cmd("sudo ufw status verbose 2>/dev/null")
    if output:
        return f"🛡️ FIREWALL (UFW) :\n{output[:1500]}"

    output, rc = _run_cmd("sudo iptables -L -n --line-numbers 2>/dev/null | head -40")
    if output:
        return f"🛡️ FIREWALL (iptables) :\n{output[:1500]}"

    output, rc = _run_cmd("sudo nft list ruleset 2>/dev/null | head -40")
    if output:
        return f"🛡️ FIREWALL (nftables) :\n{output[:1500]}"

    return "⚠️ Aucun firewall détecté actif"


@tool("scanner_malveillance",
      "Scanne les processus et fichiers suspects (cryptominers, backdoors, rootkits).")
def scanner_malveillance() -> str:
    """Scan anti-malveillance."""
    _log_security("MALWARE_SCAN", "Scan de malveillance")
    threats = []

    # 1. Processus suspects
    output, rc = _run_cmd("ps aux")
    suspicious_patterns = [
        "xmrig", "minerd", "cryptonight", "stratum", "coinhive",
        "nc -l", "ncat", "socat", "reverse", "shell",
        "/tmp/", "/dev/shm/", ".hidden", "backdoor",
        "keylog", "spy", "rat", "trojan"
    ]
    for line in output.splitlines():
        lower = line.lower()
        for pattern in suspicious_patterns:
            if pattern in lower:
                threats.append(f"🚨 Processus suspect : {line.strip()[:80]}")
                _log_security("MALWARE", f"Processus suspect : {pattern}", "critical")
                break

    # 2. Fichiers récemment modifiés dans /tmp
    output, rc = _run_cmd("find /tmp /dev/shm -type f -mmin -30 2>/dev/null | head -10")
    if output:
        for f in output.splitlines():
            threats.append(f"⚠️ Fichier temporaire récent : {f}")

    # 3. Cron jobs suspects
    output, rc = _run_cmd("crontab -l 2>/dev/null; ls /etc/cron.d/ 2>/dev/null")
    if output:
        for line in output.splitlines():
            lower = line.lower()
            if any(s in lower for s in ["curl", "wget", "/tmp/", "python", "nc "]):
                threats.append(f"⚠️ Cron job suspect : {line.strip()[:80]}")

    # 4. Ports en écoute sur 0.0.0.0
    output, rc = _run_cmd("ss -tlnp 2>/dev/null | grep '0.0.0.0:'")
    if output:
        for line in output.splitlines():
            threats.append(f"⚠️ Port exposé publiquement : {line.strip()[:80]}")

    if not threats:
        return "✅ Aucune menace détectée. Système propre."

    report = f"🚨 {len(threats)} MENACE(S) DÉTECTÉE(S) :\n" + "\n".join(threats[:15])
    _log_security("MALWARE", f"{len(threats)} menaces", "critical")
    return report


@tool("verifier_integrite",
      "Vérifie l'intégrité des fichiers système critiques.")
def verifier_integrite() -> str:
    """Vérification intégrité système."""
    _log_security("INTEGRITY", "Vérification intégrité")
    critical_files = [
        "/etc/passwd", "/etc/shadow", "/etc/group",
        "/etc/sudoers", "/etc/ssh/sshd_config",
        "/etc/crontab", "/root/.bashrc"
    ]
    issues = []
    for f in critical_files:
        if os.path.exists(f):
            output, rc = _run_cmd(f"ls -la {f}")
            if output:
                parts = output.split()
                owner = parts[2] if len(parts) > 2 else "?"
                perms = parts[0] if len(parts) > 0 else "?"
                if owner not in ["root", "0"]:
                    issues.append(f"⚠️ {f} possédé par {owner} (devrait être root)")
                if "w" in perms[4:7] and f != "/root/.bashrc":
                    issues.append(f"⚠️ {f} est modifiable par d'autres utilisateurs")

    if not issues:
        return "✅ Intégrité système vérifiée. Aucune anomalie."
    return "⚠️ ANOMALIES D'INTÉGRITÉ :\n" + "\n".join(issues)


@tool("proteger_systeme",
      "Applique les mesures de protection : bloque les IP suspectes, renforce SSH, active le firewall.")
def proteger_systeme(niveau: str = "standard") -> str:
    """Protection proactive du système."""
    _log_security("PROTECT", f"Protection niveau : {niveau}")
    actions = []

    # Activer UFW si pas actif
    output, rc = _run_cmd("sudo ufw status 2>/dev/null")
    if "inactive" in output.lower() or not output:
        _run_cmd("sudo ufw --force enable")
        actions.append("✅ Firewall UFW activé")

    # Règles de base
    _run_cmd("sudo ufw default deny incoming")
    _run_cmd("sudo ufw default allow outgoing")
    _run_cmd("sudo ufw allow 22/tcp")
    _run_cmd("sudo ufw allow 80/tcp")
    _run_cmd("sudo ufw allow 443/tcp")
    actions.append("✅ Règles de base appliquées")

    # Renforcer SSH
    ssh_config = "/etc/ssh/sshd_config"
    if os.path.exists(ssh_config):
        content = Path(ssh_config).read_text()
        changes = []
        if "PermitRootLogin yes" in content:
            content = content.replace("PermitRootLogin yes", "PermitRootLogin no")
            changes.append("Root login désactivé")
        if "PasswordAuthentication yes" in content:
            content = content.replace("PasswordAuthentication yes", "PasswordAuthentication no")
            changes.append("Auth par mot de passe désactivée")
        if changes:
            _run_cmd(f"sudo tee {ssh_config} > /dev/null << 'EOF'\n{content}\nEOF")
            _run_cmd("sudo systemctl restart sshd")
            actions.append(f"✅ SSH renforcé : {', '.join(changes)}")

    # Bloquer les IP avec trop de tentatives
    output, rc = _run_cmd("sudo grep 'Failed password' /var/log/auth.log 2>/dev/null | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -5")
    if output:
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                count = int(parts[0])
                ip = parts[1]
                if count > 10 and ip.count('.') == 3:
                    _run_cmd(f"sudo ufw deny from {ip}")
                    actions.append(f"⚠️ IP bloquée : {ip} ({count} tentatives)")

    return "🛡️ PROTECTION APPLIQUÉE :\n" + "\n".join(actions)


@tool("historique_securite",
      "Affiche l'historique des événements de sécurité.")
def historique_securite(lignes: int = 30) -> str:
    """Historique de sécurité."""
    if not SECURITY_LOG.exists():
        return "📋 Aucun historique de sécurité."
    lines = SECURITY_LOG.read_text().splitlines()
    recent = lines[-lignes:]
    return f"📋 HISTORIQUE SÉCURITÉ (dernières {len(recent)} lignes) :\n" + "\n".join(recent)


@tool("verifier_mises_a_jour",
      "Vérifie les mises à jour de sécurité disponibles.")
def verifier_mises_a_jour() -> str:
    """Vérification updates sécurité."""
    _log_security("UPDATE_CHECK", "Vérification mises à jour")
    output, rc = _run_cmd("apt list --upgradable 2>/dev/null")
    if not output:
        return "✅ Système à jour."

    lines = output.splitlines()
    security = [l for l in lines if "security" in l.lower()]
    total = len(lines) - 1

    report = f"📦 MISES À JOUR DISPONIBLES : {total}\n"
    if security:
        report += f"🔒 Mises à jour SÉCURITÉ : {len(security)}\n"
        for s in security[:5]:
            report += f"  - {s}\n"
        report += "\n⚠️ Recommandation : installer les mises à jour de sécurité en priorité."
    else:
        report += "Aucune mise à jour de sécurité urgente."

    return report
