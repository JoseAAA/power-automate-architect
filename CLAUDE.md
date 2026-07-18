@AGENTS.md

# Notas específicas de Claude Code

- Este repo es además un **plugin de Claude Code** (`.claude-plugin/` + `skills/`).
  Las skills originales usan `${CLAUDE_PLUGIN_ROOT}` en las rutas — eso solo
  funciona aquí; el espejo `.agents/skills/` (rutas relativas al repo) es para
  los demás agentes y se regenera con `python scripts/sincronizar_skills.py`.
- Principio adicional del proyecto: **soluciones antes que hacks** — para
  escribir flujos, preferir Dataverse (tabla `workflow`); la maker API
  (`api.flow.microsoft.com`) es "unsupported" y vive detrás de la capa
  intercambiable de `scripts/pa_api.py`. Ver `references/api-conexion.md`.
