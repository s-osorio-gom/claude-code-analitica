# Por qué está armado así

Cada decisión de esta plantilla salió de algo que se rompió antes. El orden es
el de la frecuencia con que muerden.

## 1 · Dos niveles de `CLAUDE.md`, no uno

Un solo archivo mezcla dos cosas que cambian a ritmos distintos: **dónde están
los archivos** (cambia cada semana) y **cómo se trabaja** (casi nunca). Cuando
están juntos, actualizar una ruta obliga a releer el rol, y al final nadie
actualiza nada.

- Nivel 1, la raíz: el índice, la estructura, qué no se toca.
- Nivel 2, el área: el rol, la validación obligatoria, el formato de respuesta.

Un proyecto puede añadir un tercer nivel con lo suyo. Tres es el techo.

## 2 · El auditor de calidad de datos es de solo lectura, a propósito

`data-quality-auditor` tiene `tools: Read, Glob, Grep, Bash`. No tiene `Edit`
ni `Write`. Conserva `Bash` para contar filas y recalcular, y un comando de
shell sí podría escribir; por eso su prompt dice «no modificar archivos» y los
permisos `ask` cubren las carpetas que importan.

No es una precaución: es lo que hace que su veredicto valga. Un agente que puede
arreglar lo que audita tiende a arreglarlo y reportar que todo está bien. Uno
que solo puede mirar tiene que decir lo que vio. La independencia se consigue
quitando herramientas, no pidiendo objetividad en el prompt.

Lo mismo vale para `executive-reviewer`, `finance-controller` y
`commercial-strategist`: opinan, no editan. De los cuatro, solo
`finance-controller` tiene `Bash`.

## 3 · Cuatro carpetas numeradas, iguales en todos los proyectos

```
1_datos_originales/   2_trabajo/   3_entregable/   4_tecnico/
```

Los números no son decorativos: marcan el flujo —original → trabajo →
entregable— y el código va aparte porque no es ninguna de las tres.

Lo que esto compra: **si entiendes un proyecto, entiendes todos**. Una sesión
nueva no tiene que averiguar dónde está el entregable de este proyecto en
particular. Y `1_datos_originales/` inmutable significa que siempre hay a qué
volver cuando un número no cuadra.

La regla que lo sostiene: **no se agregan carpetas en la raíz de un proyecto.**
Si hace falta separar algo, se subdivide dentro de una de las cuatro. Sin esa
regla, en tres meses cada proyecto tiene su propia forma.

## 4 · Cero rutas absolutas

```python
BASE = Path(__file__).resolve().parents[3]      # sí
BASE = Path("/Users/quien/Documents/taller")    # no
```

Una ruta absoluta convierte el taller en algo que solo corre en una máquina y
solo mientras nadie renombre una carpeta. El auditor las busca en todo el
código y falla si encuentra una.

No es teórico: al correr el auditor sobre el taller que originó esta plantilla
—que llevaba meses en cero— aparecieron dos scripts nuevos que fijaban la ruta
del kit de presentaciones. Habrían fallado en cualquier otro computador.

## 5 · La validación es de tres tipos y las tres son obligatorias

1. **Numérica** — los totales cuadran contra la fuente, y el cruce se documenta.
2. **Funcional** — el script corre de principio a fin sin error.
3. **Visual** — el Excel o el HTML se abre y se mira.

La tercera es la que se salta todo el mundo y la que más defectos encuentra:
cifras que no coinciden entre un panel y un tooltip, etiquetas que tapan el
dato, estados mal marcados. Nada de eso produce un error en consola.

## 6 · Permisos: `deny` para lo irreversible, `ask` para lo que se entrega

`deny` no pregunta: leer credenciales, `rm -rf`, `curl`, `wget`. Son cosas donde
la respuesta correcta nunca es "sí, dale".

`ask` es para lo que va a manos de otra persona —escribir en `3_entregable/`— y
para lo que altera el original (`1_datos_originales/`, `legacy_*`), además de
correr `python` y `pip`. No es desconfianza en el modelo: es que un
entregable que cambia sin que nadie lo note es un problema aunque el cambio sea
correcto.

> Revise las rutas de su `settings.json` cuando reorganice el taller. Las reglas
> de permiso apuntan a rutas concretas y **fallan en silencio**: si la carpeta
> que protegían dejó de existir, la regla no protege nada y nada se lo avisa.
> Es exactamente lo que había pasado en el taller que originó esta plantilla.
>
> Lo mismo pasa con el nombre de la herramienta: Claude Code solo consulta
> reglas de ruta `Read(…)` y `Edit(…)`. Una regla `Write(…)` se acepta y nunca se
> aplica. La primera versión de esta plantilla tenía cuatro; el auditor ahora
> las marca como falla.

## 7 · "No recorras el árbol"

Un taller de analítica llega rápido a decenas de GB. Recorrerlo para encontrar
un archivo gasta el contexto que hacía falta para el trabajo.

Por eso el índice (`EMPIECE_AQUI.md`) es obligatorio y por eso dice **qué
archivo abrir** para cada proyecto. Mantenerlo al día es barato; reconstruirlo
mentalmente en cada sesión, no.

## 8 · Un proyecto roto se deja funcionando y documentado

Cuando algo queda a medias, en su `LEEME.md` va: qué funciona hoy, dónde se
quedó, qué se necesita para continuar y **qué ya se intentó y no hay que
repetir**.

Lo último es lo que más tiempo ahorra y lo que nadie escribe.

## 9 · Lo que esta plantilla no resuelve

- **No valida números.** Ni el auditor ni los agentes recalculan nada desde la
  fuente. Eso lo tiene que hacer un control dentro de cada proyecto, por un
  camino distinto al que produjo el resultado.
- **No sustituye el criterio.** Los agentes que opinan —estrategia, finanzas,
  revisión ejecutiva— producen borradores, no decisiones.
- **No gestiona secretos.** Solo insiste en que vivan fuera del taller y avisa
  si aparecen adentro.
