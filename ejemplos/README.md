# Ejemplos de flujos (para entender el formato)

Esta carpeta SÍ se versiona (a diferencia de `flujos-locales/` y los `*.zip` de la
raíz, que se ignoran por privacidad). Sirve para estudiar y documentar el formato
real de los flujos: el paquete `.zip` de solución, sus `Workflows/*.json`, las
connection references y las versiones.

## ⚠️ Regla: solo ejemplos SANEADOS

Este repo es público. **Antes de poner un ejemplo aquí, quítale todo dato real:**
- RUC, correos, nombres de personas → usa ficticios (Contoso, `demo@ejemplo.com`).
- URLs de SharePoint del tenant, IDs de entorno, GUIDs de conexión reales.
- Cualquier contenido de negocio (montos, clientes, etc.).

Los exports REALES de tu empresa van en `flujos-locales/` (ignorada por git) o
como `*.zip` en la raíz (ignorados); ahí el auditor y el conector los leen sin
que salgan del equipo. Cuando quieras convertir uno en ejemplo, lo saneamos juntos.

## Qué guardar aquí
- `<caso>/` una carpeta por ejemplo, con el `.zip` de solución saneado y/o su
  contenido desempaquetado (`solution.xml`, `customizations.xml`, `Workflows/*.json`).
- Un `NOTAS.md` corto por ejemplo: qué hace, qué conectores usa, qué versión.

Ver `references/api-conexion.md` para la anatomía del `.zip` de solución.
