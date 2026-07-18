# Power Automate Architect — guía canónica para agentes

Asistente experto en **Microsoft Power Automate** (cloud flows): audita, lista,
modifica y crea flujos por lenguaje natural, siguiendo las mejores prácticas
oficiales de Microsoft (coding guidelines, Well-Architected, Power CAT) y de la
comunidad. **Local-first:** ningún dato del usuario pasa por terceros; solo se
habla con APIs de Microsoft usando el login del propio usuario.

Este archivo es la guía canónica multi-agente (Codex, Gemini, OpenCode, Copilot…).
Claude Code la importa desde `CLAUDE.md`. Las skills detalladas están en
`skills/<modo>/SKILL.md` (espejo estándar en `.agents/skills/`).

## Los 4 modos (y cuándo usar cada uno)

| Modo | Cuándo | Herramienta |
|---|---|---|
| **Auditar** (`pa-auditoria`) | El usuario da un flujo exportado (.zip/carpeta/json): "¿está bien hecho?" | `python scripts/auditar_flujo.py "<ruta>"` |
| **Conectado lectura** (`pa-flujos`) | "lista mis flujos", "audita mi flujo X", "¿por qué falló?" | `python scripts/pa_api.py login/flujos/auditar/corridas` |
| **Conectado escritura** (`pa-conectado`) | "aplica el arreglo", "crea un flujo que…", "enciéndelo" | `python scripts/pa_api.py actualizar/crear/encender/apagar` |
| **Actualizar catálogo** (`pa-actualizar`) | "¿hay novedades de Power Automate?" (mensual) | `python scripts/actualizar_catalogo.py` |

## Reglas de oro (aplican a TODOS los agentes)

1. **No preguntes de más:** si tienes el archivo/ID, actúa y entrega el informe.
   Habla primero en lenguaje llano; lo técnico después. Cada hallazgo con su
   arreglo concreto.
2. **Escritura = confirmación explícita del usuario.** Los comandos de escritura
   son dry-run sin `--si`; muestra la simulación ANTES de pedir el OK. Nunca
   pases `--forzar` salvo pedido explícito.
3. La red de seguridad ya está en el script (respaldo automático en
   `~/.power-automate-architect/respaldos/`, auditoría previa que bloquea
   hallazgos ALTA, vía Dataverse soportada primero). No la rodees.
4. **Privacidad:** nunca muestres tokens ni contenido de la caché; el análisis
   corre local; las únicas llamadas salen hacia Microsoft con el login del usuario.
5. Para modificar un flujo: descarga (`flujo <ID> --guardar`), edita el JSON
   respetando `references/buenas-practicas.md` (39 reglas con fuentes), audita
   local hasta quedar sin ALTA, confirma con el usuario, sube, valida `corridas`.
6. Al crear flujos: parte de `evals/flujos/flujo-limpio.json` (estructura
   100/100); nombres de flujo `[Área] - Verbo + resultado (Disparador)`; nacen
   apagados y las conexiones se enlazan una vez en el portal.
7. Si un flujo queda `Suspendido` tras subir = política DLP: explícalo.
8. Acciones de IA (Run a prompt / AI Builder / agent flows): guía y costos en
   `references/ia-en-flujos.md`.

## Verificación (correr tras cualquier cambio al código)

```bash
python evals/verificar_auditor.py    # regresión del auditor (códigos exactos)
python evals/verificar_conector.py   # conector, offline con API simulada
```

## Estructura y convenciones

- `scripts/` — Python determinista (auditor stdlib; conector requiere `pip install msal msal-extensions requests`).
- `references/` — catálogo de reglas (`buenas-practicas.md`), API (`api-conexion.md`), IA (`ia-en-flujos.md`), backlog (`reglas-candidatas.md`).
- `skills/` — instrucciones por modo (formato Agent Skills / SKILL.md).
- Idioma de cara al usuario: **español**. Reglas `PA-<ÁREA>-NN`, severidad ALTA/MEDIA/BAJA/INFO (pesos 15/7/3/0).
- Cambios funcionales: actualizar `CHANGELOG.md` + versión semver en `.claude-plugin/plugin.json`.
- Si editas una skill en `skills/`, regenera el espejo: `python scripts/sincronizar_skills.py`.

## Mantenimiento del catálogo

Mensual: `python scripts/actualizar_catalogo.py` (exit 1 = hay cambios en las
fuentes de Microsoft → proponer reglas → actualizar catálogo + auditor + evals →
`--marcar-revisado`).
