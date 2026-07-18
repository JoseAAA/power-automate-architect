# Power Automate Architect — instrucciones del proyecto

Plugin de Claude Code para auditar, mejorar y crear flujos de Power Automate
(cloud flows) siguiendo las mejores prácticas oficiales de Microsoft y de la
comunidad. Local-first: nada de datos del usuario sale a servicios de terceros.

## Principios (no negociables)

1. **Privacidad primero:** el análisis corre local. Las únicas llamadas de red
   permitidas son directas a APIs de Microsoft con el login del propio usuario.
2. **Determinismo barato:** todo análisis pesado va en scripts Python
   (`scripts/`), no en prompts. El asistente ejecuta y explica en lenguaje llano.
3. **Cada regla con fuente:** toda regla del catálogo cita Microsoft Learn o un
   experto reconocido, con URL. Catálogo vivo en `references/buenas-practicas.md`;
   candidatas en `references/reglas-candidatas.md`.
4. **Soluciones antes que hacks:** para escribir flujos, preferir la vía soportada
   (Dataverse Web API, tabla `workflow`); la maker API (`api.flow.microsoft.com`)
   solo para lectura/descubrimiento y flujos legacy — está "unsupported" y debe
   quedar detrás de una capa intercambiable. Ver `references/api-conexion.md`.

## Estructura

- `.claude-plugin/` — solo manifiestos (plugin.json, marketplace.json).
- `skills/<nombre>/SKILL.md` — una skill por modo (auditoría, conectado, …).
- `scripts/` — Python compartido entre skills (referenciar con `${CLAUDE_PLUGIN_ROOT}/scripts/...`).
- `references/` — catálogos y notas compartidas entre skills (ídem con `${CLAUDE_PLUGIN_ROOT}`).
  Recursos usados por UNA sola skill → van dentro de esa skill (`skills/x/references/`).

## Comandos útiles

```bash
# Auditar un flujo exportado (zip, carpeta o definition.json)
python scripts/auditar_flujo.py "<ruta>"
# Exit code: 0 sin hallazgos ALTA, 1 con hallazgos ALTA, 2 error de entrada
```

## Mantenimiento del catálogo de reglas

Mensual (o cuando el usuario vea algo nuevo en el portal): correr
`python scripts/actualizar_catalogo.py` (skill `pa-actualizar`) — exit 1 = hay
cambios en las fuentes; revisar, proponer reglas, y cerrar con
`--marcar-revisado`. Al cambiar una regla: actualizar `buenas-practicas.md` +
`scripts/auditar_flujo.py` + `evals/` y correr `python evals/verificar_auditor.py`.

## Convenciones

- Idioma de cara al usuario: español (código y JSON en inglés cuando lo exija el formato).
- Reglas con código `PA-<ÁREA>-NN` y severidad ALTA/MEDIA/BAJA (pesos 15/7/3).
- Actualizar `CHANGELOG.md` en cada cambio funcional; versionar en `plugin.json` (semver).
