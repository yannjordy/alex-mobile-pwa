"""Skill discovery and lifecycle management."""

from __future__ import annotations

import importlib
import os
import pkgutil
import sys
from typing import Optional

from brain.skills.base import Skill


class SkillManager:
    def __init__(self) -> None:
        self.skills: dict[str, Skill] = {}

    def discover(self, *paths: str) -> list[str]:
        found: list[str] = []
        for path in paths:
            if not os.path.isdir(path):
                continue
            parent = os.path.dirname(path)
            if parent not in sys.path:
                sys.path.insert(0, parent)
            for mod_info in pkgutil.iter_modules([path]):
                if mod_info.name in ("base", "manager", "__init__"):
                    continue
                found.append(mod_info.name)
        return found

    def load(self, name: str, paths: Optional[list[str]] = None) -> bool:
        if name in self.skills:
            return True
        module = None
        # Always try the package-qualified name first (absolute imports)
        try:
            module = importlib.import_module(f"brain.skills.{name}")
        except ImportError:
            pass
        if module is None and paths:
            for p in paths:
                if p not in sys.path:
                    sys.path.insert(0, p)
                try:
                    module = importlib.import_module(name)
                    break
                except ImportError:
                    module = None
                    continue
        else:
            try:
                module = importlib.import_module(f"brain.skills.{name}")
            except ImportError:
                try:
                    module = importlib.import_module(name)
                except ImportError:
                    return False
        if module is None:
            return False

        skill_inst = getattr(module, "skill", None)
        if skill_inst is None:
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Skill) and attr is not Skill:
                    skill_inst = attr()
                    break
        if skill_inst is None:
            return False

        if hasattr(module, "register_tools"):
            module.register_tools(skill_inst.tool)

        skill_inst.on_load()
        self.skills[name] = skill_inst
        return True

    def unload(self, name: str) -> bool:
        skill = self.skills.pop(name, None)
        if skill is None:
            return False
        skill.on_unload()
        return True

    def reload(self, name: str, paths: Optional[list[str]] = None) -> bool:
        self.unload(name)
        if name in sys.modules:
            del sys.modules[name]
        return self.load(name, paths)

    def list_skills(self) -> list[dict]:
        return [
            {
                "name": s.name or n,
                "description": s.description,
                "version": s.version,
                "author": s.author,
                "tools": list(s._registered_tools),
            }
            for n, s in self.skills.items()
        ]


skill_manager = SkillManager()
