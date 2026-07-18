---
name: pa-actualizar
description: >
  Mantiene el catálogo de mejores prácticas SIEMPRE al día con las fuentes
  oficiales. USAR cuando el usuario pregunta "¿hay novedades de Power Automate?",
  "actualiza el catálogo/las reglas", "¿salió algo nuevo de Microsoft?", "¿el
  catálogo está al día?", o al detectar en el diseñador funciones que el catálogo
  no contempla (ej. nuevas acciones de IA). También como rutina mensual.
---

# Actualizador del catálogo — novedades de las fuentes oficiales

Objetivo: que las 34+ reglas y las recomendaciones del plugin nunca se queden
atrás de Microsoft. El trabajo pesado lo hace un script determinista; el
asistente solo interpreta los cambios y propone reglas.

## Procedimiento

1. **Detectar cambios** (1 llamada HTTP pública por fuente, sin credenciales):
   ```bash
   python "scripts/actualizar_catalogo.py"
   ```
   - exit 0 → "Catálogo al día" → informar y terminar.
   - exit 1 → hay commits/páginas nuevas: sigue al paso 2.
   - Primera corrida: crea línea base en `references/estado-fuentes.json`.

2. **Interpretar.** Por cada fuente con cambios, abre los commits (el script da
   el link) o la página de Microsoft Learn afectada (WebFetch) y clasifica:
   - *Página nueva* → casi seguro amerita regla(s) candidata(s).
   - *Cambio de contenido* → ¿cambia alguna regla existente (severidad, arreglo,
     URL)? ¿aparece una práctica nueva verificable en el definition.json?
   - *Cosmético* (typos, imágenes, metadata) → ignorar.

3. **Proponer en simple.** Presentar al usuario: qué cambió, qué reglas nuevas o
   ajustes convienen, y el esfuerzo. NO tocar el catálogo sin su OK.

4. **Aplicar (tras el OK).** Actualizar `references/buenas-practicas.md` +
   `scripts/auditar_flujo.py` + flujos de `evals/flujos/` si hay reglas nuevas,
   correr `python evals/verificar_auditor.py` (debe dar TODO OK), actualizar
   `CHANGELOG.md` y la versión en `plugin.json`.

5. **Cerrar el ciclo:**
   ```bash
   python "scripts/actualizar_catalogo.py" --marcar-revisado
   ```

## Fuentes vigiladas (definidas en el script)
- `MicrosoftDocs/power-automate-docs` → coding-guidelines (26+ páginas) y limits-and-config
- `MicrosoftDocs/power-platform` → Well-Architected y ALM
- `microsoft/Power-CAT-Tools` → CODE_REVIEW.md (los patrones oficiales de revisión)

Complementos semestrales (no automatizados): release planner de Power Automate
(olas de abril/octubre) https://learn.microsoft.com/power-platform/release-plan/
y el blog https://www.microsoft.com/en-us/power-platform/blog/power-automate/.

## Notas
- Cadencia sugerida: **mensual** (o cuando el usuario vea algo nuevo en el portal).
- El script solo lee metadatos públicos de GitHub; no envía nada del usuario.
- Si GitHub limita las llamadas anónimas (60/hora), reintentar más tarde.
