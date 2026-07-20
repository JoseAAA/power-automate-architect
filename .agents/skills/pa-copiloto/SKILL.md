---
name: pa-copiloto
allowed-tools: Bash(python *)
description: >
  USAR cuando el usuario quiere un flujo NUEVO y no tiene definición: "crea un
  flujo que...", "quiero automatizar X", "hazme un flujo", "necesito que cuando
  pase A se haga B", "¿cómo empiezo con Power Automate?". NO usar para modificar
  flujos existentes (pa-conectado) ni para auditar (pa-auditoria / pa-flujos).
---

# Copiloto — de la idea al flujo funcionando, fácil

Objetivo: que CUALQUIER persona cree un flujo bien hecho **sin saber qué es un
JSON**. Propón, no interrogues: máximo 2-3 preguntas y siempre con opciones.

## Paso 1 — Entender (máx. 2-3 preguntas, con opciones)
Falta algo, pregunta SOLO lo esencial: ¿cuándo corre? (llega un item / horario /
lo disparo yo) · ¿de dónde salen los datos? · ¿qué hace al final? (avisar /
aprobar / guardar). Si el usuario ya lo dijo, NO re-preguntes.

## Paso 2 — Elegir plantilla base (todas auditan 100/100)

| Si el usuario quiere | Plantilla |
|---|---|
| Revisar algo cada día/semana y avisar | `plantillas/alerta-programada.json` |
| Que alguien apruebe/rechace y avisar el resultado | `plantillas/aprobacion.json` |
| Clasificar/extraer texto con IA y actuar | `plantillas/ia-clasificar.json` (avisar: consume créditos de IA) |
| Otra cosa | La más parecida; ajusta triggers/acciones manteniendo Try/Catch |

Rutas: `skills/pa-copiloto/plantillas/`.

## Paso 3 — Personalizar y auditar
1. Copia la plantilla a un archivo de trabajo y adapta: nombre del flujo
   `[Área] - Verbo + resultado (Disparador)`, textos en español, fuentes de
   datos reales del usuario. Mantén los `@parameters('X (demo_Y)')` como
   variables de entorno y explícale que se configuran al importar.
2. **Nombra CADA acción de forma descriptiva en español** (PA-NAME-01): nunca
   dejes "Compose", "Condition_2", "Apply to each" genéricos — usa "Listar
   contratos por vencer", "¿Faltan 30 días?", etc. Un flujo se lee por sus
   nombres de pasos.
3. Audita hasta 100: `python "scripts/auditar_flujo.py" trabajo.json --json`

## Paso 4 — Crear (con confirmación)
Muestra el plan en simple (cuándo corre → qué hace → a quién avisa) y con el OK
del usuario:
```bash
python "scripts/pa_api.py" crear --archivo trabajo.json --nombre "..." --si
```
Se crea en **formato moderno** (flujo de solución + connection references): abre
en el diseñador nuevo y cumple PA-SEC-02. El plugin enlaza solo las conexiones
que el usuario ya tenga; las que falten se autorizan una vez (ver Paso 5). Sin
sesión: primero `login`; sin `--si` muestra la simulación — enséñala.
(Solo si el usuario lo pide: `--clasico` crea sin solución, diseñador antiguo.)

## Paso 5 — Ponerlo a andar (manos del usuario)
El flujo nace APAGADO. El comando te dice qué conexiones quedaron **sin enlazar**
(las que el usuario no tenía). Dile: 1) abre el flujo en make.powerautomate.com,
autoriza ESAS connection references (una vez cada una), 2) vuelve y dime
"enciéndelo" (`encender <ID> --si`), 3) valídalo con `corridas <ID>`. Si no faltó
ninguna, salta directo a encenderlo.

## Reglas
- Nunca entregues un flujo que no audite 🟢 (≥90); ideal 100.
- No inventes operationId/apiId: usa los de las plantillas o de flujos reales.
- Acciones de IA solo si aportan (ver `references/ia-en-flujos.md`):
  lógica determinista se hace con condiciones, no con prompts.
