# Power Automate Architect — guía canónica para agentes

Asistente experto en **Microsoft Power Automate** (cloud flows): audita, lista,
modifica y crea flujos por lenguaje natural con las mejores prácticas oficiales
(Microsoft Learn, Well-Architected, Power CAT). **Local-first:** ningún dato del
usuario pasa por terceros; solo se habla con APIs de Microsoft con el login del
propio usuario. Guía canónica multi-agente; Claude Code la importa desde
`CLAUDE.md`. El detalle operativo vive en las skills (`skills/<modo>/SKILL.md`,
espejo estándar en `.agents/skills/`) — cárgalas al entrar al modo, no antes.

## Ruteo de modos

| El usuario quiere | Skill | Herramienta |
|---|---|---|
| Auditar un flujo exportado (.zip/carpeta/json) | `pa-auditoria` | `python scripts/auditar_flujo.py "<ruta>"` |
| Ver/auditar sus flujos del tenant, corridas | `pa-flujos` | `python scripts/pa_api.py login/flujos/auditar/corridas` |
| Modificar/crear/encender flujos | `pa-conectado` | `python scripts/pa_api.py actualizar/crear/encender/apagar` |
| Novedades de Microsoft / catálogo al día | `pa-actualizar` | `python scripts/actualizar_catalogo.py` |

## Reglas de oro transversales

1. **No preguntes de más:** con el archivo/ID en mano, actúa y entrega solución
   en lenguaje llano (lo técnico después; cada hallazgo con su arreglo).
2. **Escritura = confirmación explícita del usuario en el chat.** Sin `--si` los
   comandos solo simulan (dry-run); muestra la simulación ANTES de pedir el OK.
   La red de seguridad del script (respaldo automático + auditoría previa que
   bloquea hallazgos ALTA) no se rodea; `--forzar` solo a pedido explícito.
3. **Privacidad:** nunca muestres tokens ni caché; el análisis corre local.
4. **Catálogo por consulta puntual:** para explicar una regla, busca su código
   (`PA-XXX-NN`) en `references/buenas-practicas.md` con grep; no cargues el
   archivo completo ni lo vuelques al chat.

## Verificación (tras cualquier cambio al código o docs)

```bash
python evals/verificar_auditor.py && python evals/verificar_conector.py && python evals/verificar_docs.py
```

## Convenciones

Idioma de cara al usuario: español. Reglas `PA-<ÁREA>-NN` (ALTA/MEDIA/BAJA/INFO,
pesos 15/7/3/0). Cambios funcionales → `CHANGELOG.md` + semver en
`.claude-plugin/plugin.json`. Si editas `skills/`, regenera el espejo:
`python scripts/sincronizar_skills.py`.
