---
name: pa-conectado
description: >
  Modo conectado (vía 100% Microsoft, sin terceros): despliega y valida un flujo de
  Power Automate en el tenant usando `pac` CLI (Power Platform CLI) + tabla FlowRun.
  USAR cuando el usuario, tras auditar o crear un flujo, dice "súbelo", "despliégalo",
  "aplica la corrección al flujo real", "actívalo" o "valida que funciona". Cierra el
  ciclo corregir -> empaquetar -> importar -> activar -> validar sin reconstruir a
  mano en el portal. Requiere `pac` instalado y `pac auth create` hecho.
---

# Modo conectado — desplegar y validar con `pac` CLI (sin terceros)

Objetivo: que el usuario NO reconstruya el flujo a mano. Tomamos el `definition.json`
(corregido por el auditor o creado por el copiloto), lo empaquetamos en una solución,
lo importamos y lo activamos en el tenant, y validamos leyendo el historial de
ejecuciones — todo con la herramienta oficial de Microsoft, sin que ningún tercero
toque los datos.

## Requisitos (una sola vez)
1. **`pac` instalado.** Verifica con `pac` (muestra versión y comandos). Si falta:
   `winget install --id Microsoft.PowerAppsCLI -e`.
2. **Autenticado.** El usuario corre en SU terminal: `pac auth create` (login
   interactivo con su cuenta de trabajo) o `pac auth create --deviceCode`. Verifica con
   `pac auth who` y lista entornos con `pac org list` / `pac admin list`.
3. **El flujo debe estar en una SOLUCIÓN.** Los cloud flows solo se gestionan por
   código si están en la pestaña *Soluciones* (no en *Mis flujos*). Paso único en el
   portal: crear una solución (ej. "Dev-Legal") y *Agregar existente → Flujo en la nube*.

## Regla de oro de seguridad (tenant corporativo)
- **Confirma SIEMPRE antes de importar/activar** algo en el tenant.
- Trabaja sobre una **copia/solución de desarrollo**, NUNCA sobre producción, hasta validar.
- Sugiere versionar (commit) la solución desempaquetada antes de editar.

## El ciclo (round-trip por solución)
1. **Traer la solución con el flujo real:**
   `pac solution export --path ./sol.zip --name <NombreSolucion> --managed false`
   (o `pac solution clone --name <NombreSolucion>`). Luego
   `pac solution unpack --zipfile ./sol.zip --folder ./sol --packagetype Unmanaged`.
2. **Editar el flujo:** el JSON del flujo está en `./sol/Workflows/<...>.json`
   (contiene `definition` + `connectionReferences`). Aplica los arreglos del auditor
   (Try/Catch, Select en vez de Append-en-bucle, `$filter`, zona horaria, etc.).
   Apóyate en `${CLAUDE_PLUGIN_ROOT}/references/buenas-practicas.md`.
3. **Re-empaquetar:** `pac solution pack --zipfile ./sol-new.zip --folder ./sol --packagetype Unmanaged`.
4. **Importar y activar:** `pac solution import --path ./sol-new.zip --activate-flows --publish-changes`
   (usa `--settings-file` para mapear connection references / environment variables si aplica).
5. **Validar (tabla FlowRun, sin terceros):** consulta el historial de corridas en
   Dataverse para confirmar éxito/fallo. Vías: el conector/Web API de Dataverse sobre
   la tabla `flowrun` (Status = Succeeded/Failed, errormessage). Si el trigger es
   manual/HTTP, dispáralo; si es Recurrence, espera la ventana o reejecuta una corrida.
6. **Reportar en simple:** "Apliqué el arreglo, subí el flujo, lo activé y la última
   ejecución terminó en ÉXITO ✅" — o el error concreto + cómo se corrige.

## Notas de eficiencia y límites
- `pac` no tiene comando para *ejecutar* un flujo ni para leer `flowrun`; el disparo
  depende del tipo de trigger y la validación se hace por Dataverse (Web API o conector).
- La tabla `flowrun` tiene TTL ~28 días y es *eventually consistent*: si validas justo
  tras ejecutar, sondea con backoff (no en bucle cerrado).
- Para un flujo NUEVO desde cero (copiloto) sin solución previa, se puede generar la
  estructura de solución y empaquetarla; preferir partir de una solución real exportada
  para no errar el formato.
- Auth y tokens viven SOLO en la máquina del usuario (caché de `pac`); ningún servicio
  externo los almacena. Esa es la ventaja de seguridad de esta vía.
