---
name: pa-auditoria
allowed-tools: Bash(python *)
description: >
  Audita un flujo de Power Automate (cloud flow) contra las mejores practicas.
  USAR cuando el usuario sube o apunta a un flujo exportado (.zip de "exportar
  como paquete", una carpeta del paquete, o un definition.json / clientdata) y
  pide "audita mi flujo", "revisa este flujo", "esta bien hecho?", "que puedo
  mejorar", "es eficiente?", "sigue las buenas practicas?". NO usar para Power
  Apps, Power BI, Logic Apps puras, ni para flujos del tenant sin exportar
  (eso es pa-flujos).
---

# Auditoria de un flujo de Power Automate

Objetivo: que CUALQUIER persona (experta o no) entienda en 30 segundos que tan
bien esta su flujo y exactamente que hacer para mejorarlo. Da soluciones, no
preguntas.

## Regla de oro (facilidad de uso)
- **No preguntes nada.** Si tienes el archivo, audita y entrega el informe.
- Habla primero en **lenguaje llano**; el detalle tecnico va despues.
- Cada hallazgo lleva su **arreglo concreto** (el script ya lo trae). No dejes al
  usuario con "esta mal" sin decirle como se arregla.

## Procedimiento

1. **Ubica el flujo.** El usuario te pasa una ruta a: un `.zip`, una carpeta del
   paquete, o un `definition.json`. Si subio solo el `.zip`, usalo tal cual (el
   script lo abre sin descomprimir).

2. **Ejecuta el analisis determinista** (cero tokens, todo el trabajo lo hace el script):
   ```
   python "${CLAUDE_PLUGIN_ROOT}/scripts/auditar_flujo.py" "<ruta al .zip / carpeta / definition.json>"
   ```
   Devuelve: puntuacion 0-100, veredicto, y los hallazgos `[ALTA]/[MEDIA]/[BAJA]`
   con su arreglo y la fuente oficial.

3. **Presenta el resultado AL PUNTO** (el usuario debe poder leerlo entero y
   verificarlo). Markdown, en este orden y sin relleno:
   - **Una frase**: puntuación con semáforo (🟢 ≥90 · 🟡 75-89 · 🟠 50-74 · 🔴 <50)
     + lo más urgente. Nada de preámbulos ("he analizado tu flujo y…").
   - **Tabla de hallazgos**, una LÍNEA por hallazgo, ordenada por severidad:
     *Código · Severidad · Qué pasa (simple) · Arreglo*. Deja el código `PA-XXX-NN`
     visible (sirve para rastrearlo), pero **resume**: no copies la descripción
     larga del catálogo ni pegues la salida cruda del script.
   - **Lo bueno:** 1-2 cosas que el flujo ya hace bien (una línea).
   - Cierre con UNA oferta de acción concreta (no una batería de preguntas).
   - El "porqué" de una regla y su fuente: **solo si el usuario los pide**.
   - Cargas condicionales (no cargues todo de una vez):

     | Lee | Solo cuando |
     |---|---|
     | `${CLAUDE_PLUGIN_ROOT}/references/buenas-practicas.md` — con grep del codigo `PA-XXX-NN`, nunca entero | expliques el porque/contexto de una regla concreta |
     | `${CLAUDE_PLUGIN_ROOT}/references/ia-en-flujos.md` | el reporte traiga hallazgos PA-IA-xx / PA-AGT-xx |

4. **Si el usuario lo pide**, guia el arreglo paso a paso (clic a clic para
   no-expertos; expresion/JSON listo para experto). No edites el flujo en su
   tenant: tu salida son instrucciones o el JSON corregido para que lo importe.

## Notas
- El script es 100% offline y no envia datos a ningun servicio. Privado por diseno.
- Si el script no encuentra una definicion valida, pide el archivo correcto
  (el `.zip` de "Exportar > Paquete (.zip)" o el `definition.json`).
- El catalogo de reglas y sus fuentes se mantiene en
  `${CLAUDE_PLUGIN_ROOT}/references/buenas-practicas.md` (lleva fecha y enlaces a
  Microsoft Learn; refrescar bajo demanda, no en cada ejecucion).
