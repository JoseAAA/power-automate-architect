# Reglas candidatas para ampliar el catálogo (15 → ~45)

> `investigado: 2026-07-15` · Fuente de calibración principal: **Power CAT Tools –
> Code Review Tool** (Microsoft, [GitHub](https://github.com/microsoft/Power-CAT-Tools)),
> endosado oficialmente por el índice de coding guidelines. Al implementar cada
> regla, moverla a `buenas-practicas.md` y a `scripts/auditar_flujo.py`.

## Estado de implementación (2026-07-16 · v0.2.0: 20 de 30 implementadas)

Implementadas: #1→PA-CONC-01 · #2→PA-SEC-03 · #3→PA-SEC-04 · #4→PA-TRG-03 ·
#5→PA-TEST-01 · #6 y #12→PA-PERF-08 (fusionadas) · #7→PA-PERF-09 (esperas/webhook) ·
#8→PA-PERF-10 · #10→PA-CFG-01 · #13→PA-TRG-04 · #14→PA-TRG-02 · #15→ya cubierta por
PA-ERR-02 · #16→PA-ERR-03 · #18→PA-PERF-11 · #19→PA-SIZE-01 · #20→PA-SIZE-02 ·
#21→PA-VAR-01 · #22→PA-VAR-02 · #24→PA-DOC-02 · #25→PA-PERF-12 · #28→PA-LIC-01.

**Adición 2026-07-18 (investigación de AI capabilities, ver `ia-en-flujos.md`):**
PA-IA-01/02/03 y PA-AGT-01/02 implementadas (40 reglas). Pendientes de IA: manejo
de error por acción de IA (cuota/moderación/timeout 2 min — hoy lo cubre el
Try/Catch global), detección de "Run a generative action" (firma JSON desconocida,
preview) y detección del modelo usado (Claude/Grok externos — el modelo vive en el
registro del prompt en Dataverse, no en el definition.json).

Pendientes y por qué: **#9** flujo fuera de solución (se sabrá con el modo conectado,
no desde el definition.json exportado) · **#11** falta `$select` (afinar para no ser
ruidosa) · **#17** contrato de flujo hijo (requiere ver la solución completa) ·
**#23** acciones deprecadas (requiere lista curada de apiIds/acciones deprecadas) ·
**#26** estimación de burst (heurística especulativa) · **#27** ETL en flujo (requiere
juicio, mejor como observación del asistente) · **#29** higiene de dueños (requiere
API, va con el modo conectado) · **#30** paralelismo desaprovechado (análisis de
dependencias, riesgo de falsos positivos).

## Contexto 2025-2026 (afecta al catálogo)

- **Power CAT Tools** trae 13 patrones automatizados para cloud flows. Ya cubrimos ~6.
  Nos faltan: variables sin usar, variable estática→Compose, consolidar Initialize
  Variable, Scope si >10 acciones, >50 acciones total, chequeo de concurrencia,
  acción deprecada "Respond to PowerApp". Alinear severidades con las suyas
  (Critical/Warning/Suggestion).
- **CoE Starter Kit retirado (feb-2026)** — no citarlo como framework vigente; sus
  funciones ahora son nativas del admin center: [Inventory](https://learn.microsoft.com/power-platform/admin/power-platform-inventory),
  Usage, Monitor y [Actions/Advisor](https://learn.microsoft.com/power-platform/admin/power-platform-advisor), + [Inventory API](https://learn.microsoft.com/power-platform/admin/inventory-api).
- **Agent flows** (Copilot Studio) usan el mismo JSON de definición → el catálogo
  aplica; agregar reglas específicas (descripciones de entradas/salidas para que
  agentes/Copilot los invoquen bien).
- El **modelo de madurez de adopción** sigue vigente ([maturity model](https://learn.microsoft.com/power-platform/guidance/adoption/maturity-model-details)).
- Sección coding-guidelines completa: **26 páginas** — incluye varias que el catálogo
  aún no explota: `understand-limits`, `create-scopes`, `implement-parallel-execution`,
  `asychronous-flow-pattern` (slug con typo, es estable), `keep-flow-configuration-generic`,
  `leave-complex-business-logic-out`, `test-cloud-flows`, `monitoring-and-alerting`,
  `prevent-data-exfiltration`, `use-cmk-for-cloud-flows`.

## Tabla de reglas candidatas

Severidades: 🔴 Crítica · 🟠 Alta · 🟡 Media · 🔵 Baja/Sugerencia · ℹ️ Info

| # | Regla propuesta | Qué chequear en `definition.json` | Sev | Fuente |
|---|---|---|---|---|
| 1 | Concurrencia de bucle mal configurada | `Foreach.runtimeConfiguration.concurrency.repetitions` >1 con `SetVariable`/`Append` en el cuerpo = **condición de carrera**; sugerir subir (≤50) si el cuerpo es I/O independiente | 🔴 | [Power CAT #6](https://github.com/microsoft/Power-CAT-Tools/blob/main/CODE_REVIEW.md), [anti-patterns](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/avoid-anti-patterns) |
| 2 | Secure inputs/outputs ausentes en acciones sensibles | `runtimeConfiguration.secureData.properties` faltante donde los inputs traen Authorization/password/Key Vault | 🔴 | [secure-inputs](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/use-secure-inputs-outputs-triggers) |
| 3 | Trigger HTTP sin autenticación | trigger `Request` sin OAuth Entra ID / restricción de quién dispara | 🔴 | ídem |
| 4 | Riesgo de bucle infinito de trigger | trigger y acción de escritura sobre la MISMA tabla/lista sin trigger condition ni `filteringattributes` | 🔴 | [avoid-anti-patterns](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/avoid-anti-patterns) |
| 5 | Static results habilitados (artefacto de prueba) | `runtimeConfiguration.staticResult.staticResultOptions == "Enabled"` | 🔴 | [test-cloud-flows](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/test-cloud-flows) |
| 6 | Paginación apagada en acciones de listado | sin `paginationPolicy.minimumItemCount` ni `$top` → truncamiento silencioso al tamaño de página | 🟠 | [work-with-relevant-data](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/work-with-relevant-data) |
| 7 | HTTP / acción de espera sin timeout | `limit.timeout` ausente en HTTP/aprobaciones; valor > P29D (tope de corrida: 30 días) | 🟠 | [limits-and-config](https://learn.microsoft.com/power-automate/limits-and-config) |
| 8 | Do-until sin límites sanos | `Until.limit.count/timeout` faltantes o enormes; condición que nunca muta en el cuerpo | 🟠 | ídem |
| 9 | Flujo fuera de solución | sin bloque `connectionReferences` de solución / entregado suelto — prerrequisito de ALM | 🟠 | [solution-aware](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/understand-benefits-solution-aware-flows) |
| 10 | Valores de entorno hardcodeados (más allá de secretos) | GUIDs, URLs de sitio, correos como literales en `inputs` en vez de environment variables | 🟠 | [keep-flow-configuration-generic](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/keep-flow-configuration-generic) |
| 11 | Sin `$select` (poda de columnas) | acciones de listado Dataverse/SharePoint sin Select columns | 🟡 | [work-with-relevant-data](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/work-with-relevant-data) |
| 12 | Sin tope de filas | listados sin `$top`/row count → recuperación sin límite (throttle 14 días apaga el flujo) | 🟡 | ídem |
| 13 | Trigger Dataverse sin filtro de columnas | trigger added/modified sin `filteringattributes` → dispara en cada cambio de columna | 🟡 | [optimize-triggers](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/optimize-power-automate-triggers) |
| 14 | Concurrencia de trigger sin revisar | `trigger.runtimeConfiguration.concurrency.runs` en triggers de alto volumen; advertir que es **irreversible** | 🟡 | ídem |
| 15 | Retry policy = "none" explícito | `retryPolicy.type == "none"` en acciones de red (distinto de "sin política") | 🟡 | [error-handling](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/error-handling) |
| 16 | Catch sin Terminate (o Terminate en bucle) | scope Catch sin `Terminate(Failed)+mensaje`; `Terminate` dentro de loop | 🟡 | ídem |
| 17 | Contrato de flujo hijo roto | acción `Workflow` hacia hijo en OTRA solución; hijo sin `Respond`; padre sin run-after de error en la llamada | 🟡 | [create-reusable-code](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/create-reusable-code) |
| 18 | Delay dentro de bucle | `Wait` en `Foreach`/`Until` — riesgo de duración y burst | 🟡 | [limits-and-config](https://learn.microsoft.com/power-automate/limits-and-config) |
| 19 | Flujo demasiado grande | >50 acciones totales → refactorizar a flujos hijos | 🔵 | [Power CAT #9](https://deepwiki.com/microsoft/Power-CAT-Tools/3.1.2-power-automate-review-patterns) |
| 20 | Sin Scopes en flujo largo | >10 acciones y cero `Scope` | 🔵 | [create-scopes](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/create-scopes) |
| 21 | Variables sin usar | `InitializeVariable` cuyo nombre nunca aparece en `variables('x')` | 🔵 | [Power CAT #1](https://deepwiki.com/microsoft/Power-CAT-Tools/3.1.2-power-automate-review-patterns) |
| 22 | Variable estática → Compose | variable inicializada y nunca objetivo de Set/Append | 🔵 | [Power CAT #2](https://deepwiki.com/microsoft/Power-CAT-Tools/3.1.2-power-automate-review-patterns) |
| 23 | Acciones/conectores deprecados | `Respond to PowerApp` legacy (vs V2); conector marcado deprecated en el connector reference | 🔵 | [Power CAT #12](https://deepwiki.com/microsoft/Power-CAT-Tools/3.1.2-power-automate-review-patterns) |
| 24 | Descripción del flujo vacía | `description` top-level faltante (clave también para Copilot/agent flows) | 🔵 | [Power CAT](https://github.com/microsoft/Power-CAT-Tools), [agent flows](https://learn.microsoft.com/microsoft-copilot-studio/flows-overview) |
| 25 | Oportunidad splitOn/debatching | trigger devuelve array, `splitOn` apagado y el cuerpo itera el output del trigger | 🔵 | [limits-and-config](https://learn.microsoft.com/power-automate/limits-and-config) |
| 26 | Estimación de burst de acciones | ítems del bucle × acciones/iteración cerca de 100k acciones/5 min | ℹ️ | [understand-limits](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/understand-limits) |
| 27 | ETL dentro del flujo | cadenas largas de transformación sobre datasets grandes → recomendar dataflows | ℹ️ | [avoid-anti-patterns](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/avoid-anti-patterns) |
| 28 | Señal de licencia premium | acciones con conectores premium (HTTP, Dataverse) → nota informativa | ℹ️ | [licensing types](https://learn.microsoft.com/power-platform/admin/power-automate-licensing/types) |
| 29 | Higiene de dueños/run-only (requiere API, no definition.json) | dueño único (bus factor), dueño huérfano, run-only demasiado amplio | 🟡 | [understand-access-to-flows](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/understand-access-to-flows) |
| 30 | Paralelismo desaprovechado | ramas independientes en secuencia → parallel branches | 🔵 | [implement-parallel-execution](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/implement-parallel-execution) |

## Canon de la comunidad (2026)

- Matthew Devaney — [Coding Standards (PDF 60+ pág.)](https://www.matthewdevaney.com/power-automate-coding-standards-for-cloud-flows/)
- Forward Forever — [Naming convention](https://forwardforever.com/naming-convention-for-power-automate/)
- **David Wyatt** (nuevo referente en análisis estático) — [AutoReview](https://dev.to/wyattdave/autoreview-auto-code-reviews-for-power-automate-26no), serie "Code Review Onion"
- Matt Collins-Jones — [Artemis framework standards](https://github.com/MattCollins-Jones/PowerAutomateArtemisFramework/wiki/Cloud-Flow-Coding-Standards)
- Tom Riha ([tomriha.com](https://tomriha.com/posts-on-this-blog-thatll-help-you-build-better-power-automate-flows/)) · Pieter Veenstra ([sharepains.com](https://sharepains.com/)) · Damien Bird ([damobird365.com](https://www.damobird365.com/)) · Reza Dorrani ([YouTube](https://www.youtube.com/@RezaDorrani))
- Michael Harley — [naming/coding standards consolidados](https://michaelharley.net/doxipedia/power-automate-naming-conventions-coding-standards/)

## Flujo de actualización permanente del catálogo

Las guías viven en repos públicos de GitHub → detectar cambios es 1 llamada HTTP
por fuente (sin auth). Cadencia: **mensual** pasos 1-3, **semestral** paso 4.

1. Commits por carpeta desde la última revisión:
   - `https://api.github.com/repos/MicrosoftDocs/power-automate-docs/commits?path=articles/guidance/coding-guidelines&since={ISO}`
   - `https://api.github.com/repos/MicrosoftDocs/power-platform/commits?path=power-platform/well-architected&since={ISO}` (ídem `power-platform/alm`)
   - Alternativa RSS sin código: agregar `.atom` a la URL de commits de GitHub.
2. Páginas nuevas/renombradas: listar `/contents/articles/guidance/coding-guidelines` y comparar nombres contra el catálogo.
3. Releases de Power CAT Tools: `https://github.com/microsoft/Power-CAT-Tools/releases.atom` → diffear sus patrones de revisión.
4. Release planner (olas de abril/octubre): https://learn.microsoft.com/power-platform/release-plan/
5. Contexto (no reglas): blog Power Automate (`https://www.microsoft.com/en-us/power-platform/blog/power-automate/feed/`) y [PPWA What's new](https://learn.microsoft.com/power-platform/well-architected/whats-new).
6. Por cada regla del catálogo guardar: `source_url` + fecha/commit de verificación → el chequeo es "¿hay commit más nuevo que el mío en esa ruta?".
