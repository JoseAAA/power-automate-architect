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
