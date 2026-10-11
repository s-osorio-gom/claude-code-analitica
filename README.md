# Taller de analítica con Claude Code

[![auditar](https://github.com/s-osorio-gom/claude-code-analitica/actions/workflows/auditar.yml/badge.svg)](https://github.com/s-osorio-gom/claude-code-analitica/actions/workflows/auditar.yml)

Plantilla y **auditor** para trabajar analítica de negocio con Claude Code sin
que el taller se degrade con el tiempo: dos niveles de `CLAUDE.md`, siete
subagentes con herramientas restringidas por diseño, cinco comandos, una
estructura de proyecto que no se negocia, y un script que comprueba que todo eso
siga siendo cierto.

No es una lista de buenas intenciones. La diferencia está en el auditor:

```bash
python3 herramientas/auditar_taller.py .
```

```
  [  OK  ] Proyectos con la estructura completa           18 / 18
  [  OK  ] Proyectos con LEEME.md                         18 / 18
  [ AVISO] Proyectos sin carpetas fuera de las cuatro     17 / 18
  [ FALLA] Código sin rutas absolutas                   841 / 843
  [  OK  ] Scripts de Python que compilan               509 / 509
  [  OK  ] Sin credenciales dentro del taller          7105 / 7105
  [  OK  ] Enlaces simbólicos que resuelven                 4 / 4
  [ FALLA] Nombres compatibles con Drive y Windows     7103 / 7105
  [ AVISO] Nombres sin 'final', 'copia' ni 'nuevo'     7043 / 7105
  [ AVISO] El índice existe y nombra los proyectos        16 / 18
```

Esa salida es real, sobre el taller de 14 GB y 18 proyectos que originó esta
plantilla (antes de existir el chequeo de configuración de Claude Code, que hoy
añade una fila más). Un `CLAUDE.md` que nadie verifica se convierte en ficción en pocas
semanas: ahí, dos scripts nuevos habían vuelto a fijar una ruta absoluta que
llevaba meses en cero, y dos carpetas terminadas en espacio habrían hecho fallar
la sincronización sin decir por qué.

Sale con código 1 si una regla crítica se rompió (y 2 si la ruta no es una
carpeta), así que sirve igual en la terminal, en un hook de `Stop` o en CI.

| Chequeo | Qué mira | Crítico |
|---|---|---|
| Estructura | cada proyecto con `1_datos_originales/`, `2_trabajo/`, `3_entregable/`, `4_tecnico/` | sí |
| `LEEME.md` | cada proyecto tiene `LEEME.md` o `README.md` | sí |
| Carpetas extra | nada en la raíz del proyecto fuera de las cuatro (salvo `_*`, `legacy_*`, ocultas) | aviso |
| Rutas absolutas | `"/Users/…"`, `"/home/…"`, `"C:\…"`, `"/mnt/c/…"` en `.py .sh .js .gs .sql .r .rmd .ipynb` | sí |
| Sintaxis | todo `.py` compila | sí |
| Credenciales | nombres tipo `.env`, `*secret*`, `*.pem`… y llaves privadas, AWS o `ghp_` en el código | sí |
| Enlaces | ningún enlace simbólico roto | sí |
| Nombres | nada que Windows o Drive rechacen (`: * ?`, espacio o punto final, `CON`, rutas > 240) | sí |
| Nombres flojos | `final`, `copia`, `nuevo`, `definitivo`… | aviso |
| Índice | `EMPIECE_AQUI.md` existe y nombra cada proyecto | aviso |
| Claude Code | `settings*.json` es JSON válido, sin reglas `Write(…)` (que Claude Code acepta y nunca aplica); agentes con `name` y `description`; comandos con frontmatter cerrado | sí |

Busca los proyectos como las carpetas que contienen `1_datos_originales/` y toma
como carpeta de proyectos la que tenga más. Ignora `.git`, `node_modules`,
`__pycache__`, `.venv`, `venv`, `.ipynb_checkpoints` y `.pytest_cache`, y no lee
archivos de código de más de 2 MB.

## Qué trae

```
plantilla/
├── CLAUDE.md                  nivel 1 · dónde está cada cosa, qué no se toca
├── EMPIECE_AQUI.md            el índice: qué archivo abrir para cada proyecto
└── area/
    ├── CLAUDE.md              nivel 2 · rol, validación obligatoria, formato
    ├── .claude/
    │   ├── settings.json      permisos deny / ask
    │   ├── agents/            7 subagentes
    │   └── commands/          5 comandos
    └── proyectos/_plantilla/  la estructura de cuatro carpetas + LEEME.md

herramientas/
├── auditar_taller.py          comprueba que las reglas sigan vigentes
└── preparar_para_drive.py     enlaces simbólicos vs. Drive / OneDrive / Dropbox

docs/por-que.md                de dónde salió cada decisión
```

## Los siete subagentes

| Agente | Para qué | Herramientas |
|---|---|---|
| `orquestador-pm` | Partir un encargo en objetivo, alcance, datos, riesgos y plan | `Read, Glob, Grep` |
| `data-engineer` | Limpiar, cruzar, transformar, automatizar | `Read, Glob, Grep, Bash, Edit, Write` |
| `data-quality-auditor` | Auditar lo que produjo el anterior | `Read, Glob, Grep, Bash` |
| `finance-controller` | Consistencia financiera, variaciones, anomalías | `Read, Glob, Grep, Bash` |
| `commercial-strategist` | Convertir hallazgos en decisiones y mensajes | `Read, Glob, Grep` |
| `geo-logistics-analyst` | Coordenadas, cobertura, asignación, mapas | `Read, Glob, Grep, Bash, Edit, Write` |
| `executive-reviewer` | Última revisión antes de que salga a dirección | `Read, Glob, Grep` |

**Cinco de siete no tienen `Edit` ni `Write`, y ahí está el punto.** Un auditor
que puede arreglar lo que audita tiende a arreglarlo y reportar que todo está
bien. La independencia se consigue quitando herramientas, no pidiéndola en el
prompt. Dos de esos cinco (`data-quality-auditor` y `finance-controller`)
conservan `Bash` para contar y recalcular; un comando de shell sí podría
escribir, así que en ellos la regla «no modificar archivos» descansa también en
el prompt y en los permisos `ask` de `settings.json`.

`data-quality-auditor` y `executive-reviewer` llevan `MUST BE USED` en su
descripción, lo que empuja a Claude a delegarles por iniciativa propia después de
transformar datos y antes de entregar. Es una indicación al modelo, no una
garantía: `/cerrar-entrega` los invoca de forma explícita.

## Los cinco comandos

| Comando | Qué hace |
|---|---|
| `/iniciar-proyecto` | Objetivo, alcance, datos requeridos, riesgos, plan y criterios de aceptación. **No toca archivos.** |
| `/auditar-datos` | Lanza al auditor sobre una base y exige conteos, no impresiones |
| `/revisar-pg` | Ventas contra meta, gastos contra mes anterior, variaciones anómalas |
| `/preparar-reporte-jefes` | Reporte ejecutivo en tercera persona, con decisiones requeridas |
| `/cerrar-entrega` | Encadena auditoría, revisión financiera y revisión ejecutiva antes de dar algo por entregado |

## Requisitos

- Python 3.10 o posterior. Solo biblioteca estándar: no hay nada que instalar.
- [Claude Code](https://code.claude.com/docs) para usar los agentes, comandos y
  permisos de la plantilla. El auditor funciona sin él.
- macOS o Linux. En Windows el auditor corre, pero `preparar_para_drive.py`
  necesita permiso para crear enlaces simbólicos.

## Instalarlo

```bash
git clone https://github.com/s-osorio-gom/claude-code-analitica.git
mkdir -p /ruta/a/mi-taller
cp -r claude-code-analitica/plantilla/* /ruta/a/mi-taller/
cp -r claude-code-analitica/herramientas /ruta/a/mi-taller/
cd /ruta/a/mi-taller
mv area mi-area                      # el nombre real del área
python3 herramientas/auditar_taller.py .
```

Después: llenar `EMPIECE_AQUI.md` con los proyectos reales y copiar
`mi-area/proyectos/_plantilla/` una vez por proyecto. Claude Code se abre desde
`mi-area/`: ahí está `.claude/` y desde ahí carga también el `CLAUDE.md` de la
raíz.

### Que el auditor corra solo

En `mi-area/.claude/settings.json`, como hook de `Stop`. Como la sesión arranca
en `mi-area/` y el auditor vive un nivel arriba, la ruta se arma con
`$CLAUDE_PROJECT_DIR`:

```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/../herramientas/auditar_taller.py\" \"$CLAUDE_PROJECT_DIR/..\" 1>&2 || exit 2"
      }]
    }]
  }
}
```

Claude Code solo bloquea con código 2 y le pasa a Claude lo que salga por
`stderr`; de ahí el `1>&2 || exit 2`. Así, si una regla crítica falla, Claude no
termina el turno y recibe la tabla para corregirla. Si prefiere solo un aviso,
quite `|| exit 2`: el código 1 se muestra como error no bloqueante.
Use esa variante también si hay una falla que no se puede corregir en la sesión
(una carpeta con nombre inválido que hay que renombrar a mano, por ejemplo): con
`exit 2` Claude seguiría intentando terminar y el hook lo seguiría deteniendo.

## Las tres reglas que más sostienen

**Cero rutas absolutas.** `Path(__file__).resolve().parents[n]`, siempre. Una
ruta absoluta convierte el taller en algo que solo corre en una máquina.

**Validación de tres tipos, las tres obligatorias:** numérica (los totales
cuadran contra la fuente), funcional (el script corre completo) y **visual** (el
Excel o el HTML se abre y se mira). La tercera es la que todo el mundo se salta
y la que más defectos encuentra: nada de lo que encuentra produce un error en
consola.

**Si un proyecto queda a medias, se deja funcionando y se escribe qué falta** —
incluido *qué ya se intentó y no hay que repetir*, que es lo que más tiempo
ahorra y lo que nadie escribe.

El resto de las decisiones, con su origen, en **[`docs/por-que.md`](docs/por-que.md)**.

## Un aviso sobre los permisos

Las reglas de `settings.json` apuntan a rutas concretas y **fallan en silencio**:
si la carpeta que protegían dejó de existir tras una reorganización, la regla no
protege nada y nadie se entera. En el taller original, `settings.json` seguía
pidiendo confirmación para escribir en `02_data/`, `05_output/` y `07_QA/`,
carpetas eliminadas meses antes. Las de esta plantilla apuntan a la estructura de
cuatro carpetas; revíselas cuando reorganice.

La otra forma de fallar en silencio es el nombre de la herramienta: Claude Code
solo consulta reglas de ruta escritas como `Read(…)` o `Edit(…)`. Una regla
`Write(./**/3_entregable/**)` se acepta y nunca se aplica; `Edit(…)` ya cubre
crear y sobrescribir archivos. El auditor marca esas reglas como falla.

Los `deny` de lectura protegen frente a las herramientas de Claude y a comandos
como `cat`, pero no frente a un script de Python que abra el archivo por su
cuenta. Por eso `Bash(python *)` está en `ask` y las credenciales van fuera del
taller.

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

Crean en una carpeta temporal una copia de la plantilla y la rompen a propósito,
una regla a la vez (carpeta faltante, ruta absoluta, script que no compila,
binario con extensión `.py`, credencial, enlace roto, nombre inválido,
`settings.json` corrupto, regla `Write(…)`, agente sin frontmatter…), y
comprueban que el auditor sale con código 1. También prueban el ciclo
`bajar`/`subir`/`bajar` de `preparar_para_drive.py` y que rechace un
`enlaces.json` roto o con rutas que se salen del taller. El workflow de
`.github/workflows/auditar.yml` corre lo mismo, más `ruff check .`.

## Qué NO hace

- **No valida números.** El auditor revisa la forma del taller, no los
  resultados. Recalcular desde la fuente por otro camino es trabajo de cada
  proyecto.
- **No gestiona secretos.** Insiste en que vivan fuera del taller y avisa si
  aparecen adentro. La detección es por nombre de archivo y por unos pocos
  formatos de llave; no es un escáner de secretos completo, y puede dar falsos
  positivos con nombres como `secretaria.xlsx`.
- **No revisa el contenido de `.claude/`** más allá de su configuración: los
  secretos, nombres y rutas de esa carpeta no se auditan.
- **No valida el YAML completo** del frontmatter: comprueba que el bloque abra y
  cierre y que existan `name` y `description` en los agentes.
- **No decide.** Los agentes que opinan producen borradores.

---

### In English

A workspace template and **auditor** for running business analytics with Claude
Code. Two-level `CLAUDE.md`, seven subagents (five without Edit/Write *by
design*, so an auditor cannot quietly fix what it audits), five commands, a
four-folder project convention, and a standard-library Python script that fails
when any of it stops being true — including Claude Code permission rules that
are silently ignored — usable as a `Stop` hook or in CI. Docs in Spanish.

## Licencia

MIT — ver [LICENSE](LICENSE).
