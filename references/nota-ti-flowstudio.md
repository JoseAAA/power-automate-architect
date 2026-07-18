# Nota para TI/Seguridad — Conexión de FlowStudio MCP (piloto)

> Texto listo para enviar a tu área de TI si la conexión pide aprobación de administrador.

## ¿Qué es y para qué?
Estamos evaluando **FlowStudio MCP** para que un asistente de IA (Claude Code)
pueda **desplegar, ejecutar y validar flujos de Power Automate** durante el
desarrollo, evitando reconstruirlos a mano en el portal. Es un **piloto** de
prueba (plan gratuito, 21 días).

## Modelo de acceso y datos (según el proveedor)
- **Acceso delegado** de Microsoft: el servicio actúa **con los mismos permisos
  que el usuario** que inicia sesión (no permisos de aplicación, no secretos
  almacenados). Pide dos alcances: *gestión de flujos* y *lectura de actividad*.
- **No almacena** los payloads de los flujos ni los secretos de los conectores.
- Hospedado en **Azure**, TLS 1.2+, cifrado en reposo, aislamiento por tenant,
  **permisos revocables** en cualquier momento desde Entra ID.
- La autenticación al MCP usa una **API key (JWT) revocable**.

## La pregunta clave: ¿se necesita aprobación de administrador?
Depende de la política de **consentimiento de usuario** del tenant de la organización:
- Si la organización **permite** el consentimiento de usuario a apps de terceros → el usuario
  puede autorizarlo solo, sin TI.
- Si lo **bloquea** (común en entornos con datos sensibles) → al iniciar
  sesión aparecerá **"Se necesita aprobación del administrador"** y TI deberá dar
  *consentimiento de administrador* a la app, o aprobar la solicitud.

## Cómo saberlo en 1 minuto (sin comprometer nada)
Iniciar sesión en https://mcp.flowstudio.app con la cuenta de trabajo. El propio
inicio de sesión lo revela:
- **Entra al dashboard** → el usuario está autorizado (no hace falta TI para el piloto).
- **Aparece "Necesita aprobación del administrador"** → enviar esta nota a TI.

El intento de inicio de sesión **no concede nada por sí solo**: solo muestra si se
puede autoconsentir. El consentimiento se puede **revocar** después en
*Entra ID → Aplicaciones empresariales*.

## Recomendación
Para un **piloto personal** de un solo usuario, el riesgo es bajo (delegado, sin
almacenamiento de payloads, revocable). Para un **despliegue a todo el equipo o
producción**, conviene el visto bueno formal de TI y, si se quiere cero terceros,
evaluar la alternativa **open-source self-hosted** o la **vía oficial pac CLI**.

Fuentes: https://flowstudio.app · https://mcp.flowstudio.app
