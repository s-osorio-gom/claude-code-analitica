#!/usr/bin/env python3
"""
auditar_taller.py — comprueba que el taller siga cumpliendo sus propias reglas.

    python3 herramientas/auditar_taller.py <ruta del taller>
    python3 herramientas/auditar_taller.py . --detalle

Un CLAUDE.md que nadie verifica es una carta de buenas intenciones. Esto lo
convierte en algo que puede FALLAR: sale con código 1 si una regla crítica dejó
de cumplirse, así que sirve igual en la terminal que en un hook o en CI.

Qué revisa

    estructura    cada proyecto con sus cuatro carpetas y su LEEME.md
    rutas         ninguna ruta absoluta escrita a mano en el código
    sintaxis      todo script de Python compila
    secretos      ninguna credencial guardada dentro del taller, incluida .claude/
    enlaces       ningún enlace simbólico roto
    nombres       nada que Drive o Windows rechacen, ni "final2" ni "copia"
    indice        el índice existe y nombra a todos los proyectos
    claude        settings.json es JSON válido y sus reglas de permiso se
                  consultan; agentes y comandos con frontmatter válido y
                  agentes sin name repetido

Sale con 0 si todo lo crítico pasa, 1 si algo crítico falla y 2 si la ruta no
es una carpeta.

Qué NO revisa: si los NÚMEROS están bien. Eso lo hace el control de cada
proyecto, recalculándolos desde la fuente por otro camino.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

CARPETAS = ("1_datos_originales", "2_trabajo", "3_entregable", "4_tecnico")
CODIGO = {".py", ".sh", ".js", ".gs", ".sql", ".r", ".rmd", ".ipynb"}
IGNORAR = {".git", "node_modules", "__pycache__", ".venv", "venv",
           ".ipynb_checkpoints", ".pytest_cache", ".claude"}
TOPE_BYTES = 2_000_000

RUTA_ABSOLUTA = re.compile(r"""["'](?:/Users/|/home/|[A-Za-z]:[\\/]|/mnt/[a-z]/)""")
SECRETO_NOMBRE = re.compile(
    r"(^\.env$|\.env\.|credential|secret|_token|password|\.pem$|\.p12$|\.pfx$"
    r"|^service[_-]account.*\.json$|\.key$)", re.IGNORECASE)
# Dentro de .claude/ los nombres de agentes, comandos y hooks hablan de secretos
# («secret-scanner.md», «check_password.py») sin serlo: ahí solo cuentan los
# nombres de archivos de credenciales reales. El contenido se revisa entero.
SECRETO_ARCHIVO = re.compile(
    r"(^\.env$|^\.env\.|^\.?credentials?(\.\w+)?$|^service[_-]account.*\.json$"
    r"|\.pem$|\.p12$|\.pfx$|\.key$|^id_(rsa|dsa|ecdsa|ed25519)$)", re.IGNORECASE)
SECRETO_CONTENIDO = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}"
    r"|sk-ant-[A-Za-z0-9_-]{20,})")
NOMBRE_FLOJO = re.compile(
    r"(?:^|[ _\-(])(final\d*|copia\d*|nuevo|ahora_?si|definitivo|ultimo|v\d+ ?final)"
    r"(?:$|[ _\-.)])", re.IGNORECASE)
PROHIBIDOS_WIN = set('\\:<>"|?*')
RESERVADOS_WIN = ({"CON", "PRN", "AUX", "NUL"}
                  | {f"COM{i}" for i in range(1, 10)}
                  | {f"LPT{i}" for i in range(1, 10)})

# Claude Code solo consulta reglas de ruta escritas como Read(...) o Edit(...).
# Una regla Write(ruta), NotebookEdit(ruta), MultiEdit(ruta) o Glob(ruta) se
# acepta pero nunca se aplica: falla en silencio. Sin ruta (solo el nombre de la
# herramienta) sí se aplica, así que no se marca.
REGLA_IGNORADA = re.compile(r"^(Write|NotebookEdit|MultiEdit|Glob)\(.+\)$")
NOMBRE_AGENTE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class Informe:
    def __init__(self):
        self.filas, self.detalles, self.criticos = [], {}, 0

    def anota(self, chequeo, ok_n, total, hallazgos, critico=True):
        estado = "OK" if not hallazgos else ("FALLA" if critico else "AVISO")
        if hallazgos and critico:
            self.criticos += 1
        self.filas.append((chequeo, f"{ok_n} / {total}", estado))
        if hallazgos:
            self.detalles[chequeo] = hallazgos


class Arbol:
    """Un solo recorrido del taller que nunca lanza: lo que no se puede leer
    queda en `ilegibles` en vez de interrumpir la auditoría. No sigue enlaces
    simbólicos a carpetas (aparecen como entrada, no se recorren)."""

    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.carpetas: list[Path] = []
        self.archivos: list[Path] = []      # incluye enlaces a archivos y enlaces rotos
        self.ilegibles: list[Path] = []

        def error(e: OSError):
            self.ilegibles.append(Path(e.filename))

        for base, dirs, files in os.walk(raiz, onerror=error):
            b = Path(base)
            dirs[:] = sorted(d for d in dirs if d not in IGNORAR - {".claude"})
            self.carpetas += [b / d for d in dirs]
            self.archivos += [b / f for f in sorted(files)]
        self.es_carpeta = set(self.carpetas)
        self.es_archivo = set(self.archivos)

    def rel(self, p: Path) -> tuple[str, ...]:
        return p.relative_to(self.raiz).parts

    def fuera_de_claude(self) -> list[Path]:
        """Todo lo del taller salvo el contenido de .claude/ (ni la carpeta misma)."""
        return [p for p in self.carpetas + self.archivos if ".claude" not in self.rel(p)]


def seguro(prueba, defecto=False):
    """is_file(), exists(), stat()… sin dejar que un permiso denegado lance."""
    try:
        return prueba()
    except OSError:
        return defecto


def archivos_claude(arbol: Arbol) -> tuple[list[Path], list[Path]]:
    """(configuración, worktrees): los archivos de cada .claude/ del taller, para
    buscar credenciales.

    Configuración es settings.local.json —cuyo bloque `env` es donde suele
    terminar una API key—, agentes, comandos, hooks… Worktrees es
    .claude/worktrees/<nombre>/: copias de trabajo del repositorio que viven
    dentro del taller y se sincronizan con él, y a las que `.worktreeinclude`
    copia archivos ignorados por git como `.env`. Lo que decide es el último
    .claude/ de la ruta: el .claude/ de un worktree vuelve a ser configuración."""
    config, worktrees = [], []
    for p in arbol.archivos:
        partes = arbol.rel(p)
        if ".claude" not in partes:
            continue
        k = len(partes) - 1 - partes[::-1].index(".claude")
        (worktrees if partes[k + 1] == "worktrees" else config).append(p)
    return config, worktrees


def hallar_proyectos(arbol: Arbol) -> tuple[Path | None, list[Path]]:
    """La carpeta de proyectos es la que contiene subcarpetas con la estructura."""
    candidatas: dict[Path, list[Path]] = {}
    for p in arbol.carpetas:
        if p.name == "1_datos_originales" and ".claude" not in arbol.rel(p):
            candidatas.setdefault(p.parent.parent, []).append(p.parent)
    if not candidatas:
        return None, []
    padre = max(candidatas, key=lambda k: len(candidatas[k]))
    return padre, sorted(candidatas[padre])


def frontmatter(texto: str) -> dict[str, str] | None:
    """Claves de primer nivel del bloque --- ... --- inicial; None si no lo hay
    o no cierra. No es un parser YAML completo: basta para las claves simples
    (name, description, tools, argument-hint) que usa Claude Code."""
    lineas = texto.lstrip("\ufeff").splitlines()
    if not lineas or lineas[0].strip() != "---":
        return None
    claves: dict[str, str] = {}
    for linea in lineas[1:]:
        if linea.strip() == "---":
            return claves
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", linea)
        if m:
            claves[m.group(1)] = m.group(2).strip()
    return None


def revisar_claude(arbol: Arbol) -> tuple[int, list[str]]:
    """(archivos revisados, hallazgos) de cada carpeta .claude/ del taller."""
    raiz = arbol.raiz
    revisados, hallazgos = 0, []
    for cl in sorted(c for c in arbol.carpetas if c.name == ".claude"):
        propios = [p for p in arbol.archivos if cl in p.parents]

        for cfg in sorted(p for p in propios
                          if p.parent == cl and fnmatch.fnmatch(p.name, "settings*.json")):
            revisados += 1
            rel = cfg.relative_to(raiz)
            try:
                datos = json.loads(cfg.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
                hallazgos.append(f"{rel} — no es JSON válido: {e}")
                continue
            permisos = datos.get("permissions", {}) if isinstance(datos, dict) else None
            if not isinstance(permisos, dict):
                hallazgos.append(f"{rel} — 'permissions' debe ser un objeto")
                continue
            for lista in ("allow", "ask", "deny"):
                reglas = permisos.get(lista, [])
                if not isinstance(reglas, list) or not all(isinstance(r, str) for r in reglas):
                    hallazgos.append(f"{rel} — permissions.{lista} debe ser una lista de textos")
                    continue
                for r in reglas:
                    m = REGLA_IGNORADA.match(r)
                    if m:
                        en_su_lugar = "Read" if m.group(1) == "Glob" else "Edit"
                        hallazgos.append(f"{rel} — {lista}: '{r}' nunca se aplica; "
                                         f"use {en_su_lugar}(...) en su lugar")

        # Claude Code recorre agents/ y commands/ con subcarpetas, y el name
        # identifica al agente: si dos archivos lo repiten, uno tapa al otro.
        nombres: dict[str, Path] = {}
        for tipo in ("agents", "commands"):
            for md in sorted(p for p in propios
                             if (cl / tipo) in p.parents and p.suffix == ".md"):
                revisados += 1
                rel = md.relative_to(raiz)
                try:
                    texto = md.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as e:
                    hallazgos.append(f"{rel} — no se puede leer como UTF-8: {e}")
                    continue
                fm = frontmatter(texto)
                if tipo == "commands":
                    # En un comando el frontmatter es opcional, pero si abre debe cerrar.
                    if fm is None and texto.lstrip("\ufeff").startswith("---"):
                        hallazgos.append(f"{rel} — el frontmatter no cierra con ---")
                    continue
                if fm is None:
                    hallazgos.append(f"{rel} — sin frontmatter --- ... ---")
                    continue
                falta = [k for k in ("name", "description") if not fm.get(k)]
                if falta:
                    hallazgos.append(f"{rel} — falta {', '.join(falta)} en el frontmatter")
                elif not NOMBRE_AGENTE.match(fm["name"]):
                    hallazgos.append(f"{rel} — name '{fm['name']}' debe ir en "
                                     "minúsculas y guiones")
                elif fm["name"] in nombres:
                    hallazgos.append(f"{rel} — name '{fm['name']}' repetido; ya lo usa "
                                     f"{nombres[fm['name']].relative_to(raiz)}")
                else:
                    nombres[fm["name"]] = md
    return revisados, hallazgos


def auditar(raiz: Path) -> Informe:
    inf = Informe()
    arbol = Arbol(raiz)
    todos = arbol.fuera_de_claude()
    _padre, proyectos = hallar_proyectos(arbol)

    # ── estructura ──────────────────────────────────────────────────────────
    # Sin ningún proyecto, casi seguro la ruta es otra: que no pase en verde.
    faltantes = [] if proyectos else [
        "ningún proyecto: no hay carpetas con 1_datos_originales/ — ¿es la raíz del taller?"]
    for pr in proyectos:
        falta = [c for c in CARPETAS if (pr / c) not in arbol.es_carpeta]
        if falta:
            faltantes.append(f"{pr.name}: falta {', '.join(falta)}")
    inf.anota("Proyectos con la estructura completa",
              max(len(proyectos) - len(faltantes), 0), len(proyectos), faltantes)

    sin_leeme = [pr.name for pr in proyectos
                 if not any((pr / n) in arbol.es_archivo for n in ("LEEME.md", "README.md"))]
    inf.anota("Proyectos con LEEME.md", len(proyectos) - len(sin_leeme),
              len(proyectos), sin_leeme)

    extras = []
    for pr in proyectos:
        sobra = [d.name for d in arbol.carpetas
                 if d.parent == pr and d.name not in CARPETAS
                 and not d.name.startswith((".", "legacy_", "_"))]
        if sobra:
            extras.append(f"{pr.name}: {', '.join(sorted(sobra))}")
    inf.anota("Proyectos sin carpetas fuera de las cuatro",
              len(proyectos) - len(extras), len(proyectos), extras, critico=False)

    # ── código ──────────────────────────────────────────────────────────────
    codigo = [p for p in todos if p in arbol.es_archivo and p.suffix.lower() in CODIGO
              and seguro(lambda p=p: not p.is_symlink() and p.stat().st_size <= TOPE_BYTES)]
    con_ruta, no_compilan, con_secreto = [], [], []
    for p in codigo:
        try:
            texto = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            if RUTA_ABSOLUTA.search(linea):
                con_ruta.append(f"{p.relative_to(raiz)}:{n}")
                break
        if SECRETO_CONTENIDO.search(texto):
            con_secreto.append(str(p.relative_to(raiz)))
        if p.suffix.lower() == ".py":
            try:
                compile(texto, str(p), "exec")
            except SyntaxError as e:  # desde 3.12 los bytes nulos llegan aquí, sin línea
                linea = f":{e.lineno}" if e.lineno else " —"
                no_compilan.append(f"{p.relative_to(raiz)}{linea} {e.msg}")
            except ValueError as e:  # p. ej. bytes nulos: un binario con extensión .py
                no_compilan.append(f"{p.relative_to(raiz)} — {e}")

    inf.anota("Código sin rutas absolutas", len(codigo) - len(con_ruta),
              len(codigo), con_ruta)
    py = [p for p in codigo if p.suffix.lower() == ".py"]
    inf.anota("Scripts de Python que compilan", len(py) - len(no_compilan),
              len(py), no_compilan)

    # ── secretos ────────────────────────────────────────────────────────────
    # En los worktrees rigen las reglas del resto del taller; en la configuración,
    # solo nombres de credenciales reales, pero todo el contenido. Un enlace
    # simbólico se sigue: Drive lo convierte en copia del archivo al que apunta.
    config, worktrees = archivos_claude(arbol)
    por_nombre = [str(p.relative_to(raiz)) for p in todos + worktrees
                  if SECRETO_NOMBRE.search(p.name) and seguro(p.is_file)]
    por_nombre += [str(p.relative_to(raiz)) for p in config
                   if SECRETO_ARCHIVO.search(p.name) and seguro(p.is_file)]
    revisar_contenido = config + [p for p in worktrees if p.suffix.lower() in CODIGO
                                  and seguro(lambda p=p: not p.is_symlink())]
    for p in revisar_contenido:
        if seguro(lambda p=p: p.stat().st_size <= TOPE_BYTES):
            try:
                texto = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if SECRETO_CONTENIDO.search(texto):
                con_secreto.append(str(p.relative_to(raiz)))
    secretos = sorted(set(por_nombre + con_secreto))
    total = len(todos) + len(config) + len(worktrees)
    inf.anota("Sin credenciales dentro del taller",
              total - len(secretos), total, secretos)

    # ── enlaces ─────────────────────────────────────────────────────────────
    enlaces = [p for p in todos if seguro(p.is_symlink)]
    rotos = [str(p.relative_to(raiz)) for p in enlaces if not seguro(p.exists)]
    inf.anota("Enlaces simbólicos que resuelven",
              len(enlaces) - len(rotos), len(enlaces), rotos)

    # ── nombres ─────────────────────────────────────────────────────────────
    malos = []
    for p in todos:
        n = p.name
        if PROHIBIDOS_WIN & set(n):
            malos.append(f"{p.relative_to(raiz)} — carácter que Windows rechaza")
        elif n != n.rstrip(" ."):
            malos.append(f"{p.relative_to(raiz)} — termina en espacio o punto")
        elif n.split(".")[0].upper() in RESERVADOS_WIN:
            malos.append(f"{p.relative_to(raiz)} — nombre reservado de Windows")
        elif len(str(p.relative_to(raiz))) > 240:
            malos.append(f"{p.relative_to(raiz)} — ruta demasiado larga")
    inf.anota("Nombres compatibles con Drive y Windows",
              len(todos) - len(malos), len(todos), malos)

    flojos = [str(p.relative_to(raiz)) for p in todos if NOMBRE_FLOJO.search(p.stem)]
    inf.anota("Nombres sin 'final', 'copia' ni 'nuevo'",
              len(todos) - len(flojos), len(todos), flojos, critico=False)

    # ── índice ──────────────────────────────────────────────────────────────
    indice = next((raiz / n for n in ("EMPIECE_AQUI.md", "INDICE.md", "README.md")
                   if (raiz / n) in arbol.es_archivo), None)
    if indice is None:
        inf.anota("El índice existe y nombra los proyectos", 0, 1,
                  ["no hay EMPIECE_AQUI.md, INDICE.md ni README.md en la raíz"])
    elif (texto := seguro(lambda: indice.read_text(encoding="utf-8", errors="ignore"),
                          None)) is None:
        inf.anota("El índice existe y nombra los proyectos", 0, 1,
                  [f"{indice.name} no se puede leer (¿permisos?)"])
    else:
        sin_listar = [pr.name for pr in proyectos if pr.name not in texto]
        inf.anota("El índice existe y nombra los proyectos",
                  len(proyectos) - len(sin_listar), len(proyectos),
                  sin_listar, critico=False)

    # ── configuración de Claude Code ────────────────────────────────────────
    revisados, malos_cfg = revisar_claude(arbol)
    inf.anota("Configuración de Claude Code válida",
              revisados - len({h.split(" — ")[0] for h in malos_cfg}),
              revisados, malos_cfg)

    # ── lo que no se pudo leer ──────────────────────────────────────────────
    # Aviso, no falla: el auditor no sabe qué hay adentro, pero no lo calla.
    ilegibles = [f"{p.relative_to(raiz) if p != raiz else '.'} — sin permiso de lectura; "
                 "su contenido no se auditó" for p in arbol.ilegibles]
    carpetas = len(arbol.carpetas) + 1
    inf.anota("Carpetas que se pudieron leer", carpetas - len(ilegibles), carpetas,
              ilegibles, critico=False)
    return inf


def main() -> int:
    ap = argparse.ArgumentParser(description="Audita las convenciones de un taller.")
    ap.add_argument("ruta", nargs="?", default=".")
    ap.add_argument("--detalle", action="store_true",
                    help="lista todos los hallazgos, no solo los cinco primeros")
    a = ap.parse_args()

    raiz = Path(a.ruta).resolve()
    if not raiz.is_dir():
        print(f"No es una carpeta: {raiz}", file=sys.stderr)
        return 2

    print(f"\n  Taller: {raiz}")
    inf = auditar(raiz)

    ancho = max(len(f[0]) for f in inf.filas)
    print("\n  " + "─" * (ancho + 22))
    for chequeo, cuenta, estado in inf.filas:
        marca = {"OK": "  OK  ", "AVISO": " AVISO", "FALLA": " FALLA"}[estado]
        print(f"  [{marca}] {chequeo.ljust(ancho)}  {cuenta:>10}")
    print("  " + "─" * (ancho + 22))

    for chequeo, hallazgos in inf.detalles.items():
        print(f"\n  {chequeo}:")
        for h in (hallazgos if a.detalle else hallazgos[:5]):
            print(f"      · {h}")
        if not a.detalle and len(hallazgos) > 5:
            print(f"      … y {len(hallazgos) - 5} más (--detalle)")

    print(f"\n  {inf.criticos} chequeos críticos en falla\n")
    return 1 if inf.criticos else 0


if __name__ == "__main__":
    raise SystemExit(main())
