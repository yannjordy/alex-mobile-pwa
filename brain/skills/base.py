"""Skill system for Alex."""

from typing import Any, Callable

from brain.tools import _build_schema, _tools


class Skill:
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    author: str = ""

    _registered_tools: list[str] = []

    def on_load(self) -> None:
        pass

    def on_unload(self) -> None:
        self.unregister_tools()

    def tool(self, name: str, description: str, dangerous: bool = False) -> Callable:
        def decorator(func: Callable) -> Callable:
            if name in _tools:
                print(f"[skill:{self.name}] ⚠️ Outil « {name} » déjà existant, ignoré")
                return func
            _tools[name] = {
                "func": func,
                "name": name,
                "description": description,
                "parameters": _build_schema(func),
                "dangerous": dangerous,
                "skill": self.name,
            }
            self._registered_tools.append(name)
            return func
        return decorator

    def unregister_tools(self) -> None:
        for name in self._registered_tools:
            _tools.pop(name, None)
        self._registered_tools.clear()
