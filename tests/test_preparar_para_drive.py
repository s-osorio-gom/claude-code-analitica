"""Pruebas de preparar_para_drive.py: ciclo subir/bajar y configuración inválida.

    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "herramientas" / "preparar_para_drive.py"


def correr(taller: Path, modo: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), modo, "--taller", str(taller)],
                          capture_output=True, text=True, encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.taller = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def config(self, datos) -> None:
        texto = datos if isinstance(datos, str) else json.dumps(datos)
        (self.taller / "enlaces.json").write_text(texto, encoding="utf-8")


@unittest.skipIf(os.name == "nt", "enlaces simbólicos requieren permisos en Windows")
class Ciclo(Base):
    def test_subir_y_bajar(self):
        origen = self.taller / "proyectos" / "mapas" / "1_datos_originales" / "MGN"
        origen.mkdir(parents=True)
        (origen / "capa.txt").write_text("x" * 2000, encoding="utf-8")
        destino = self.taller / "proyectos" / "cobertura" / "1_datos_originales"
        destino.mkdir(parents=True)
        self.config({"enlaces": [{
            "nombre": "MGN",
            "origen": "proyectos/mapas/1_datos_originales/MGN",
            "destinos": ["proyectos/cobertura/1_datos_originales"]}]})

        r = correr(self.taller, "bajar")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        enlace = destino / "MGN"
        self.assertTrue(enlace.is_symlink() and enlace.exists())
        self.assertEqual(correr(self.taller, "revisar").returncode, 0)

        r = correr(self.taller, "subir")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(enlace.is_symlink())
        self.assertTrue((destino / "LEER_falta_MGN.txt").is_file())
        self.assertTrue((origen / "capa.txt").is_file(), "subir no debe tocar el origen")

        self.assertEqual(correr(self.taller, "bajar").returncode, 0)
        self.assertTrue(enlace.is_symlink())
        self.assertFalse((destino / "LEER_falta_MGN.txt").exists())

    def test_archivo_donde_va_el_enlace_es_problema(self):
        (self.taller / "a" / "MGN").mkdir(parents=True)
        (self.taller / "b").mkdir()
        (self.taller / "b" / "MGN").write_text("no soy un enlace", encoding="utf-8")
        self.config({"enlaces": [{"origen": "a/MGN", "destinos": ["b"]}]})
        self.assertEqual(correr(self.taller, "revisar").returncode, 1)
        r = correr(self.taller, "bajar")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("un ARCHIVO", r.stdout)
        self.assertEqual((self.taller / "b" / "MGN").read_text(encoding="utf-8"),
                         "no soy un enlace", "bajar no debe borrar lo que encuentra")

    def test_bajar_sin_origen_falla(self):
        (self.taller / "b").mkdir()
        self.config({"enlaces": [{"origen": "a/MGN", "destinos": ["b"]}]})
        self.assertEqual(correr(self.taller, "bajar").returncode, 1)


class ConfigInvalida(Base):
    def assertInvalida(self, datos):
        self.config(datos)
        r = correr(self.taller, "revisar")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("enlaces.json inválido", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_json_roto(self):
        self.assertInvalida('{"enlaces": [')

    def test_falta_destinos(self):
        self.assertInvalida({"enlaces": [{"origen": "a"}]})

    def test_ruta_absoluta(self):
        self.assertInvalida({"enlaces": [{"origen": "/etc", "destinos": ["b"]}]})

    def test_ruta_que_se_sale_del_taller(self):
        self.assertInvalida({"enlaces": [{"origen": "a", "destinos": ["../../fuera"]}]})

    def test_sin_config_no_es_error(self):
        self.assertEqual(correr(self.taller, "revisar").returncode, 0)

    def test_taller_inexistente(self):
        r = correr(self.taller / "no-existe", "revisar")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
