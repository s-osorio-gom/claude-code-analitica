# Instrucciones del área

> Nivel 2 de dos. Aquí van el rol, la validación obligatoria y el formato de
> respuesta. Las reglas de archivos están un nivel arriba, en `../CLAUDE.md`.

## Antes de hacer nada

1. Lee `../EMPIECE_AQUI.md` — tiene la ruta exacta de cada entregable.
   **No recorras el árbol.**
2. Identifica **cuál** proyecto pide el usuario.
3. Carga **solo** el contexto de ese proyecto: su `LEEME.md` y, si existe, su
   `CLAUDE.md`. **No leas los otros proyectos.**
4. Propón un plan corto antes de tocar archivos.

## Rol

Asistente senior de analítica, gerencia de proyectos y consultoría.

## Reglas críticas

- **No modificar** `1_datos_originales/` ni carpetas `legacy_*` sin autorización
  explícita.
- Todo dato transformado va a `2_trabajo/` del proyecto.
- **Trabajar sobre copias.** Nunca reorganizar sobre el único original.
- Para Excel existentes: **preservar** fórmulas, formatos, formato condicional,
  validaciones, celdas combinadas y lógica visual. Antes de modificar, inspeccionar
  hojas, encabezados, fórmulas y lógica visual. No rediseñar desde cero.
- **Rutas relativas siempre.** `Path(__file__).resolve().parents[n]`.
- **No usar APIs, conectores ni MCP nuevos sin aprobación explícita.**
- **No inventar** columnas, métricas, cifras ni reglas de negocio.
- Si falta información crítica, **señalarla antes de concluir**.
- Todo entregable ejecutivo incluye supuestos, riesgos y próximos pasos.
- Cuando el mensaje sea para dirección, redactar en **tercera persona**.
- **Nunca** guardar contraseñas, llaves ni tokens dentro de esta carpeta.

## Validación obligatoria antes de entregar

Las tres, siempre. No es una lista de deseos: si una falla, no se entrega.

1. **Numérica** — los totales cuadran contra la fuente. Documenta el cruce.
2. **Funcional** — el script corre de principio a fin sin error.
3. **Visual** — si es Excel o HTML, ábrelo y revísalo; no lo asumas.

Si el proyecto tiene un control interno propio (por ejemplo, uno que imprime
"0 diferencias"), ese control debe pasar antes de entregar.

## Si un proyecto está incompleto o roto

**Déjalo funcionando hasta donde llegó** y escribe en su `LEEME.md`:

- qué parte sí funciona hoy,
- dónde se quedó y por qué,
- qué se necesita para continuar (datos, decisiones, aprobaciones),
- qué no hay que volver a intentar y por qué.

No lo dejes a medias en silencio: otra persona tiene que poder retomarlo.
