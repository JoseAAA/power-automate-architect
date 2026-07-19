# Bundle .mcpb (instalador de doble clic para Claude Desktop)

Pasos para generar el `.mcpb` en cada release (requiere Node.js):

```bash
npm i -g @anthropic-ai/mcpb
# copiar el servidor y sus modulos al layout del bundle
mkdir -p mcpb/server
cp scripts/pa_mcp.py scripts/pa_api.py scripts/auditar_flujo.py mcpb/server/
cd mcpb && mcpb pack   # valida manifest.json y produce power-automate-architect.mcpb
```

Publicar el `.mcpb` en el GitHub Release. El usuario final: **doble clic → Aceptar**.

## Avisos conocidos (Windows + Python, investigados 2026-07)

- mcpb con runtime `uv` en Windows tiene bugs abiertos: falso "incompatible with
  your device" si no hay Python del sistema (mcpb #84/#96) y una condición de
  carrera del venv en la primera conexión (claude-code #38266). Mitigación:
  probar el caso "máquina sin Python", documentar la instalación de `uv`
  (una línea) y ofrecer el fallback técnico `uvx pa-architect-mcp` (PyPI).
- El login es por device code: el código viaja como resultado de herramienta
  (el asistente se lo muestra al usuario), nunca por stdout/stderr.
