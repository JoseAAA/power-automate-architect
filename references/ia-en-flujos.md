# IA en Power Automate (AI capabilities) — qué son, costos y cuándo usarlas

> `investigado: 2026-07-18` · Cubre el grupo "AI capabilities" del diseñador:
> Run a prompt, Respond to the agent (agent flows), Run a generative action
> (preview) y las acciones de AI Builder. Reglas derivadas: PA-IA-xx / PA-AGT-xx.

## Qué es cada cosa

| Capacidad | Qué hace | Estado |
|---|---|---|
| **Run a prompt** | Ejecuta un prompt personalizado de AI Builder (instrucciones + entradas + conocimiento opcional) sobre Azure OpenAI y devuelve texto o **JSON estructurado**. Modelos 2026: GPT-4.1 mini (básico, default), GPT-4.1/GPT-5 chat (estándar), GPT-5 reasoning (premium), y modelos externos Claude (Anthropic, **hospedado fuera de Microsoft**) y Grok (experimental, no recomendado para producción). Se puede "aterrizar" con tablas Dataverse (RAG) | GA |
| **Respond to the agent** | Convierte el flujo en **herramienta de un agente** de Copilot Studio: trigger "When an agent calls the flow" + acción de respuesta. Requisitos duros: misma solución/entorno que el agente, responder en **<100 s**, respuesta asíncrona **apagada**, mismas salidas en todas las ramas | GA (mar-2025) |
| **Run a generative action** | La IA decide en runtime qué conectores/acciones ejecutar según una intención. Solo ~9 conectores, entradas de texto ≤2.500 caracteres, DLP parcial. Microsoft: **"no para producción"** | Preview |
| **Acciones AI Builder** | Process invoices/receipts/documents/ID, Extract entities, Classify, Generate key phrases, OCR, Describe images (preview), traducción, sentimiento | GA/preview según acción |

Novedades relacionadas: agent flows facturan por Copilot Studio (convertir un flujo a agent flow es **irreversible**); Copilot en el diseñador y "describe it to design it"; un flujo también puede **invocar** a un agente (conector Microsoft Copilot Studio).

## Costos y restricciones (lo que hay que saber ANTES de usarlas)

- **Todo consume créditos.** Tarifas clave (Copilot Credits, 1 crédito = $0.01 PAYG):
  prompt básico 0.1/1K tokens · estándar 1.5 · premium 10 · factura/recibo/ID 8
  por página · OCR 0.1/página · clasificación/extracción 1.5/1K caracteres.
  Se cobran tokens de entrada (incluido el system prompt) y de salida (incluido
  el razonamiento). Fuente: https://learn.microsoft.com/ai-builder/administer-licensing
- **⚠️ Cambio de licenciamiento en curso:** desde nov-2025 no se venden créditos
  AI Builder a clientes nuevos (todo va a Copilot Credits) y en **nov-2026 se
  eliminan los créditos incluidos** (los 5.000/mes del Power Automate Premium
  desaparecen): los flujos con IA pasarán a consumir créditos pagados o fallarán
  con `QuotaExceeded`. Fuente: https://learn.microsoft.com/ai-builder/endofaibcredits
- Los créditos **no se acumulan** (reset el día 1); al agotarse, las acciones IA
  fallan (`EntitlementNotAvailable`/`QuotaExceeded`) y en agent flows se
  **bloquean corridas nuevas** si no hay pay-as-you-go.
- Los prompts **consumen créditos incluso en pruebas** del panel (solo el prompt
  builder es gratis); "Run a prompt" tiene timeout ~2 minutos.
- **Privacidad:** los datos NO entrenan los modelos; inferencia en Azure OpenAI
  del región del entorno. EXCEPCIÓN: modelos Claude/Grok se hospedan fuera de
  Microsoft (términos de Anthropic/xAI) — evitar con datos sensibles.
  Fuente: https://learn.microsoft.com/ai-builder/faqs-prompts
- **DLP sutil:** "Run a prompt"/Predict viajan por el conector de **Dataverse**
  (`shared_commondataserviceforapps`): la DLP clásica no puede bloquear IA sin
  bloquear Dataverse. Controles reales: PPAC (bloquear consumo no asignado,
  apagar modelos preview, topes por agente).
- Disponibilidad **por región** (traducción solo Europa/EE.UU.; GCC sin
  imágenes/documentos en prompts; sin DoD).

## Cuándo SÍ ayudan mucho / cuándo NO

**SÍ (casos fuertes):**
1. **Procesar documentos a volumen** (facturas, recibos, contratos): reemplaza
   digitación manual; ~$0.08/página.
2. **Clasificar/triaje** de correos, tickets, solicitudes en texto libre.
3. **Resumir + aprobar**: prompt que resume → aprobación humana → acción
   (patrón documentado por Microsoft).
4. **Extraer datos de texto no estructurado** hacia columnas de Dataverse/listas.
5. **Agent flows**: dar a un agente conversacional herramientas deterministas.

**NO (evitar):**
- Lógica determinista (cálculos, ruteo por campos conocidos): una Condition es
  gratis y nunca alucina. Microsoft lista cálculos financieros/científicos como
  **uso no soportado** de prompts.
- IA **dentro de un Apply to each** de miles de ítems: quema créditos y puede
  bloquear la IA de todo el entorno.
- Datos regulados con modelos preview o externos (Claude/Grok).
- Cualquier cosa de producción sobre features **preview** (generative actions).

## Mejores prácticas oficiales (base de las reglas PA-IA/PA-AGT)

1. La salida de IA es **probabilística**: validarla (JSON estructurado + Parse
   JSON + condiciones) y poner **humano en el circuito** para decisiones con
   impacto (prompt → aprobación → acción). https://learn.microsoft.com/ai-builder/azure-openai-human-review
2. **Temperatura 0** para automatización que exige exactitud.
3. Manejar el error de las acciones IA (cuota, moderación de contenido, timeout).
4. En agent flows: **describir bien** la herramienta, el esquema del trigger y
   las salidas (el orquestador decide con eso); responder <100 s; mismas salidas
   en cada rama. https://learn.microsoft.com/microsoft-copilot-studio/flow-agent
5. Transparencia con el usuario final: avisar que el contenido lo generó IA.
6. Guía Well-Architected "Intelligent application workload":
   https://learn.microsoft.com/power-platform/well-architected/intelligent-application/

## Firmas JSON (para el auditor)

- **Acción IA (Run a prompt / AI Builder / Predict):** `type: OpenApiConnection`
  con `host.apiId` = `.../shared_commondataserviceforapps` y `operationId` =
  `aibuilderpredict` (diseñador moderno) o `Predict` (genérica). NO existe un
  conector `shared_aibuilder`. Confianza alta (JSON real confirmado en foros).
- **Trigger de agente:** `type: "Request"`, `kind: "Skills"` (nombre heredado de
  PVA; no se observó kind "Agent").
- **Respond to the agent:** acción `type: "Response"` en un flujo con trigger
  Skills (el `kind` exacto de la respuesta no está 100% confirmado público).
- **Run a generative action:** firma desconocida (preview, sin ejemplos
  públicos) — pendiente de capturar un export real.
