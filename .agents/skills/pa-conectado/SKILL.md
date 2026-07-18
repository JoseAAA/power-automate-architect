---
name: pa-conectado
description: >
  Modo conectado de ESCRITURA (vía 100% Microsoft, sin terceros): modifica, crea,
  enciende o apaga cloud flows del tenant por lenguaje natural, con respaldo
  automático y auditoría previa. USAR cuando el usuario dice "aplica el arreglo",
  "corrige mi flujo", "agrégale try/catch", "crea un flujo que haga X",
  "modifícalo para que...", "enciende/apaga el flujo", "súbelo al tenant".
  Requiere sesión iniciada (skill pa-flujos / pa_api.py login).
---

# Modo conectado (escritura) — modificar y crear flujos por lenguaje natural

Objetivo: cerrar el ciclo **auditar → corregir → subir → validar** sin que el
usuario reconstruya nada a mano en el portal. El asistente edita el JSON de la
definición; `pa_api.py` lo sube por la vía soportada.

## Red de seguridad (integrada en el script — no la saltes)
1. **Respaldo automático** del flujo actual antes de tocarlo
   (`~/.power-automate-architect/respaldos/<id>-<fecha>.json`) → siempre se puede
   volver atrás con `actualizar --archivo <respaldo> --si`.
2. **Auditoría previa obligatoria**: si la definición nueva tiene hallazgos ALTA,
   el script se niega a subirla (`--forzar` solo si el usuario lo pide explícito).
3. **Dry-run por defecto**: sin `--si` solo simula. El `--si` lo agregas SOLO
   después de que el usuario confirmó en el chat.
4. **Vía soportada primero**: Dataverse (tabla `workflow`) cuando el flujo vive
   ahí; maker API solo para flujos legacy (el script decide y te lo dice).

## Ciclo: MODIFICAR un flujo existente ("agrégale manejo de errores a X")

```bash
# 1. Descargar la definicion actual
python "scripts/pa_api.py" flujo <ID> --guardar flujo.json
```
2. **Editar `flujo.json`** aplicando el cambio pedido. Respeta el catálogo
   (`references/buenas-practicas.md`): nombres descriptivos,
   Try/Catch con Terminate(Failed), filtros en origen, notes. NO inventes
   operationId/apiId: reutiliza los que ya están en la definición.
3. **Auditar localmente** hasta que no queden ALTA:
   `python "scripts/auditar_flujo.py" flujo.json`
4. **Mostrar al usuario un resumen del cambio** (qué acciones se agregan/cambian,
   puntuación antes → después) y **pedir confirmación explícita**.
5. Subir (primero sin `--si` para el dry-run; con OK del usuario, con `--si`):
   ```bash
   python "scripts/pa_api.py" actualizar <ID> --archivo flujo.json --si
   ```
6. **Validar**: `corridas <ID>` tras la siguiente ejecución (o pedir al usuario
   que lo dispare) y reportar en simple: "Apliqué X, respaldo en Y, última
   corrida: ÉXITO ✅".

## Ciclo: CREAR un flujo nuevo ("crea un flujo que avise cuando...")

1. **2-3 preguntas máximo** (si faltan): disparador (¿cuándo corre?), fuente de
   datos, y acción final (¿a quién avisa / qué escribe?). No interrogues: propone.
2. **Genera la definición** cumpliendo el catálogo desde el inicio (Try/Catch,
   trigger conditions, filtros, nombres en español, description del flujo).
   Base útil: `evals/flujos/flujo-limpio.json` (estructura
   100/100). Para IA/agent flows revisa `references/ia-en-flujos.md`.
3. Audita local hasta 🟢, muestra el plan al usuario y con su OK:
   ```bash
   python "scripts/pa_api.py" crear --archivo nuevo.json --nombre "Área - Qué hace (Disparador)" --si
   ```
4. El flujo **nace APAGADO**. Si usa conectores, el usuario debe abrir el flujo
   una vez en el portal para **enlazar las conexiones** (eso no se puede hacer
   por API con login delegado); luego: `encender <ID> --si`.

## Encender / apagar

```bash
python "scripts/pa_api.py" encender <ID> --si
python "scripts/pa_api.py" apagar <ID> --si
```

## Reglas de oro
- **NUNCA subas nada sin confirmación explícita del usuario en el chat.** El
  dry-run (sin `--si`) es tu amigo: muéstralo primero.
- Trabaja sobre el flujo que el usuario nombró; verifica con `flujos` si hay
  ambigüedad (mismo displayName repetido).
- Si el flujo queda `Suspendido` tras subir = lo bloqueó una política DLP:
  explica cuál conector chocó y ofrece alternativas.
- Si algo sale mal: restaura con el respaldo
  (`actualizar <ID> --archivo <respaldo.json> --si`) y repórtalo tal cual.
- pac CLI queda solo como vía alternativa de ALM por soluciones (export/pack/import).
