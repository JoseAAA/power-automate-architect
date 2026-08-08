---
name: pa-conectado
allowed-tools: Bash(python *)
description: >
  USAR cuando el usuario pide cambiar un flujo EXISTENTE del tenant: "aplica el
  arreglo", "corrige mi flujo", "agrégale try/catch", "modifícalo para que...",
  "enciende/apaga el flujo", "súbelo", "restaura el respaldo". NO usar para
  crear flujos nuevos (pa-copiloto), listar/auditar (pa-flujos) ni flujos
  exportados a mano (pa-auditoria). Requiere sesión iniciada (pa_api.py login).
---

# Escritura conectada — modificar y crear flujos por lenguaje natural

Cierra el ciclo **auditar → corregir → subir → validar** sin reconstruir a mano.
El asistente edita el JSON; `pa_api.py` sube por la vía soportada (Dataverse;
maker API solo legacy — el script decide y lo dice).

## 🟡🔴 Un solo plan, un solo OK (no preguntes paso a paso)
Aquí SÍ hay plan porque se cambia algo real. Pero **uno solo, al inicio**:

1. **Investiga primero en silencio** (exportar el flujo, auditarlo, ver corridas):
   eso es lectura, no la anuncies ni pidas permiso.
2. **Presenta UN plan compacto** (≤8 líneas) y pide UNA aprobación:
   - *Qué haré* (en simple) · *Qué toco* (flujo/acciones) · *Riesgo* ·
     *Cómo se revierte* (respaldo automático) · *Preguntas* (agrupadas AQUÍ, si las hay).
   - Si una duda tiene un default sensato, **decide y dilo** en vez de preguntar.
3. **Con el OK, ejecuta TODO seguido** (editar → auditar → `--si` → validar) sin
   volver a preguntar. Solo te detienes si aparece algo que cambia el plan: di QUÉ
   cambió y re-pide una vez.
4. Cierra en 3-4 líneas: qué quedó, score antes→después, ruta del respaldo.

| Excusa para volver a preguntar | Realidad |
|---|---|
| "Quiero confirmar cada paso" | El OK del plan ya cubrió los pasos del plan |
| "Salió un detalle menor" | Si no cambia el resultado ni el riesgo, decide y sigue |
| "Es más seguro preguntar" | Preguntar de más agota al usuario; el `--si` y el respaldo ya son la red |

## Red de seguridad (integrada en el script — no la rodees)
1. **Respaldo automático** previo en `~/.power-automate-architect/respaldos/` →
   revertir = `actualizar <ID> --archivo <respaldo> --si`.
2. **Auditoría previa**: hallazgos ALTA bloquean la subida (`--forzar` solo si
   el usuario lo pide textualmente).
3. **Dry-run por defecto**: sin `--si` solo simula. El `--si` se agrega SOLO
   tras confirmación explícita del usuario en el chat.

| Excusa para saltarse la confirmación | Realidad |
|---|---|
| "El usuario dijo que es urgente" | Urgencia no es confirmación: muestra el dry-run y pide el OK |
| "Ya confirmó un cambio parecido" | Cada subida requiere su propio OK |
| "El cambio es trivial" | Lo trivial también rompe producción; dry-run igual |
| "La auditoría previa ya pasó" | La auditoría valida calidad, no intención: el OK es del usuario |

## Ledger (sobrevivir a compactación de contexto)
Al iniciar un ciclo de escritura crea `~/.power-automate-architect/sesiones/<flowid>-<fecha>.md`
con checkboxes: `[ ] descargado (ruta)` `[ ] editado (qué)` `[ ] auditado (score)`
`[ ] confirmado por usuario` `[ ] subido (via, respaldo)` `[ ] validado (corrida)`.
Actualízalo al completar CADA paso; si la conversación se compacta, retoma de ahí.

## Ciclo MODIFICAR — por .zip de solución (confiable, como un experto)
Se edita el **JSON REAL exportado** (que ya trae `$authentication`, connection
references, etc.), NO uno armado a mano. Por eso no falla.
1. Exporta el JSON real (paso 1):
   `python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" exportar-flujo <ID> --a flujo.json`
   (NO uses `flujo --guardar` para modificar: ese es el formato de la maker API y
   al reimportar falla; `exportar-flujo` da el JSON de solución correcto.)
2. Edita `flujo.json` dentro de `properties.definition` con el cambio pedido. NO
   inventes operationId/apiId: reutiliza los de la definición.
3. Audita hasta quedar sin ALTA: `auditar_flujo.py flujo.json --json`.
4. Muestra el resumen (qué cambia, score antes → después), pide confirmación, y con el OK:
   `python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" actualizar <ID> --archivo flujo.json --si`
   (hace export→editar→import de la solución, con respaldo del zip anterior.)
5. Valida con `corridas <ID>` y reporta en simple (+ ruta del respaldo).

### ⛔ Reglas de oro al MODIFICAR (no desconectar, no duplicar)
Un cambio de lógica NUNCA debe obligar al usuario a reconectar sus conexiones.
- **Edita SOLO lo que cambia** dentro de `properties.definition`. NO pegues un flujo
  entero rearmado a mano: parte del JSON exportado y toca solo la(s) acción(es) pedida(s).
- **NO reescribas `properties.connectionReferences`.** El comando `actualizar` ya
  preserva las connection references reales (los enlaces del usuario) aunque tu JSON
  las traiga distintas — pero igual: no las inventes ni las renombres. Reutiliza sus
  `connectionReferenceLogicalName` tal cual.
- **Es el MISMO flujo (mismo ID).** Modificar = actualizar ese flujo, NUNCA crear
  uno nuevo. Si `actualizar` falla por permisos, NO lo "resuelvas" creando un flujo
  nuevo con otro nombre (eso pierde las conexiones y duplica): repórtalo y ofrece
  el rol de personalizador o el `.zip` de actualización. Ver Permisos abajo.
- **Descripciones de acción ≤ 256 caracteres.** Power Automate rechaza el guardado
  con `ActionDescriptionTooLong` si una descripción pasa de 256. Sé conciso.
- **Excel Online (Business):** su `$select` NO admite columnas con espacios (ej.
  `Fecha Cumpleaños` → error OData). Si necesitas filtrar columnas, renombra la
  columna en Excel sin espacios primero; si no, trae todas (sin `$select`).
- **Ordenar un arreglo** es con la expresión `sort(coleccion, 'propiedad')` (o
  `reverse(sort(...))`); una acción **Select** (Data Operations) NO ordena.

⚠️ **Permisos:** la vía de solución (formato moderno + modificar por zip) requiere
que la cuenta tenga rol de **personalizador (System Customizer / Creador del
entorno)** en el entorno. Si sale error de permisos (403 / "does not have
ReadAccess"), NO caigas al clásico (está prohibido). Opciones: (1) pídele a tu
admin de Power Platform ese rol; (2) si el cambio se puede entregar como flujo
nuevo/copia corregida, la skill `pa-copiloto` puede generarte el `.zip` importable
(`crear ... --solo-zip`) para subirlo a mano — así hay entregable aunque el tenant
no te deje escribir por API.

## Encender / apagar un flujo
"enciéndelo" / "actívalo" → `pa_api.py encender <ID> --si`.
"apágalo" / "desactívalo" → `pa_api.py apagar <ID> --si`. Sin `--si` solo simula.

## Crear flujos nuevos
Eso es de la skill `pa-copiloto` (plantillas 100/100 + creación guiada); este
modo solo modifica, enciende/apaga y restaura respaldos.

## Cargas condicionales (no cargues todo de una vez)
| Lee | Solo cuando |
|---|---|
| `references/buenas-practicas.md` (grep del código `PA-XXX-NN`) | expliques el porqué de una regla concreta |
| `references/ia-en-flujos.md` | el flujo use acciones de IA / sea agent flow |
| `references/api-conexion.md` | falle la autenticación o quieras la vía Dataverse en detalle |

## Notas
- Flujo `Suspendido` tras subir = política DLP: explica qué conector chocó.
- Ambigüedad de nombre → verifica con `flujos` antes de tocar nada.
- pac CLI queda solo como ALM alternativo por soluciones.
