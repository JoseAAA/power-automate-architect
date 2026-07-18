#!/usr/bin/env python3
"""
sincronizar_skills.py - Espeja skills/ hacia .agents/skills/ (estándar Agent Skills).

Codex, Gemini CLI y OpenCode descubren skills en .agents/skills/. Este script
copia cada skills/<n>/SKILL.md alli, reemplazando la variable de Claude
${CLAUDE_PLUGIN_ROOT}/ por rutas relativas a la raiz del repo (los demas agentes
corren con cwd en el repo). Correr cada vez que cambie una skill.

  python scripts/sincronizar_skills.py          # sincroniza
  python scripts/sincronizar_skills.py --check  # exit 1 si el espejo esta desactualizado
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "skills"
DESTINO = RAIZ / ".agents" / "skills"


def contenido_convertido(ruta_skill):
    texto = ruta_skill.read_text(encoding="utf-8")
    return texto.replace("${CLAUDE_PLUGIN_ROOT}/", "").replace("${CLAUDE_PLUGIN_ROOT}", ".")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    solo_chequear = "--check" in sys.argv
    desactualizadas = []
    for skill_md in sorted(ORIGEN.glob("*/SKILL.md")):
        nombre = skill_md.parent.name
        destino = DESTINO / nombre / "SKILL.md"
        nuevo = contenido_convertido(skill_md)
        actual = destino.read_text(encoding="utf-8") if destino.exists() else None
        if actual != nuevo:
            desactualizadas.append(nombre)
            if not solo_chequear:
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(nuevo, encoding="utf-8")
    if solo_chequear:
        if desactualizadas:
            print("Espejo .agents/skills desactualizado: " + ", ".join(desactualizadas))
            print("Corre: python scripts/sincronizar_skills.py")
            return 1
        print("Espejo .agents/skills al dia.")
        return 0
    print(f"Sincronizadas: {', '.join(desactualizadas) if desactualizadas else '(sin cambios)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
