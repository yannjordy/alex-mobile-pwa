"""Skill: contrôle d'appareils (volume, verrouillage, extinction, etc.)."""

from __future__ import annotations

import shutil
import subprocess

from brain.skills.base import Skill

skill: Skill | None = None
"""Instance exportée pour le SkillManager."""


class DeviceControlSkill(Skill):
    name = "device_control"
    description = "Contrôle des appareils : volume, luminosité, verrouillage, extinction, applications"
    version = "1.0.0"
    author = "Alex"

    def on_load(self) -> None:
        self._register_tools()

    def _register_tools(self) -> None:
        @self.tool("volume", "Monte ou baisse le volume. action: up/down/mute")
        def volume(action: str = "up") -> str:
            p = {"up": "+10%", "down": "-10%", "mute": "toggle"}
            if action == "mute":
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=False)
                return "Son activé/coupé."
            v = p.get(action, "+10%")
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", v], check=False)
            return f"Volume {action}."

        @self.tool("verrouiller_ecran", "Verrouille l'écran. Pas de paramètre.")
        def verrouiller_ecran() -> str:
            subprocess.run(["loginctl", "lock-session"], check=False)
            return "Écran verrouillé."

        @self.tool("eteindre", "Éteint l'ordinateur. Nécessite confirmation.", dangerous=True)
        def eteindre() -> str:
            subprocess.run(["systemctl", "poweroff"], check=False)
            return "Extinction en cours."

        @self.tool("redemarrer", "Redémarre l'ordinateur. Nécessite confirmation.", dangerous=True)
        def redemarrer() -> str:
            subprocess.run(["systemctl", "reboot"], check=False)
            return "Redémarrage en cours."

        @self.tool("ouvrir_application", "Ouvre une application par son nom. nom: nom de l'app")
        def ouvrir_application(nom: str = "") -> str:
            if not nom:
                return "Usage : ouvrir_application nom='firefox'"
            slug = nom.strip().lower().replace(" ", "-")
            binary = shutil.which(slug) or shutil.which(nom.strip().lower())
            if binary:
                subprocess.Popen([binary])
                return f"J'ouvre {nom.strip()}."
            try:
                subprocess.Popen(["gtk-launch", slug])
                return f"J'ouvre {nom.strip()}."
            except FileNotFoundError:
                pass
            return f"Je ne trouve pas comment ouvrir « {nom.strip()} »."


skill = DeviceControlSkill()
