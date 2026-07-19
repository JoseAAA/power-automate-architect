# Contrato agente ↔ CLI (salida --json)

> `desde: v0.6.0` · Patrón adoptado de OpenSpec (`docs/agent-contract.md`).
> Los CLIs del proyecto son la fuente de verdad; cualquier agente (Claude, Codex,
> Gemini, OpenCode, scripts) parsea el JSON en vez de raspar texto humano.

## Convenciones

1. **Un documento JSON por invocación** en stdout cuando se pasa `--json`; nada
   más se imprime en stdout en ese modo (los errores también salen como JSON).
2. Cada payload lleva **`contrato`**: `"pa-architect/<comando>@<versión>"` —
   si la forma cambia de manera incompatible, sube la versión.
3. Claves opcionales **se omiten**, no van en `null`.
4. Cada hallazgo/error incluye su **arreglo accionable** (`arreglo` / mensajes
   de error con el comando a correr) — el agente siempre sabe qué hacer después.
5. Los **exit codes no cambian** entre modo humano y JSON.

## Comandos con `--json`

| Comando | Contrato | Exit codes |
|---|---|---|
| `auditar_flujo.py <ruta> --json` | `pa-architect/auditoria@1`: flujo, puntuacion, veredicto, hallazgos[{codigo, severidad, titulo, ocurrencias, donde[], arreglo, fuente}], totales | 0 sin ALTA · 1 con ALTA · 2 entrada inválida |
| `pa_api.py flujos --json` | `pa-architect/flujos@1`: entorno, flujos[{id, nombre, estado}] (estado `Suspendido` = DLP) | 0 · 3 error (JSON `pa-architect/error@1`) |
| `pa_api.py corridas <id> --json` | `pa-architect/corridas@1`: corridas[{estado, inicio, fin, error}] | ídem |

Los comandos de escritura (`actualizar`/`crear`/`encender`/`apagar`) son
deliberadamente conversacionales (dry-run + `--si`): el gate determinista es la
auditoría previa (exit 1 bloquea) y la aprobación es del humano en el chat.

## Verificación

`evals/verificar_auditor.py` exige que el contrato JSON y el reporte humano
devuelvan exactamente los mismos códigos y exit codes (no pueden divergir).
