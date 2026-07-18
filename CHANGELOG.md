# Changelog

## [0.5.0] — 2026-07-18

### Agregado — Fase 3: escritura por lenguaje natural + portabilidad multi-agente
- **Escritura en `scripts/pa_api.py`**: `actualizar` (reemplaza la definición),
  `crear` (nace apagado), `encender`/`apagar`. Vía soportada (Dataverse, tabla
  `workflow`: PATCH `clientdata` con `If-Match`, POST con `category 5`) y
  fallback maker API para flujos legacy. Triple red de seguridad: respaldo
  automático en `~/.power-automate-architect/respaldos/`, auditoría previa que
  bloquea hallazgos ALTA (`--forzar` para anular), y dry-run por defecto
  (`--si` para ejecutar). Verificado en vivo (dry-run + gate) y offline
  (`evals/verificar_conector.py`: 18/18).
- **Skill `pa-conectado` reescrita**: ciclo por lenguaje natural
  descargar → editar → auditar → confirmar → subir → validar corridas; creación
  guiada con máx. 2-3 preguntas partiendo de `flujo-limpio.json`.
- **Portabilidad multi-agente (investigada e implementada, fase 0):**
  `AGENTS.md` canónico (estándar Linux Foundation, 28+ herramientas),
  `CLAUDE.md` reducido a import `@AGENTS.md` + notas propias, `GEMINI.md`
  puntero, y espejo `.agents/skills/` (estándar Agent Skills que leen Codex,
  Gemini CLI y OpenCode) generado por `scripts/sincronizar_skills.py`
  (convierte `${CLAUDE_PLUGIN_ROOT}` a rutas relativas). Roadmap: servidor MCP
  en PyPI (capa universal: los 4 ecosistemas son clientes MCP) y bundle
  `.mcpb` de doble clic para no técnicos.

## [0.4.0] — 2026-07-18

### Agregado — IA + actualizador permanente (fase 5)
- **5 reglas de IA/agent flows** (39 en total), derivadas de la investigación de
  las "AI capabilities" del diseñador (ver `references/ia-en-flujos.md`):
  PA-IA-01 (salida de IA sin validación ni humano en el circuito), PA-IA-02
  (acción de IA dentro de un bucle: quema créditos), PA-IA-03 (INFO: consumo de
  créditos + fin de créditos incluidos nov-2026), PA-AGT-01 (agent flow sin
  'Respond to the agent' o con salidas distintas por rama), PA-AGT-02 (trigger
  de agente con parámetros genéricos). Detección: conector Dataverse +
  operationId (aibuilder)predict; trigger Request/Skills.
- `references/ia-en-flujos.md`: qué es cada AI capability, tarifas de créditos,
  restricciones (privacidad, DLP, regiones, timeout), cuándo usar IA y cuándo no.
- **Vigilante del catálogo** `scripts/actualizar_catalogo.py` + skill
  `pa-actualizar`: detecta commits/páginas nuevas en las fuentes oficiales
  (coding-guidelines, limits, Well-Architected, ALM, Power CAT) con 1 llamada
  pública por fuente; estado en `references/estado-fuentes.json`; exit 1 = hay
  cambios. Probado contra datos reales (12 commits en coding-guidelines y 28 en
  ALM detectados en ventanas históricas).
- Eval nuevo `flujos/flujo-agente-ia.json` (regresión 5/5 exacta).

### Validado en vivo (2026-07-17)
- Login real en un tenant corporativo sin aprobación de administrador; listado de entornos
  y flujos del tenant; auditoría en vivo del flujo "prueba" (76/100). Fase 2
  cerrada de punta a punta.

## [0.3.0] — 2026-07-16

### Agregado — Fase 2: modo conectado de lectura (login único → todos los flujos)
- `scripts/pa_api.py`: conector local a la maker API de Power Automate con MSAL.
  Un login (navegador o `--device`) con client first-party de Microsoft (sin
  registrar apps; `--client-id` propio como fallback), caché de tokens cifrada
  (DPAPI vía msal-extensions). Comandos: `login`, `logout`, `entornos`, `flujos`
  (TODOS: Mis flujos + soluciones, con `includeSolutionCloudFlows`), `flujo`
  (detalle + `--guardar` definición), `corridas`, `auditar` (descarga + 34 reglas
  local). Reintentos con backoff en 429/5xx; estado "Suspendido" (DLP) visible.
- Skill `skills/pa-flujos/SKILL.md`: modo conectado de lectura para el asistente.
- `evals/verificar_conector.py`: prueba offline del conector (API simulada):
  paginación nextLink, detección de entorno por defecto, parámetro
  includeSolutionCloudFlows, normalización de connectionReferences y ciclo
  descargar→auditar = 100/100. 8/8 verificaciones.
- Dependencias del modo conectado: `msal`, `msal-extensions` (el modo auditor
  offline sigue siendo 100% stdlib).

### Validado
- Fase 1 re-verificada: regresión 4/4, zip = json (20 hallazgos idénticos),
  casos borde con exit 2 y mensaje claro.

## [0.2.0] — 2026-07-16

### Agregado
- **Catálogo ampliado de 14 → 34 reglas** en `scripts/auditar_flujo.py`, alineado con
  el Power CAT Tools Code Review de Microsoft. Nuevas: PA-CONC-01 (condición de
  carrera en bucles paralelos), PA-ERR-03 (Catch sin Terminate), PA-SEC-03 (secure
  inputs/outputs), PA-SEC-04 (trigger HTTP sin restricción), PA-TEST-01 (static
  results olvidados), PA-TRG-02/03/04 (concurrencia de trigger, bucle infinito,
  filteringattributes), PA-PERF-08..12 (paginación, timeouts de espera, Do-until,
  Delay en bucle, Split On), PA-VAR-01/02 (variables sin usar / constantes),
  PA-SIZE-01/02 (tamaño y Scopes), PA-CFG-01 (config hardcodeada), PA-DOC-02
  (descripción del flujo) y PA-LIC-01 (nota informativa de conectores premium,
  nueva severidad INFO con peso 0).
- **Suite de regresión** `evals/verificar_auditor.py` + 4 flujos de prueba en
  `evals/flujos/` (3 con fallas deliberadas, 1 limpio que exige 100/100): compara
  los códigos detectados de forma EXACTA — cero falsos positivos tolerados.
- Estado de implementación de candidatas anotado en `references/reglas-candidatas.md`
  (20 de 30 implementadas; pendientes documentadas con su porqué).

### Corregido
- Los helpers del auditor ya no fallan cuando `inputs` de una acción es un string
  (caso Compose con expresión directa).

## [0.1.0] — 2026-07-16

### Existente
- **Modo Auditor** (`skills/pa-auditoria`): auditoría offline de flujos exportados
  (.zip / carpeta / definition.json) con `scripts/auditar_flujo.py` — 14 reglas
  PA-xxx basadas en Microsoft Learn coding guidelines + Well-Architected.
  Verificado E2E el 2026-07-15 (13/13 detecciones en flujo de prueba).
- **Modo conectado** (`skills/pa-conectado`): guía documental del ciclo con pac CLI
  (pendiente de reemplazar por la capa API propia — ver roadmap).
- Catálogo de reglas con fuentes: `references/buenas-practicas.md`.

### Agregado (investigación 2026-07-15)
- `references/api-conexion.md` — arquitectura login único → todos los flujos
  (MSAL + maker API + Dataverse Web API).
- `references/reglas-candidatas.md` — 30 reglas nuevas candidatas (alineación con
  Power CAT Tools) + flujo de actualización permanente del catálogo.
- `references/panorama-herramientas.md` — panorama jul-2026 de MCP/herramientas y
  veredicto reutilizar-vs-construir.
- Higiene de proyecto: git, `.gitignore`, `LICENSE` (MIT), `CHANGELOG.md`, `CLAUDE.md`.
