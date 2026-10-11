# Empiece aquí

Índice del taller. **Este archivo es el contrato**: si una ruta cambia y no se
actualiza aquí, la siguiente sesión se pierde recorriendo carpetas.

No necesita saber programar para usar esta carpeta.

## 1. Reglas de oro

1. **Nunca edite nada dentro de `1_datos_originales/`.** Es la información
   original. Si se daña, no se recupera.
2. **Trabaje sobre una copia.** Si va a experimentar, duplique el archivo.
3. **Ningún número que salga de una IA se usa en una decisión sin verificarlo**
   contra el archivo fuente.
4. **Contraseñas y llaves no van aquí.** Viven fuera del taller.

## 2. Todos los proyectos son idénticos por dentro

```
proyectos/<PROYECTO>/
├── LEEME.md              <- empiece aquí: qué es, qué abro, qué falta
├── 1_datos_originales/   <- lo que llegó. NO SE TOCA.
├── 2_trabajo/            <- limpieza, cruces, versiones
├── 3_entregable/         <- lo que se presenta
└── 4_tecnico/            <- código y logs
```

## 3. Qué archivo abro

| Proyecto | Estado | Archivo que se abre | Código |
|---|---|---|---|
| `_plantilla` | plantilla | — | — |

<!-- Una fila por proyecto. Mantenerla al día es la única tarea obligatoria
     de este archivo. -->

## 4. Nivel de sensibilidad

Revíselo antes de compartir.

| Nivel | Proyectos | Quién debería verlo |
|---|---|---|
| Alto | | |
| Medio | | |
| Bajo | | |

## 5. Si algo falla

| Síntoma | Qué hacer |
|---|---|
| No sé qué archivo abrir | La tabla del punto 3, o el `LEEME.md` del proyecto |
| Un script da error de "no such file" | La ruta cambió. Repórtelo; no lo edite a ciegas. |
| No sé si un número está bien | Búsquelo en `1_datos_originales/`. Esa es la verdad. |

**A quién consultar:** <nombre y correo>

## 6. Estado verificado

Lo produce `python3 herramientas/auditar_taller.py .`
Si algo de esa tabla deja de ser cierto, algo se rompió.
