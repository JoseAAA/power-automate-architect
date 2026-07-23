---
name: pa-copiloto
allowed-tools: Bash(python *)
description: >
  USAR cuando el usuario quiere un flujo NUEVO y no tiene definición: "crea un
  flujo que...", "quiero automatizar X", "hazme un flujo", "necesito que cuando
  pase A se haga B", "¿cómo empiezo con Power Automate?". NO usar para modificar
  flujos existentes (pa-conectado) ni para auditar (pa-auditoria / pa-flujos).
---

# Copiloto — de la idea al flujo funcionando

Objetivo: que CUALQUIER persona cree un flujo bien hecho **sin saber qué es un
JSON**. Hay DOS caminos según la complejidad — elige al entrar:

- **Rápido** (flujo simple y claro: 1 disparador, 1-2 acciones, encaja en una
  plantilla): sigue los Pasos 1-5 tal cual. Máximo 2-3 preguntas.
- **Guiado / plan-primero** (flujo NO trivial: varias fuentes, extracción de
  datos, decisiones de negocio, o el usuario quiere "armarlo juntos e iterar"):
  usa el **Modo plan-primero** de abajo ANTES de construir. Ej: ingesta de
  facturas, integraciones multi-sistema, algo con IA/documentos.

Ante la duda o si el usuario dice "vamos armándolo/iterando", usa plan-primero.

---
# Modo plan-primero (colaborativo e iterativo)

Patrón: **descubrir → plan escrito → iterar hasta aprobar → construir**. El plan
es el contrato (como una propuesta de OpenSpec): nada se construye hasta que el
usuario diga "apruébalo".

### P1 — Descubrir (preguntas que importan, no interrogatorio)
Haz las preguntas necesarias para entender de verdad (disparador, fuentes,
formato de los datos, transformaciones, destino, quién valida, volumen, manejo de
errores). Agrupa; ofrece opciones. Es correcto hacer MÁS de 3 preguntas aquí si
el flujo lo amerita — pero explica por qué cada una importa.

### P2 — Investigar y presentar TODAS las opciones (gratis Y premium)
Si algo no es obvio (¿qué conector extrae de un PDF? ¿el XML ya trae todo?),
investígalo antes de prometerlo. No inventes conectores/acciones. Consulta
`${CLAUDE_PLUGIN_ROOT}/references/` (ia-en-flujos, api-conexion, buenas-practicas).

**NO te limites a conectores gratis/estándar ni asumas una cuenta free.** Para
cada decisión con alternativas, presenta el **menú completo** con su trade-off y
deja que el usuario elija:
- opción **estándar/gratis** (si existe) — ej. leer XML con `xpath()`, condiciones;
- opción **premium** — ej. acción `HTTP` para pegarle a una API externa (OpenAI,
  el ERP, etc.), AI Builder para extraer de PDF/imágenes, conectores premium
  (Encodian, SQL, Dataverse), custom connector;
- indica de cada una: qué necesita (licencia premium por usuario/proceso,
  créditos de IA, custom connector) y cuándo conviene.

El objetivo es **construir CON el usuario informándole las opciones**, no elegir
por él la más barata. Si sigue sin estar claro, ponlo como pregunta abierta.

### P3 — Escribir el plan (artefacto en disco)
Copia `${CLAUDE_PLUGIN_ROOT}/skills/pa-copiloto/plantillas/_plan-de-flujo.md` a
`~/.power-automate-architect/planes/<slug>.md` y complétalo con lo que sabes.
Muéstraselo al usuario en lenguaje llano (objetivo → disparador → pasos → validación
→ preguntas abiertas). `estado: BORRADOR`.

### P4 — Iterar
Ajusta el plan con el feedback del usuario, ronda por ronda, hasta que esté de
acuerdo. Resuelve las "preguntas abiertas". Actualiza el archivo cada ronda (así
sobrevive a compactación de contexto). No pases a construir con preguntas abiertas.

### P5 — Aprobar y construir
Cuando el usuario apruebe explícitamente, marca `estado: APROBADO` en el plan y
recién ahí genera la definición y sigue los **Pasos 2-5** de abajo (plantilla o
construcción a medida → nombres descriptivos → auditar 100 → crear moderno →
poner a andar). Mantén el plan como registro.

---
# Camino rápido (flujos simples)

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

Rutas: `${CLAUDE_PLUGIN_ROOT}/skills/pa-copiloto/plantillas/`.

## Paso 3 — Personalizar y auditar
1. Copia la plantilla a un archivo de trabajo y adapta: nombre del flujo
   `[Área] - Verbo + resultado (Disparador)`, textos en español, y **REEMPLAZA
   los marcadores `@parameters('X (demo_Y)')` por los datos REALES del usuario**
   (URL del sitio de SharePoint, nombre de la lista, correos…). Pregúntaselos si
   no los tienes. ⚠️ Si dejas los `@parameters(...)` de demo, el flujo abre pero
   NO corre: la acción falla con *"missing required property 'dataset'"* porque
   apunta a un sitio/lista que no existe. (Lo ideal a futuro son Environment
   Variables reales; para un flujo que funcione ya, valores reales directos bastan.)
2. **Nombra CADA acción de forma descriptiva en español** (PA-NAME-01): nunca
   dejes "Compose", "Condition_2", "Apply to each" genéricos — usa "Listar
   productos con stock bajo", "¿Stock < 10?", etc. Un flujo se lee por sus
   nombres de pasos.
3. Audita hasta 100: `python "${CLAUDE_PLUGIN_ROOT}/scripts/auditar_flujo.py" trabajo.json --json`

## Paso 4 — Crear (con confirmación)
Muestra el plan en simple (cuándo corre → qué hace → a quién avisa) y con el OK
del usuario:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/pa_api.py" crear --archivo trabajo.json --nombre "..." --si
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

## Conexiones — NO te trabes con esto
El flujo usa **connection references por nombre de conector** (ej.
`shared_sharepointonline`); **NO necesitas los GUID de las conexiones reales** para
crearlo. Por defecto `crear` deja las conexiones **SIN enlazar** y el flujo nace
apagado: el usuario las conecta en el portal (un clic por conector) al abrirlo.
- **No interrogues** por conexiones ni iteres buscándolas. Pregunta como MUCHO una
  vez; si el usuario no las da, sigue igual y déjalas en blanco.
- Al terminar, dile qué conectores debe enlazar (los que devuelve
  `conexiones_sin_enlazar`) y que eso se hace una sola vez en make.powerautomate.com.
- Solo si el usuario lo pide, `crear --enlazar` intenta pre-enlazar a conexiones
  que ya tenga (silencioso, sin preguntar).

## Reglas
- Nunca entregues un flujo que no audite 🟢 (≥90); ideal 100.
- No inventes operationId/apiId: usa los de las plantillas o de flujos reales.
- **Presenta todas las opciones (estándar y premium) con su costo/licencia; el
  usuario decide.** No descartes premium (HTTP a una API, AI Builder, conectores
  premium) por asumir cuenta free — solo infórmale el trade-off.
- IA/premium cuando aporten (ver `${CLAUDE_PLUGIN_ROOT}/references/ia-en-flujos.md`):
  para lógica determinista, condiciones antes que prompts — pero si el usuario
  quiere IA/una API externa, es su decisión informada.
