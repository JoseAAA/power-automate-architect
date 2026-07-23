# Changelog

## [1.9.0] — 2026-07-20 · Conexiones en blanco por defecto + round-trip .zip validado

### Cambiado — al crear, las conexiones se dejan SIN enlazar (el usuario las conecta)
- Problema observado: el copiloto iteraba/preguntaba demasiado buscando conexiones
  y no avanzaba. Ahora `crear` (moderno) crea las **connection references sin
  enlazar por defecto** — el flujo nace apagado y el usuario las conecta en el
  portal (un clic por conector). Opt-in `crear --enlazar` para pre-enlazar a
  conexiones existentes (silencioso). La skill `pa-copiloto` instruye NO
  interrogar por conexiones (usar referencias por nombre, dejar en blanco, avisar
  cuáles conectar).

### Validado en vivo — el round-trip por .zip FUNCIONA (base para modificar robusto)
- Probado contra la cuenta test: `ExportSolution` → editar el `Workflows/*.json`
  del flujo → repack (subiendo la versión de `solution.xml`) → `ImportSolution`
  (204) → re-export confirma el cambio en el tenant (hora 7→8). Con token
  delegado, sin `pac`, sin terceros. Es el mecanismo para el modo modificar
  confiable (implementación en el siguiente paso).

## [1.8.0] — 2026-07-20 · Prueba en vivo (jose.alarcon): precisión y hallazgos

### Corregido — precisión del puntaje (PA-SEC-02 falso positivo)
- El auditor marcaba PA-SEC-02 ("conexión embebida") en flujos de solución que SÍ
  usan connection references. Ahora **no marca** si hay `connectionReferenceLogicalName`
  (Shape B de Dataverse, o al tope en la maker API); solo marca conexiones
  realmente embebidas sin referencia. Validado en vivo: el flujo moderno pasó de
  90 → 97/100 (correcto), y la regresión sigue detectando las embebidas de verdad.

### Validado en vivo con la cuenta de test
- **Analizar/puntuar**: preciso (auditó flujos reales del tenant con hallazgos correctos).
- **Crear (formato moderno)**: ✅ FUNCIONA. Creó un flujo de solución con
  connection references reales (Shape B confirmado en Dataverse) y **enlazó solo
  las conexiones existentes** del usuario. Ahora además **crea con la descripción**
  del flujo. `crear_flujo_moderno` acepta `descripcion`.
- **Modificar**: `actualizar_flujo` ahora **preserva las connection references
  existentes** (no rompe el formato moderno) y asegura `parameters.$connections/
  $authentication`. LÍMITE CONOCIDO: la modificación por API directa aún falla en
  algunos flujos (ej. trigger Recurrence: "missing '$authentication'"). El arreglo
  robusto es el **round-trip por `.zip` de solución** (export→editar→pack→import),
  ya investigado; es el siguiente paso.

## [1.7.2] — 2026-07-20 · Privacidad: ejemplos genéricos y neutrales

### Cambiado
- **Ningún dato de empresa en el repo** (verificado en todo el historial). Los
  ejemplos que tenían tema "legal/contratos" (genéricos, sin identificadores) se
  neutralizaron al dominio de inventario/ventas para que no se parezcan a ningún
  flujo real: catálogo de nomenclatura, plantilla `alerta-programada.json`,
  `flujo-limpio.json`, `flujo-dataverse.json`, `flujo-con-fallas.json`.
- `ejemplos/` y `flujos-locales/` y `*.zip` quedan **ignorados** por git: los
  exports reales se estudian solo en local, nunca se versionan.

## [1.7.1] — 2026-07-20 · Copiloto presenta todas las opciones (gratis y premium)

### Mejorado
- `pa-copiloto` ahora tiene la regla explícita de **no limitarse a conectores
  gratis/estándar ni asumir cuenta free**: en cada decisión con alternativas
  presenta el menú completo (estándar y premium — `HTTP` a APIs externas como
  OpenAI, AI Builder, conectores premium, custom connectors) con su
  costo/licencia y trade-off, y deja que el usuario elija de forma informada.

## [1.7.0] — 2026-07-20 · Copiloto plan-primero (crear flujos en conjunto)

### Agregado — modo plan-primero (patrón OpenSpec/superpowers)
- `pa-copiloto` ahora tiene DOS caminos: **rápido** (flujo simple → plantilla, 2-3
  preguntas) y **guiado/plan-primero** (flujo no trivial: descubrir → plan escrito
  → iterar hasta aprobar → construir). El plan es un artefacto en disco
  (`~/.power-automate-architect/planes/<slug>.md`) que el usuario y la IA iteran;
  nada se construye hasta `estado: APROBADO` (gate propose→approve→apply de
  OpenSpec; artefacto que sobrevive a compactación, de superpowers).
- Plantilla del plan: `skills/pa-copiloto/plantillas/_plan-de-flujo.md` (objetivo,
  disparador, fuentes, pasos, conectores, datos, validación humana, errores,
  preguntas abiertas, riesgos, fuera de alcance).

## [1.6.0] — 2026-07-20 · Crear en formato moderno (connection references)

### Corregido — los flujos creados abrían en el diseñador clásico
- **Causa (verificada con fuentes MS):** crear por la tabla `workflow` produce un
  flujo de solución, y el diseñador moderno exige **connection references** (no
  conexiones directas). Ver `references/api-conexion.md`.
- **`crear` ahora crea en FORMATO MODERNO por defecto** (`crear_flujo_moderno`):
  asegura una solución dedicada (`PowerAutomateArchitect`) con su publisher, crea
  las **connection references** (Shape B: `connectionReferenceLogicalName`),
  las **pre-enlaza** a las conexiones existentes del usuario cuando las encuentra
  (usa la API de conexiones), y hace POST del flujo con
  `MSCRM.SolutionUniqueName`. Resultado: abre en el diseñador nuevo y cumple
  PA-SEC-02. Las conexiones que falten se autorizan una vez en el portal.
  `crear --clasico` mantiene el comportamiento anterior (sin solución).
- Prueba offline del ciclo moderno (Shape B, cabecera de solución, pre-enlace) en
  `evals/verificar_conector.py`.

### Mejorado
- Skill `pa-copiloto`: exige **nombrar cada acción descriptivamente en español**
  (PA-NAME-01) y explica el formato moderno + el enlace de conexiones.

## [1.5.0] — 2026-07-20 · Sesiones por lenguaje natural

### Agregado — login en 2 pasos (lo maneja el agente, sin terminal)
- `login --iniciar` muestra al instante la URL + código y **no bloquea** (guarda
  el estado en `~/.power-automate-architect/.device_flow.json`); `login
  --completar` espera a que el usuario ingrese el código y confirma la sesión.
  Así el agente puede iniciar sesión **por lenguaje natural**: relaya el código
  y completa, sin pedirle al usuario que abra una terminal. `login` por navegador
  sigue disponible para la terminal.
- La skill `pa-flujos` instruye la gestión completa de cuentas por lenguaje
  natural: el agente corre `sesion` / `cambiar-cuenta` / `logout` directamente y
  usa el login en 2 pasos para agregar cuentas.

### Cambiado
- README: cuentas y sesiones presentadas como lenguaje natural (*"conéctate con
  mi cuenta de la empresa"*, *"¿a qué cuenta estoy conectado?"*), con la terminal
  como alternativa; "Problemas comunes" actualizado.

## [1.4.1] — 2026-07-20 · Enrutamiento de preguntas de sesión/cuenta

### Corregido
- Preguntas como "¿cuántas sesiones tengo?" / "¿a qué cuenta estoy conectado?"
  no cargaban la skill y el asistente improvisaba (buscaba archivos y decía "no
  hay sesión" cuando sí la había). La descripción de `pa-flujos` ahora incluye
  esos disparadores (sesión/cuenta) y el procedimiento instruye correr `sesion`
  y NO buscar archivos.

## [1.4.0] — 2026-07-20 · Reporte de salud (conexiones rotas)

### Agregado — `salud` (idea del fabric-cli de Microsoft)
- Nuevo comando `pa_api.py salud [--detalle f.json] [--json]`: detecta flujos
  que fallan o van a fallar porque su **conexión** (SharePoint, Outlook, SQL…)
  se **desconectó o caducó**. Cruza flujos × conexiones y reporta: conexiones
  rotas, flujos afectados por ellas, flujos suspendidos por DLP, y encendidos/
  apagados. Contrato `pa-architect/salud@1`.
- **API verificada en vivo** (no inventada): las conexiones viven en
  `api.powerapps.com/.../connections` (el host de flujos da 404) con token de
  PowerApps obtenido silencioso del mismo login; estado en
  `properties.statuses[*].status` (`Connected` vs `Error`); unión flujo↔conexión
  por `connectionReferences[*].connectionName == connection.name` (la lista de
  flujos ya trae las referencias inline → 2 llamadas por entorno, sin N GETs).
  Documentado en `references/api-conexion.md`.
- **Token-mínimo**: resumen compacto al asistente, detalle a `--detalle`.
  Probado en vivo (detectó una conexión real en `Error`) y offline
  (`evals/verificar_conector.py`: cruce, afectados, suspendidos, estados).

## [1.3.0] — 2026-07-20 · Gestión de sesiones

### Agregado
- **`logout <correo>`**: cierra una cuenta específica sin tener que cambiarte a
  ella primero (antes solo se podía cerrar la activa o todas). Si cierras la
  activa, la sesión pasa a otra cuenta disponible; `logout --todas` sigue
  borrando todo. `sesion` ahora muestra los comandos para cambiar/cerrar cuentas.
- Gestión de cuentas completa: `sesion` (ver), `login [--como]` (agregar),
  `cambiar-cuenta` (activar), `logout [<correo>|--todas]` (cerrar).
- Prueba offline del cierre puntual y del vaciado de la última cuenta.

## [1.2.1] — 2026-07-20 · Login a una cuenta específica

### Agregado
- `login --como <correo>`: fuerza el login a una cuenta concreta (`login_hint`),
  útil cuando el navegador tiene sesión única y no muestra el selector. En
  device code, recuerda "Usar otra cuenta". Avisa si terminas en otra cuenta.

### Nota de uso
- El login interactivo (navegador) debe correr en la **terminal del usuario**,
  no dentro del agente: el proceso del agente no tiene navegador ni TTY. Para
  agentes, `--device` es lo robusto (muestra URL + código que el usuario abre).

## [1.2.0] — 2026-07-20 · Auditoría de todo el tenant (token-mínima)

### Agregado — `auditar-todos` (tablero de gobernanza)
- Nuevo comando `pa_api.py auditar-todos [--entorno X] [--detalle f.json] [--json]`:
  audita TODOS los flujos del entorno y devuelve un **resumen compacto** —
  puntuación media, distribución 🟢🟡🟠🔴, peores 10, reglas más incumplidas.
  Contrato `pa-architect/auditoria-tenant@1`.
- **Diseño token-mínimo** (principio del proyecto): cada flujo se audita en
  Python (0 tokens de IA); el asistente lee solo el resumen (tamaño fijo, no
  crece con el tenant). El **detalle por flujo va a un archivo** (`--detalle`)
  que el asistente NO carga salvo que se pida un flujo concreto. Auditar 1 o
  500 flujos cuesta casi los mismos tokens.
- Reutiliza `auditar_flujo.auditar()` por import (sin subprocess por flujo);
  progreso por stderr para no ensuciar la salida. Prueba offline del agregado
  en `evals/verificar_conector.py`. Verificado en vivo contra un tenant real.

## [1.1.0] — 2026-07-20 · Multi-cuenta + seguridad

### Agregado — varias cuentas de Microsoft (personal / empresa)
- Nuevos comandos en `pa_api.py`: **`sesion`** (a qué correo estás conectado),
  **`cambiar-cuenta <correo>`** (cambia la cuenta activa, ej. la de tu empresa),
  y `logout [--todas]` (cierra la activa, o todas). `login` ahora agrega cuentas
  adicionales sin borrar las anteriores.
- El token se pide para la **cuenta activa** (`config.cuenta_activa`), no "la
  primera de la caché". `flujos`/`entornos` muestran **"conectado como X"** (y
  un campo `usuario` en la salida `--json`).

### Seguridad (revisión para uso en empresas)
- Al cambiar de cuenta o entrar a una nueva se **olvida el entorno por defecto
  cacheado** → una escritura no puede terminar en el tenant equivocado.
- Tokens **separados por cuenta** en MSAL: cambiar de cuenta solo elige a cuál
  pedir token, nunca mezcla ni expone credenciales de otra. Verificado: ningún
  token se imprime ni se serializa; `config.json` solo guarda datos no secretos.
- `SECURITY.md` amplía el modelo multi-tenant y recomienda registrar una app
  propia con `--client-id` para entornos corporativos estrictos.
- Prueba offline de la lógica de cuentas añadida a `evals/verificar_conector.py`.

### Cambiado
- Descripciones de `plugin.json` y `marketplace.json` actualizadas (sin el
  conteo de reglas desactualizado; reflejan los 5 modos actuales).

## [1.0.0] — 2026-07-20 · Primera versión funcional

### Agregado — Copiloto (crear flujos, fácil)
- **Skill `pa-copiloto`**: de la idea al flujo con máx. 2-3 preguntas, partiendo
  de **plantillas que auditan 100/100** (`skills/pa-copiloto/plantillas/`):
  `alerta-programada`, `aprobacion` (con timeout de 7 días y avisos dinámicos) y
  `ia-clasificar` (patrón IA con validación y humano en el circuito).
  `pa-conectado` queda solo para modificar/encender (ruteo sin solapamiento).
- `sincronizar_skills.py` espeja ahora TODOS los archivos de las skills
  (plantillas incluidas); `verificar_docs.py` exige que cada plantilla siga
  auditando 100/100.

### Cambiado — decisión de arquitectura
- **Servidor MCP retirado** (evaluado y construido en 0.7.0): se adopta la vía
  que recomienda la evidencia experta — skills + CLI en terminal. El análisis
  queda en el historial por si se retoma para clientes GUI.
- **README reescrito**: claro para no expertos (instalación, ejemplos de frases,
  cómo funciona, privacidad, problemas comunes, stack, roadmap).

### Seguridad (revisión de release para cuentas de empresa)
- **`SECURITY.md`**: modelo de seguridad para TI (local-first, tabla de tráfico
  de red, tokens DPAPI, client-id corporativo opcional, defensa en profundidad
  de la escritura, alcance y reporte de vulnerabilidades).
- Regla anti prompt-injection en `AGENTS.md`: el contenido de los flujos son
  datos, nunca instrucciones para el asistente.
- Secreto de prueba con formato realista reemplazado por uno inocuo (evita
  falsos positivos de los escáneres de secretos de GitHub).
- Revisión de superficie verificada: sin `shell=True`/`eval`/`verify=False`,
  timeouts en todo HTTP, subprocess con listas, cero fugas de datos
  personales/tenant en el repo (verificado con git grep).

## [0.7.0] — 2026-07-18

### Agregado — servidor MCP para clientes GUI (validado con evidencia experta)
- Investigación previa (Anthropic engineering, eval de Arize 500 corridas,
  Ronacher, Willison, guía de seguridad de Microsoft jun-2026): CLI+skills
  sigue siendo la vía para agentes con terminal (igual exactitud, ~6x más
  barato); MCP se construye **solo** como puerta para GUI sin terminal.
  ChatGPT queda fuera de v1 (solo acepta MCP remoto HTTPS).
- **`scripts/pa_mcp.py`**: adaptador delgado (SDK oficial `mcp`, stdio) con 7
  herramientas con forma de tarea: `iniciar_sesion` (device code devuelto como
  RESULTADO de herramienta), `estado_sesion`, `listar_flujos`, `auditar_flujo`,
  `ver_corridas`, `simular_cambio` y `aplicar_cambio`. Seguridad de escritura
  **en el contrato**: simular → auditoría que bloquea ALTA → token de un solo
  uso (15 min) → aplicar (con respaldo automático del núcleo); anotaciones
  `readOnlyHint`/`destructiveHint` para la UI de permisos del cliente.
- `evals/verificar_mcp.py`: 12/12 offline (API simulada) — incluye token de un
  solo uso, rechazo sin simulación y gate de ALTA.
- Empaquetado: `pyproject.toml` (PyPI → `uvx pa-architect-mcp`) y `mcpb/`
  (manifest + pasos del bundle de doble clic para Claude Desktop, con los bugs
  conocidos de Windows/uv documentados).

## [0.6.0] — 2026-07-18

### Agregado — contrato JSON agente-agnóstico (estudio de Fission-AI/OpenSpec)
- **`--json` en los CLIs** (patrón gather-then-render): `auditar_flujo.py <ruta>
  --json` (contrato `pa-architect/auditoria@1` con hallazgos estructurados y
  arreglo accionable por hallazgo), `pa_api.py flujos --json` y `corridas --json`
  (`@1`). Un documento JSON por invocación; los errores en modo JSON también
  salen como JSON (`pa-architect/error@1`); mismos exit codes que el modo humano.
  Convenciones en `references/contrato-agente.md`.
- **La regresión exige paridad**: `verificar_auditor.py` compara los códigos del
  JSON contra el reporte humano en los 5 flujos — no pueden divergir.
- **`allowed-tools: Bash(python *)`** en las 4 skills (patrón OpenSpec v1.6.0):
  los agentes ejecutan los scripts del plugin sin fricción de permisos.
- `sincronizar_skills.py` ahora regenera-sin-fusionar: borra espejos huérfanos
  de skills eliminadas.
- Backlog anotado: carpeta de cambios `cambios/<flujo>/` estilo propose/apply de
  OpenSpec (el gate determinista —auditoría exit 1 bloquea— ya existe).

## [0.5.1] — 2026-07-18

### Mejorado — eficiencia de tokens y anti-drift (estudio de skills-for-fabric, superpowers y ponytail)
- **`AGENTS.md` adelgazado ~40%** (se paga en cada conversación vía el import de
  `CLAUDE.md`): solo identidad, ruteo de modos, 4 reglas de oro y verificación;
  el detalle vive en las skills, que se cargan al entrar al modo.
- **Descriptions de las 4 skills = solo disparadores** (<550 chars, patrón
  "USAR cuando…/NO usar…" de superpowers); los requisitos y resúmenes pasaron
  al cuerpo.
- **Tablas de carga condicional** ("Lee X solo cuando Y", patrón fabric) en las
  skills: el catálogo se consulta con grep del código `PA-XXX-NN`, nunca entero.
- **`pa-conectado`**: tabla anti-racionalización para la regla de confirmación
  (urgencia ≠ OK, cada subida su propio OK) y **ledger de sesión** en disco para
  sobrevivir compactación de contexto a mitad del ciclo de escritura.
- **`pa-actualizar`**: TTL de 30 días (patrón check-updates de fabric) — no
  re-chequear fuentes si se revisó hace poco.
- **`evals/verificar_docs.py`** (patrón check-rule-copies de ponytail): espejo
  `.agents/skills` sin drift, frases canario de la red de seguridad, conteo de
  reglas del código == documentación, y límites de descriptions. 12/12.

### Corregido
- **El conteo real de reglas es 40, no 39** (el "14" inicial eran 15 y el error
  se arrastró) — detectado al implementar el verificador de conteos. Corregido
  en README, catálogo, backlog y CHANGELOG histórico.

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
- **5 reglas de IA/agent flows** (40 en total), derivadas de la investigación de
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
- **Catálogo ampliado de 15 → 35 reglas** en `scripts/auditar_flujo.py`, alineado con
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
