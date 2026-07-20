# Plan de flujo — <Nombre del flujo>

> Artefacto de trabajo entre el usuario y la IA. Se itera hasta que el usuario
> lo aprueba; recién entonces se construye la definición. Vive en
> `~/.power-automate-architect/planes/<slug>.md` (sobrevive a compactación).
> `estado: BORRADOR | APROBADO`  ·  `actualizado: <fecha>`

## 1. Objetivo (en una frase)
<Qué problema de negocio resuelve y para quién.>

## 2. Disparador
- Cuándo corre: <correo entrante / programado / manual / cambio en lista…>
- Detalle: <buzón, frecuencia, condiciones de activación>

## 3. Entradas y fuentes de datos
- <De dónde salen los datos: correo+adjuntos, SharePoint, Excel, API…>

## 4. Pasos (borrador, con nombres descriptivos en español)
1. <Nombre del paso> — <qué hace>
2. …
(Marca los pasos que aún son inciertos con ❓.)

## 5. Conectores necesarios
| Conector | Acción | ¿Premium? | ¿Conexión ya existe? |
|---|---|---|---|
| <Office 365 Outlook> | <When a new email arrives V3> | <no> | <sí/no> |

## 6. Datos a extraer / transformar
- <Campos, de qué formato (XML/PDF/…), a dónde van>

## 7. Validación humana
- <Quién valida, cómo se le avisa (Teams/correo/Aprobación), qué decide>

## 8. Manejo de errores y robustez
- Try/Catch + Terminate(Failed); reintentos; idempotencia (no procesar 2 veces);
  qué pasa si un adjunto falta o el formato es inesperado.

## 9. Preguntas abiertas / decisiones pendientes
- [ ] <Pregunta 1 para el usuario>
- [ ] <Decisión de diseño a confirmar>

## 10. Riesgos y supuestos
- <Licencias (créditos IA / premium), volumen, límites, dependencias externas>

## 11. Fuera de alcance (por ahora)
- <Lo que NO hará este flujo, para acotar>
