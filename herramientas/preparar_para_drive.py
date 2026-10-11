#!/usr/bin/env python3
"""
preparar_para_drive.py — sobrevivir a un sincronizador que no entiende enlaces.

    python3 herramientas/preparar_para_drive.py revisar
    python3 herramientas/preparar_para_drive.py subir     # antes de sincronizar
    python3 herramientas/preparar_para_drive.py bajar     # después de bajar

EL PROBLEMA

Un insumo pesado que varios proyectos comparten —cartografía, un maestro, un
volcado— existe UNA sola vez y los demás proyectos lo ven por un enlace
simbólico dentro de su propia carpeta de datos. Así la ruta en el código es
siempre la misma y el disco no guarda cinco copias.

Google Drive, OneDrive y Dropbox no entienden esos enlaces: **los convierten en
copias completas**. Cinco proyectos con un enlace a 1,4 GB se vuelven 7 GB, y
después nadie sabe cuál es la buena.

LA SOLUCIÓN

Retirar los enlaces antes de sincronizar, dejando en su lugar una nota que
explica qué falta y cómo recuperarlo, y volver a crearlos al bajar.

CONFIGURACIÓN

Un `enlaces.json` en la raíz del taller:

    {
      "enlaces": [
        {
          "nombre": "MGN2024",
          "origen":  "proyectos/mapas/1_datos_originales/MGN2024",
          "destinos": ["proyectos/cobertura/1_datos_originales",
                       "proyectos/rutas/1_datos_originales"]
        }
      ]
    }

`origen` es la copia real; cada `destino` es la carpeta donde va el enlace.
Todas las rutas son relativas a la raíz del taller.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

BASURA = (".DS_Store", ".Rhistory", "__pycache__", "*.pyc", "Thumbs.db")

NOTA = """Aquí va un enlace a: {nombre}

Se retiró antes de sincronizar porque el sincronizador no entiende los enlaces
simbólicos y los convierte en copias completas.

La copia real está en:
    {origen}

Para recuperar el enlace, desde la raíz del taller:

    python3 herramientas/preparar_para_drive.py bajar

Mientras el enlace no exista, lo que dependa de este insumo no se puede volver
a generar. Lo que ya está hecho sigue funcionando.
"""


class ConfigInvalida(Exception):
    """enlaces.json existe pero no se puede usar tal como está."""


def _ruta_interna(raiz: Path, texto, campo: str) -> str:
    """Una ruta del JSON: texto, relativa y sin salirse del taller."""
    if not isinstance(texto, str) or not texto.strip():
        raise ConfigInvalida(f"'{campo}' debe ser un texto no vacío")
    if Path(texto).is_absolute():
        raise ConfigInvalida(f"'{campo}' debe ser relativa a la raíz del taller: {texto}")
    destino = (raiz / texto).resolve()
    if destino != raiz.resolve() and raiz.resolve() not in destino.parents:
        raise ConfigInvalida(f"'{campo}' se sale del taller: {texto}")
    return texto


def cargar(raiz: Path) -> list[dict]:
    cfg = raiz / "enlaces.json"
    if not cfg.is_file():
        print(f"  No hay {cfg.name} en la raíz del taller.")
        print("  Si ningún insumo se comparte por enlace, no hace falta.")
        return []
    try:
        datos = json.loads(cfg.read_text(encoding="utf-8"))
    except OSError as e:
        raise ConfigInvalida(f"{cfg.name} no se puede leer: {e.strerror}") from e
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ConfigInvalida(f"{cfg.name} no es JSON válido en UTF-8: {e}") from e
    enlaces = datos.get("enlaces", []) if isinstance(datos, dict) else None
    if not isinstance(enlaces, list):
        raise ConfigInvalida("'enlaces' debe ser una lista")
    for i, e in enumerate(enlaces):
        if not isinstance(e, dict):
            raise ConfigInvalida(f"enlaces[{i}] debe ser un objeto")
        _ruta_interna(raiz, e.get("origen"), f"enlaces[{i}].origen")
        destinos = e.get("destinos")
        if not isinstance(destinos, list) or not destinos:
            raise ConfigInvalida(f"enlaces[{i}].destinos debe ser una lista no vacía")
        for j, d in enumerate(destinos):
            _ruta_interna(raiz, d, f"enlaces[{i}].destinos[{j}]")
    return enlaces


def pares(raiz: Path, enlaces: list[dict]):
    """(nombre, origen, carpeta destino, ruta del enlace) de cada enlace declarado."""
    for e in enlaces:
        origen = raiz / e["origen"]
        nombre_enlace = Path(e["origen"]).name
        for d in e["destinos"]:
            yield e.get("nombre", nombre_enlace), origen, raiz / d, raiz / d / nombre_enlace


def tam(n: int) -> str:
    """Unidad legible. Un insumo de 2 MB no se anuncia como "0.0 GB"."""
    for unidad, corte in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= corte:
            return f"{n/corte:,.1f} {unidad}"
    return f"{n} B"


def limpiar_basura(raiz: Path) -> int:
    n = 0
    for patron in BASURA:
        for b in list(raiz.rglob(patron)):
            try:
                shutil.rmtree(b) if b.is_dir() and not b.is_symlink() else b.unlink()
                n += 1
            except OSError:
                pass
    return n


def modo_revisar(raiz: Path, enlaces: list[dict]) -> int:
    print("\n  Estado de los enlaces\n")
    problemas = 0
    for _nombre, origen, _carpeta, enlace in pares(raiz, enlaces):
        rel = enlace.relative_to(raiz)
        # Sin enlace (retirado por `subir`) es el estado normal en la nube.
        if enlace.is_symlink():
            estado, mal = ("enlace OK", False) if enlace.exists() else ("ENLACE ROTO", True)
        elif enlace.is_dir():
            estado, mal = "CARPETA REAL — el sincronizador la copió", True
        elif enlace.exists():
            estado, mal = "ARCHIVO donde va el enlace — bajar falla", True
        else:
            estado, mal = "no está (retirado o nunca creado)", False
        problemas += mal
        print(f"    {estado:<42} {rel}")
        if not origen.exists():
            print(f"    {'FALTA EL ORIGEN':<42} {origen.relative_to(raiz)}")
            problemas += 1
    print()
    return 1 if problemas else 0


def modo_subir(raiz: Path, enlaces: list[dict]) -> int:
    print("\n  Preparando para SINCRONIZAR\n")
    print(f"    basura eliminada: {limpiar_basura(raiz)} elementos")

    quitados, ahorro = 0, 0
    for nombre, origen, carpeta, enlace in pares(raiz, enlaces):
        if not enlace.is_symlink():
            continue
        try:
            ahorro += sum(f.stat().st_size for f in origen.rglob("*") if f.is_file())
        except OSError:
            pass
        enlace.unlink()
        (carpeta / f"LEER_falta_{Path(enlace).name}.txt").write_text(
            NOTA.format(nombre=nombre, origen=origen.relative_to(raiz)), encoding="utf-8")
        quitados += 1

    print(f"    enlaces retirados: {quitados}"
          + (f" (se ahorran ~{tam(ahorro)})" if ahorro else ""))
    total = sum(f.stat().st_size for f in raiz.rglob("*")
                if f.is_file() and not f.is_symlink())
    print(f"    se sincronizarán:  {tam(total)}\n")
    print("    Recuerde NO sincronizar la carpeta de credenciales.\n")
    return 0


def modo_bajar(raiz: Path, enlaces: list[dict]) -> int:
    print("\n  Restaurando después de BAJAR\n")
    puestos = fallos = 0
    for _nombre, origen, carpeta, enlace in pares(raiz, enlaces):
        rel = enlace.relative_to(raiz)
        if not origen.is_dir():
            print(f"    ERROR    falta el origen: {origen.relative_to(raiz)}")
            fallos += 1
            continue
        if not carpeta.is_dir():
            print(f"    OMITIDO  {rel} (la carpeta destino no existe aquí)")
            continue
        if enlace.exists() and not enlace.is_symlink():
            que = "una CARPETA REAL" if enlace.is_dir() else "un ARCHIVO"
            print(f"    CUIDADO  {rel} es {que}, no un enlace.")
            print( "             Probablemente el sincronizador la copió. Revísela, bórrela"
                   " a mano y repita.")
            fallos += 1
            continue
        if enlace.is_symlink():
            enlace.unlink()
        enlace.symlink_to(os.path.relpath(origen, carpeta))
        aviso = carpeta / f"LEER_falta_{Path(enlace).name}.txt"
        if aviso.exists():
            aviso.unlink()
        if enlace.exists():
            print(f"    OK       {rel}")
            puestos += 1
        else:
            print(f"    ROTO     {rel}")
            fallos += 1

    print(f"\n    enlaces restaurados: {puestos}")
    if fallos:
        print(f"    con problema: {fallos}\n")
        return 1
    print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", choices=["revisar", "subir", "bajar"])
    ap.add_argument("--taller", default=None,
                    help="raíz del taller (por defecto, la carpeta que contiene herramientas/)")
    a = ap.parse_args()

    raiz = Path(a.taller).resolve() if a.taller else Path(__file__).resolve().parents[1]
    if not raiz.is_dir():
        print(f"  No es una carpeta: {raiz}", file=sys.stderr)
        return 2
    try:
        enlaces = cargar(raiz)
    except ConfigInvalida as e:
        print(f"  enlaces.json inválido: {e}", file=sys.stderr)
        return 2
    if not enlaces:
        return 0
    modos = {"revisar": modo_revisar, "subir": modo_subir, "bajar": modo_bajar}
    return modos[a.modo](raiz, enlaces)


if __name__ == "__main__":
    sys.exit(main())
