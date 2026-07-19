---
name: pa-conectado
allowed-tools: Bash(python *)
description: >
  USAR cuando el usuario pide cambiar el tenant: "aplica el arreglo", "corrige
  mi flujo", "agrégale try/catch", "crea un flujo que haga X", "modifícalo para
  que...", "enciende/apaga el flujo", "súbelo", "restaura el respaldo". NO usar
  para solo listar o auditar (eso es pa-flujos) ni para flujos exportados a mano
  (pa-auditoria). Requiere sesión iniciada (pa-flujos / pa_api.py login).
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

## Ciclo MODIFICAR ("agrégale manejo de errores a X")
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" flujo <ID> --guardar flujo.json
```
1. Edita `flujo.json` con el cambio pedido. NO inventes operationId/apiId:
   reutiliza los de la definición.
2. Audita local hasta quedar sin ALTA (con `--json` para leer códigos/score
   sin raspar texto): `python "${CLAUDE_PLUGIN_ROOT}/scripts/auditar_flujo.py" flujo.json --json`
3. Muestra al usuario el resumen (acciones que cambian, score antes → después)
   y pide confirmación. Con el OK:
   `python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" actualizar <ID> --archivo flujo.json --si`
4. Valida con `corridas <ID>` y reporta en simple (+ ruta del respaldo).

## Ciclo CREAR ("crea un flujo que avise cuando...")
1. Máximo 2-3 preguntas si faltan: disparador, fuente de datos, acción final.
2. Genera la definición partiendo de `${CLAUDE_PLUGIN_ROOT}/evals/flujos/flujo-limpio.json`
   (estructura 100/100); nombre `[Área] - Verbo + resultado (Disparador)`.
3. Audita hasta 🟢, muestra el plan, y con el OK:
   `python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" crear --archivo nuevo.json --nombre "..." --si`
4. Nace APAGADO: el usuario enlaza conexiones una vez en el portal (no se puede
   por API delegada) y luego `encender <ID> --si`.

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
