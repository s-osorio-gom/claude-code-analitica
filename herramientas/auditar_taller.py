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
    secretos      ninguna credencial guardada dentro del taller
    enlaces       ningún enlace simbólico roto
    nombres       nada que Drive o Windows rechacen, ni "final2" ni "copia"
    indice        el índice existe y nombra a todos los proyectos
    claude        settings.json es JSON válido y sus reglas de permiso se
                  consultan; agentes y comandos con frontmatter válido

Qué NO revisa: si los NÚMEROS están bien. Eso lo hace el control de cada
proyecto, recalculándolos desde la fuente por otro camino.
"""
from __future__ import annotations

import argparse
import json
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
SECRETO_CONTENIDO = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,})")
NOMBRE_FLOJO = re.compile(
    r"(?:^|[ _\-(])(final\d*|copia\d*|nuevo|ahora_?si|definitivo|ultimo|v\d+ ?final)"
    r"(?:$|[ _\-.)])", re.IGNORECASE)
PROHIBIDOS_WIN = set('\\:<>"|?*')
RESERVADOS_WIN = ({"CON", "PRN", "AUX", "NUL"}
                  | {f"COM{i}" for i in range(1, 10)}
                  | {f"LPT{i}" for i in range(1, 10)})

# Claude Code solo consulta reglas de ruta escritas como Read(...) o Edit(...).
# Una regla Write(ruta) se acepta pero nunca se aplica: falla en silencio.
REGLA_IGNORADA = re.compile(r"^(Write|NotebookEdit|MultiEdit)\(.+\)$")
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


def ignorado(p: Path, raiz: Path) -> bool:
    """Solo cuentan las partes DENTRO del taller: un taller guardado en
    ~/venv/... o ~/.claude/... no debe quedar ignorado entero."""
    return any(parte in IGNORAR for parte in p.relative_to(raiz).parts)


def archivos(raiz: Path):
    for p in raiz.rglob("*"):
        if not ignorado(p, raiz):
            yield p


def hallar_proyectos(raiz: Path) -> tuple[Path | None, list[Path]]:
    """La carpeta de proyectos es la que contiene subcarpetas con la estructura."""
    candidatas: dict[Path, list[Path]] = {}
    for p in raiz.rglob("1_datos_originales"):
        if p.is_dir() and not ignorado(p, raiz):
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


def revisar_claude(raiz: Path) -> tuple[int, list[str]]:
    """(archivos revisados, hallazgos) de cada carpeta .claude/ del taller."""
    revisados, hallazgos = 0, []
    for cl in sorted(raiz.rglob(".claude")):
        rel_cl = cl.relative_to(raiz)
        if not cl.is_dir() or any(x in IGNORAR - {".claude"} for x in rel_cl.parts):
            continue

        for cfg in sorted(cl.glob("settings*.json")):
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
                    if REGLA_IGNORADA.match(r):
                        hallazgos.append(f"{rel} — {lista}: '{r}' nunca se aplica; "
                                         "use Edit(...) en su lugar")

        for tipo in ("agents", "commands"):
            for md in sorted((cl / tipo).glob("*.md")):
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
    return revisados, hallazgos


def auditar(raiz: Path) -> Informe:
    inf = Informe()
    todos = list(archivos(raiz))
    _padre, proyectos = hallar_proyectos(raiz)

    # ── estructura ──────────────────────────────────────────────────────────
    faltantes = []
    for pr in proyectos:
        falta = [c for c in CARPETAS if not (pr / c).is_dir()]
        if falta:
            faltantes.append(f"{pr.name}: falta {', '.join(falta)}")
    inf.anota("Proyectos con la estructura completa",
              len(proyectos) - len(faltantes), len(proyectos), faltantes)

    sin_leeme = [pr.name for pr in proyectos
                 if not any((pr / n).is_file() for n in ("LEEME.md", "README.md"))]
    inf.anota("Proyectos con LEEME.md", len(proyectos) - len(sin_leeme),
              len(proyectos), sin_leeme)

    extras = []
    for pr in proyectos:
        sobra = [d.name for d in pr.iterdir()
                 if d.is_dir() and d.name not in CARPETAS
                 and not d.name.startswith((".", "legacy_", "_"))]
        if sobra:
            extras.append(f"{pr.name}: {', '.join(sorted(sobra))}")
    inf.anota("Proyectos sin carpetas fuera de las cuatro",
              len(proyectos) - len(extras), len(proyectos), extras, critico=False)

    # ── código ──────────────────────────────────────────────────────────────
    codigo = [p for p in todos if p.is_file() and not p.is_symlink()
              and p.suffix.lower() in CODIGO and p.stat().st_size <= TOPE_BYTES]
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
            except SyntaxError as e:
                no_compilan.append(f"{p.relative_to(raiz)}:{e.lineno} {e.msg}")
            except ValueError as e:  # p. ej. bytes nulos: un binario con extensión .py
                no_compilan.append(f"{p.relative_to(raiz)} — {e}")

    inf.anota("Código sin rutas absolutas", len(codigo) - len(con_ruta),
              len(codigo), con_ruta)
    py = [p for p in codigo if p.suffix.lower() == ".py"]
    inf.anota("Scripts de Python que compilan", len(py) - len(no_compilan),
              len(py), no_compilan)

    # ── secretos ────────────────────────────────────────────────────────────
    por_nombre = [str(p.relative_to(raiz)) for p in todos
                  if p.is_file() and SECRETO_NOMBRE.search(p.name)]
    secretos = sorted(set(por_nombre + con_secreto))
    inf.anota("Sin credenciales dentro del taller",
              len(todos) - len(secretos), len(todos), secretos)

    # ── enlaces ─────────────────────────────────────────────────────────────
    enlaces = [p for p in todos if p.is_symlink()]
    rotos = [str(p.relative_to(raiz)) for p in enlaces if not p.exists()]
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
                   if (raiz / n).is_file()), None)
    if indice is None:
        inf.anota("El índice existe y nombra los proyectos", 0, 1,
                  ["no hay EMPIECE_AQUI.md, INDICE.md ni README.md en la raíz"])
    else:
        texto = indice.read_text(encoding="utf-8", errors="ignore")
        sin_listar = [pr.name for pr in proyectos if pr.name not in texto]
        inf.anota("El índice existe y nombra los proyectos",
                  len(proyectos) - len(sin_listar), len(proyectos),
                  sin_listar, critico=False)

    # ── configuración de Claude Code ────────────────────────────────────────
    revisados, malos_cfg = revisar_claude(raiz)
    inf.anota("Configuración de Claude Code válida",
              revisados - len({h.split(" — ")[0] for h in malos_cfg}),
              revisados, malos_cfg)
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
