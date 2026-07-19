# Catálogo de reglas y mejores prácticas — Power Automate Architect

> `actualizado: 2026-07-18` · **40 reglas automatizadas** en `scripts/auditar_flujo.py`.
> Fuentes normativas: **Microsoft Learn – Coding guidelines for cloud flows** (26
> páginas), **Power Platform Well-Architected** y el **Power CAT Tools – Code Review**
> de Microsoft (estándar de facto de revisión automatizada). Cómo refrescar: sección
> "Flujo de actualización" en `reglas-candidatas.md`.

Cada regla tiene un código `PA-xxx`. Aquí está el "por qué" en lenguaje llano y la
fuente oficial, para explicar hallazgos sin re-derivarlos (ahorra tokens) y mantener
el catálogo al día. Pesos: ALTA 15 · MEDIA 7 · BAJA 3 · INFO 0 (se descuentan de 100).

## Confiabilidad (Reliability)

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-ERR-01** (ALTA) | Manejo de errores (Scope *Try* + *Catch* con `runAfter` = Failed/TimedOut) | Sin esto, si un paso falla el flujo muere en silencio | [error-handling](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/error-handling) |
| **PA-ERR-02** (BAJA) | Reintentos exponenciales en acciones de conector (detecta también `none`/`fixed`) | Sobrevive fallos transitorios sin intervención | [WAF transient faults](https://learn.microsoft.com/power-platform/well-architected/reliability/handle-transient-faults) |
| **PA-ERR-03** (MEDIA) | Catch sin `Terminate(Failed)` / Terminate dentro de un bucle | Si el Catch no termina como fallido, la corrida figura EXITOSA y nadie se entera | [error-handling](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/error-handling) |

## Seguridad (Security)

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-SEC-01** (ALTA) | Secretos/credenciales escritos directo en el flujo | Un secreto en el JSON queda expuesto y viaja en cada export | [secure-inputs-outputs](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/use-secure-inputs-outputs-triggers) |
| **PA-SEC-02** (MEDIA) | Conexiones embebidas vs *Connection References* | Las references permiten mover el flujo entre entornos — base del ALM | [connection-reference](https://learn.microsoft.com/power-apps/maker/data-platform/create-connection-reference) |
| **PA-SEC-03** (ALTA) | Acción con material sensible (Authorization, claves, Key Vault) sin *Entradas/Salidas seguras* | Sin secure data, los valores quedan visibles en el historial de ejecución | [secure-inputs-outputs](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/use-secure-inputs-outputs-triggers) |
| **PA-SEC-04** (MEDIA) | Trigger HTTP "Cuando se recibe una solicitud" | Exigir OAuth Entra ID o restringir quién dispara; una URL SAS filtrada la usa cualquiera | ídem |

## Pruebas y artefactos

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-TEST-01** (ALTA) | *Static results* (mock) habilitados en una acción | La acción no ejecuta de verdad: artefacto de pruebas olvidado | [test-cloud-flows](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/test-cloud-flows) |

## Rendimiento y eficiencia (Performance)

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-PERF-01** (MEDIA) | `Anexar a variable` dentro de `Apply to each` | `Seleccionar` transforma todo el array de una vez | [use-data-operations](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/use-data-operations) |
| **PA-PERF-02** (MEDIA) | Bucles anidados | OData `$expand`/`Filter array` los elimina | [avoid-anti-patterns](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/avoid-anti-patterns) |
| **PA-PERF-03** (MEDIA) | Crear/Actualizar uno por uno en bucle | Batch / `CreateMultiple` es mucho más eficiente | [avoid-anti-patterns](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/avoid-anti-patterns) |
| **PA-PERF-04** (BAJA) | Demasiadas variables individuales (≥5) | Una variable objeto o `Compose` reduce acciones | [use-data-operations](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/use-data-operations) |
| **PA-PERF-05** (MEDIA) | Traer todas las filas y filtrar después | Filtrar en el origen (`$filter`) reduce datos y API calls | [use-data-operations](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/use-data-operations) |
| **PA-PERF-06** (MEDIA) | Bloques repetidos casi idénticos | Consolidar en bucle parametrizado o flujo hijo | [avoid-anti-patterns](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/avoid-anti-patterns) |
| **PA-PERF-07** (BAJA) | `Condition` dentro de un bucle | `Filtrar matriz` antes del bucle itera solo lo necesario | [use-data-operations](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/use-data-operations) |
| **PA-PERF-08** (MEDIA) | Listado sin paginación ni tope (`$top`/Top Count) | Solo llega la primera página y el resto se pierde EN SILENCIO | [work-with-relevant-data](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/work-with-relevant-data) |
| **PA-PERF-09** (MEDIA) | Aprobación/webhook sin timeout (`limit.timeout`) | Espera hasta 30 días y muere sin avisar; definir P7D + camino de escalamiento | [asychronous-flow-pattern](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/asychronous-flow-pattern) |
| **PA-PERF-10** (MEDIA) | `Do until` sin count/timeout sanos | Un bug se vuelve bucle de horas que consume la cuota | [limits-and-config](https://learn.microsoft.com/power-automate/limits-and-config) |
| **PA-PERF-11** (BAJA) | `Delay` dentro de un bucle | Multiplica la duración; riesgo del límite de 30 días | [limits-and-config](https://learn.microsoft.com/power-automate/limits-and-config) |
| **PA-PERF-12** (BAJA) | Bucle sobre la salida del trigger sin *Split On* | Split On crea una corrida por elemento: más simple y paralelo | [limits-and-config](https://learn.microsoft.com/power-automate/limits-and-config) |

## Concurrencia

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-CONC-01** (ALTA) | Bucle con concurrencia >1 que escribe variables | Las iteraciones se pisan entre sí: **condición de carrera**, resultado impredecible | [Power CAT Code Review](https://github.com/microsoft/Power-CAT-Tools/blob/main/CODE_REVIEW.md) |

## IA y agent flows (ver `ia-en-flujos.md` para el contexto completo)

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-IA-01** (MEDIA) | Acción de IA (Run a prompt / AI Builder) sin validación visible (Parse JSON, condiciones, aprobación) | La IA es probabilística: valida la salida y pon humano en el circuito para decisiones con impacto | [human review](https://learn.microsoft.com/ai-builder/azure-openai-human-review) |
| **PA-IA-02** (ALTA) | Acción de IA dentro de un bucle | Cada iteración cobra créditos; al agotar la cuota, TODA la IA del entorno falla | [licensing](https://learn.microsoft.com/ai-builder/administer-licensing) |
| **PA-IA-03** (INFO) | Presencia de acciones de IA | Aviso de consumo de créditos + fin de los créditos incluidos en nov-2026 | [endofaibcredits](https://learn.microsoft.com/ai-builder/endofaibcredits) |
| **PA-AGT-01** (ALTA) | Agent flow sin 'Respond to the agent' o con salidas distintas por rama | El agente que lo llame recibirá error 3000 / timeout | [flow-modify-use-with-agent](https://learn.microsoft.com/microsoft-copilot-studio/flow-modify-use-with-agent) |
| **PA-AGT-02** (MEDIA) | Trigger de agente con parámetros genéricos (`text_1`…) | El orquestador elige y llama la herramienta leyendo nombres/descripciones | [flow-agent](https://learn.microsoft.com/microsoft-copilot-studio/flow-agent) |

## Fechas y zonas horarias

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-DATE-01** (MEDIA) | Zona horaria a mano con `addHours(utcNow(),-N)` | *Convertir zona horaria* maneja el horario de verano solo | [convert-time-zone](https://learn.microsoft.com/power-automate/convert-time-zone) |

## Triggers

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-TRG-01** (BAJA) | Trigger automático sin *condiciones de activación* | Evita ejecuciones innecesarias y bucles | [optimize-triggers](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/optimize-power-automate-triggers) |
| **PA-TRG-02** (BAJA) | Concurrencia configurada en el trigger | Es **irreversible** y puede reordenar corridas; verificar que sea intencional | ídem |
| **PA-TRG-03** (ALTA) | El flujo escribe en la misma tabla/lista que lo dispara (sin trigger conditions) | **Bucle infinito**: cada corrida re-dispara el flujo y quema la cuota | [avoid-anti-patterns](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/avoid-anti-patterns) |
| **PA-TRG-04** (MEDIA) | Trigger Dataverse de modificación sin `filteringattributes` | Se dispara con CUALQUIER cambio de la fila | [optimize-triggers](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/optimize-power-automate-triggers) |

## Variables

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-VAR-01** (BAJA) | Variable inicializada que nunca se usa | Acción muerta: ruido y tiempo | [Power CAT Code Review](https://github.com/microsoft/Power-CAT-Tools/blob/main/CODE_REVIEW.md) |
| **PA-VAR-02** (BAJA) | Variable que nunca se reasigna | Es una constante: `Compose` es más barato y claro | [use-data-operations](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/use-data-operations) |

## Tamaño y organización

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-SIZE-01** (BAJA) | Más de 50 acciones | Dividir en flujos hijos (misma solución) | [create-reusable-code](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/create-reusable-code) |
| **PA-SIZE-02** (BAJA) | Más de 10 acciones sin ningún Scope | Los Scopes hacen el flujo legible por capítulos | [create-scopes](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/create-scopes) |

## Configuración portable

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-CFG-01** (BAJA) | URLs de sitio, correos y GUIDs escritos a mano | Environment Variables permiten mover el flujo entre entornos sin editarlo | [keep-flow-configuration-generic](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/keep-flow-configuration-generic) |

## Legibilidad y mantenimiento

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-NAME-01** (BAJA) | Acciones con nombre genérico | Nombres descriptivos = flujo legible | [naming-conventions](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/use-consistent-naming-conventions) |
| **PA-DOC-01** (BAJA) | Ausencia de *Notes* | Los comentarios del flujo explican el "por qué" | [peek-code-add-notes](https://learn.microsoft.com/power-automate/guidance/coding-guidelines/use-peekcode-addnotes) |
| **PA-DOC-02** (BAJA) | Flujo sin descripción | Clave para mantenimiento y para que Copilot/agentes entiendan el flujo | [Power CAT](https://github.com/microsoft/Power-CAT-Tools/blob/main/CODE_REVIEW.md) |

## Informativas (peso 0, no bajan puntuación)

| Código | Qué revisa | Por qué importa | Fuente |
|---|---|---|---|
| **PA-LIC-01** (INFO) | Conectores premium (HTTP, Dataverse, SQL…) | Requieren licencia Premium/proceso; solo aviso | [licensing types](https://learn.microsoft.com/power-platform/admin/power-automate-licensing/types) |

---

## Convención de nomenclatura recomendada (para el modo Copiloto y los arreglos)

Basada en Microsoft Learn + Matthew Devaney + Forward Forever:

- **Flujo:** `[Área] - Verbo + resultado + (disparador)`. Ej: *"Legal - Alerta vencimiento de contratos (Programado)"*.
- **Acciones:** nombre descriptivo de lo que hacen. Ej: *"Listar contratos vigentes"*, no *"Get items"*.
- **Variables:** prefijo + camelCase. Ej: `varDiasRestantes`, `varContratos`.
- **Scopes de error:** `Try`, `Catch`, `Finally`.
- Documentar la convención y comentar con *Notes* las decisiones no obvias.

## Verificación del auditor

Tras cualquier cambio en `scripts/auditar_flujo.py`:

```bash
python evals/verificar_auditor.py
```

Corre los 4 flujos de `evals/flujos/` (3 con fallas deliberadas + 1 limpio) y exige
coincidencia EXACTA de códigos detectados — sin falsos positivos ni regresiones.

## Fuentes maestras (para mantenerse al día)

- Índice oficial: https://learn.microsoft.com/power-automate/guidance/coding-guidelines/
- Well-Architected: https://learn.microsoft.com/power-platform/well-architected/
- Power CAT Tools (revisión oficial automatizada): https://github.com/microsoft/Power-CAT-Tools
- Matthew Devaney – Coding Standards: https://www.matthewdevaney.com/power-automate-coding-standards-for-cloud-flows/
- Forward Forever – Naming: https://forwardforever.com/naming-convention-for-power-automate/
- Procedimiento de actualización permanente: ver `reglas-candidatas.md` (final).
