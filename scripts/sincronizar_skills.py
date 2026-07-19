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
    # regenerar-sin-fusionar: espeja TODOS los archivos de cada skill (SKILL.md,
    # plantillas, etc.) y borra espejos huerfanos de archivos/skills eliminados
    rel_origen = {p.relative_to(ORIGEN) for p in ORIGEN.rglob("*") if p.is_file()}
    if DESTINO.exists():
        for espejo in sorted(DESTINO.rglob("*")):
            if espejo.is_file() and espejo.relative_to(DESTINO) not in rel_origen:
                desactualizadas.append(f"{espejo.relative_to(DESTINO)} (huerfano)")
                if not solo_chequear:
                    espejo.unlink()
                    try:
                        espejo.parent.rmdir()
                    except OSError:
                        pass
    for rel in sorted(rel_origen):
        origen, destino = ORIGEN / rel, DESTINO / rel
        if origen.suffix == ".md":
            nuevo = contenido_convertido(origen)
        else:
            nuevo = origen.read_text(encoding="utf-8")
        actual = destino.read_text(encoding="utf-8") if destino.exists() else None
        if actual != nuevo:
            desactualizadas.append(str(rel))
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
