"""Moniteur de sécurité 24/7 - Surveillance continue du système."""
import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

SECURITY_DIR = Path.home() / ".alex-security"
ALERTS_FILE = SECURITY_DIR / "alerts.json"
LOG_FILE = SECURITY_DIR / "monitor.log"
CONFIG_FILE = SECURITY_DIR / "config.json"

_last_scan = 0
SCAN_INTERVAL = 300  # 5 minutes
_critical_alerts = []


def _log(msg):
    SECURITY_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")


def _run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except:
        return "", 1


def _check_ports():
    """Détecte les nouveaux ports ouverts."""
    output, _ = _run("ss -tlnp 2>/dev/null")
    ports = set()
    for line in output.splitlines():
        if "LISTEN" in line:
            for part in line.split():
                if ":" in part and part[0].isdigit():
                    try:
                        ports.add(int(part.split(":")[-1]))
                    except:
                        pass
    return ports


def _check_suspicious_processes():
    """Détecte les processus suspects."""
    output, _ = _run("ps aux")
    threats = []
    patterns = ["xmrig", "minerd", "cryptonight", "coinhive", "nc -l", "ncat", "socat",
                "keylog", "spy", "backdoor", "reverse_shell", "/dev/shm/", "/tmp/.hidden"]
    for line in output.splitlines():
        lower = line.lower()
        for p in patterns:
            if p in lower:
                threats.append(line.strip()[:80])
                break
    return threats


def _check_failed_logins():
    """Détecte les tentatives de connexion échouées."""
    output, _ = _run("sudo grep 'Failed password' /var/log/auth.log 2>/dev/null | tail -20")
    failed = []
    for line in output.splitlines():
        if "Failed" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "from" and i + 1 < len(parts):
                    failed.append(parts[i + 1])
    return failed


def _check_intrusion():
    """Détecte les indices d'intrusion."""
    indicators = []

    # Fichiers modifiés récemment dans /etc
    output, _ = _run("find /etc -mmin -5 -type f 2>/dev/null | wc -l")
    if output.isdigit() and int(output) > 3:
        indicators.append(f"{output} fichiers /etc modifiés récemment")

    # Processus cachés
    output, _ = _run("ps aux | grep -E '\\[' | wc -l")
    kernel = int(output) if output.isdigit() else 0
    output2, _ = _run("ps aux | wc -l")
    total = int(output2) if output2.isdigit() else 0
    if total - kernel > 200:
        indicators.append(f"Nombre élevé de processus : {total}")

    # Connexions vers des IP externes
    output, _ = _run("ss -tnp 2>/dev/null | grep ESTAB | grep -v '127.0.0.1' | wc -l")
    external = int(output) if output.isdigit() else 0
    if external > 30:
        indicators.append(f"{external} connexions externes actives")

    return indicators


def _save_alert(alert):
    """Sauvegarde une alerte."""
    SECURITY_DIR.mkdir(parents=True, exist_ok=True)
    alerts = []
    if ALERTS_FILE.exists():
        try:
            alerts = json.loads(ALERTS_FILE.read_text())
        except:
            alerts = []
    alerts.append(alert)
    if len(alerts) > 100:
        alerts = alerts[-100:]
    ALERTS_FILE.write_text(json.dumps(alerts, indent=2))


async def security_check_loop(broadcast_fn=None):
    """Boucle principale de surveillance de sécurité."""
    global _last_scan, _critical_alerts

    _log("🟢 Moniteur de sécurité démarré")

    while True:
        try:
            now = time.time()
            if now - _last_scan < SCAN_INTERVAL:
                await asyncio.sleep(10)
                continue

            _last_scan = now
            _log("🔍 Scan de sécurité en cours...")

            # 1. Vérifier les ports
            current_ports = _check_ports()
            known_ports_file = SECURITY_DIR / "known_ports.json"
            known_ports = set()
            if known_ports_file.exists():
                try:
                    known_ports = set(json.loads(known_ports_file.read_text()))
                except:
                    pass

            new_ports = current_ports - known_ports
            if new_ports:
                msg = f"⚠️ Nouveaux ports détectés : {', '.join(map(str, new_ports))}"
                _log(msg)
                _save_alert({"type": "new_port", "ports": list(new_ports), "time": time.time()})
                if broadcast_fn:
                    await broadcast_fn("security_alert", {"message": msg, "severity": "warning"})

            known_ports_file.write_text(json.dumps(list(current_ports)))

            # 2. Vérifier les processus suspects
            procs = _check_suspicious_processes()
            if procs:
                msg = f"🚨 Processus suspects : {len(procs)} détectés"
                _log(msg)
                _save_alert({"type": "suspicious_process", "count": len(procs), "time": time.time()})
                _critical_alerts.append({"msg": msg, "time": time.time()})
                if broadcast_fn:
                    await broadcast_fn("security_alert", {"message": msg, "severity": "critical"})

            # 3. Vérifier les tentatives de connexion
            failed = _check_failed_logins()
            if len(failed) > 5:
                unique_ips = list(set(failed))
                msg = f"⚠️ {len(failed)} tentatives de connexion échouées depuis {len(unique_ips)} IP"
                _log(msg)
                _save_alert({"type": "failed_logins", "count": len(failed), "ips": unique_ips[:5], "time": time.time()})
                if broadcast_fn:
                    await broadcast_fn("security_alert", {"message": msg, "severity": "warning"})

            # 4. Vérifier les indices d'intrusion
            intrusion = _check_intrusion()
            if intrusion:
                msg = f"🚨 Indices d'intrusion : {'; '.join(intrusion)}"
                _log(msg)
                _save_alert({"type": "intrusion_indicator", "details": intrusion, "time": time.time()})
                _critical_alerts.append({"msg": msg, "time": time.time()})
                if broadcast_fn:
                    await broadcast_fn("security_alert", {"message": msg, "severity": "critical"})

            if not new_ports and not procs and len(failed) <= 5 and not intrusion:
                _log("✅ Scan OK - Aucune menace")

            # Nettoyer les alertes anciennes (> 1h)
            _critical_alerts = [a for a in _critical_alerts if time.time() - a["time"] < 3600]

        except Exception as e:
            _log(f"❌ Erreur scan : {e}")

        await asyncio.sleep(30)


def get_critical_alerts():
    """Retourne les alertes critiques récentes."""
    return [a["msg"] for a in _critical_alerts[-5:]]


def get_security_status():
    """Retourne le statut de sécurité."""
    alerts_file = SECURITY_DIR / "alerts.json"
    alerts = []
    if alerts_file.exists():
        try:
            alerts = json.loads(alerts_file.read_text())
        except:
            pass
    recent = [a for a in alerts if time.time() - a.get("time", 0) < 86400]
    return {
        "total_alerts_24h": len(recent),
        "critical": len([a for a in recent if a.get("type") in ("suspicious_process", "intrusion_indicator")]),
        "warnings": len([a for a in recent if a.get("type") in ("new_port", "failed_logins")]),
    }
