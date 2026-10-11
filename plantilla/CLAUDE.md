# Reglas del taller

> Nivel 1 de dos. Aquí van las reglas que valen para **todo** lo que hay en esta
> carpeta: dónde está cada cosa y qué no se toca. El rol, la validación
> obligatoria y el formato de respuesta están un nivel abajo, en
> `area/CLAUDE.md`. Renombre `area/` como se llame la suya.

Antes de buscar cualquier archivo, leer **`EMPIECE_AQUI.md`**: tiene la ruta
exacta de cada entregable.

**No recorras el árbol completo.** Un taller de analítica llega a decenas de GB
entre datos crudos y cartografía; recorrerlo agota el contexto sin aportar nada.
El índice tiene la ruta que necesitas.

## Reglas críticas

1. **Las rutas del código son relativas.** Ningún script lleva una ruta absoluta
   escrita a mano; usan `Path(__file__).resolve().parents[n]`. Eso permite mover
   o renombrar carpetas sin romper nada. **No escribas rutas absolutas.**

2. **Todos los proyectos tienen la misma estructura.** No agregues carpetas
   nuevas en la raíz de un proyecto: subdivide dentro de una de las cuatro.

   ```
   proyectos/<PROYECTO>/
   ├── LEEME.md
   ├── 1_datos_originales/   <- NO SE TOCA
   ├── 2_trabajo/
   ├── 3_entregable/
   └── 4_tecnico/
   ```

   Los números marcan el flujo: original → trabajo → entregable, y el código
   aparte. **Si entiendes un proyecto, entiendes todos.**

3. **Cada proyecto lleva adentro lo que necesita.** No hay carpetas de datos
   compartidos por fuera. Si un proyecto necesita cartografía, un maestro o
   cualquier insumo, va en su propia `1_datos_originales/`.

   La excepción son los insumos pesados que se repiten: existen **una sola vez**
   y los demás proyectos los ven por un enlace simbólico dentro de su propia
   `1_datos_originales/`, de modo que en el código la ruta es siempre la misma.
   Nunca los copies. Ver `herramientas/preparar_para_drive.py`.

4. **No modificar `1_datos_originales/` ni carpetas `legacy_*`** sin
   autorización explícita.

5. **Contraseñas y llaves nunca dentro de esta carpeta.** Van fuera, en un
   directorio que no se sincroniza ni se respalda con el resto.

6. **Nombres en español**, sin `final`, `final2`, `copia`, `nuevo`, `ahora_si`.
   Si hay versiones, usa fecha: `Sobreprecio - version 2026-07-07.xlsx`.

7. **Todo proyecto lleva `LEEME.md`** con: qué es, cuál archivo se abre, cómo se
   corre y qué falta si quedó a medias.

8. **Lo personal no va aquí.**

## Para una sesión nueva

Lee este archivo y `area/CLAUDE.md`. Después **solo** el `LEEME.md` del proyecto
que te pidan. No leas los otros proyectos: gasta contexto sin aportar.

| Si te piden… | Lee SOLO esto |
|---|---|
| Trabajar en un proyecto | `EMPIECE_AQUI.md` + `proyectos/<proyecto>/LEEME.md` |
| Empezar algo nuevo | `/iniciar-proyecto` |
| Cerrar una entrega | `/cerrar-entrega` |

## Comprobar que esto sigue siendo cierto

```bash
python3 herramientas/auditar_taller.py .
```

Si el auditor falla, alguna de estas reglas dejó de cumplirse.
