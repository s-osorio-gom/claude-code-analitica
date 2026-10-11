"""Pruebas del auditor: la plantilla pasa y un taller roto a propósito FALLA.

    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AUDITOR = REPO / "herramientas" / "auditar_taller.py"
PLANTILLA = REPO / "plantilla"

sys.path.insert(0, str(REPO / "herramientas"))
import auditar_taller  # noqa: E402


def correr(ruta: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(AUDITOR), str(ruta), "--detalle"],
                          capture_output=True, text=True, encoding="utf-8")


def estados(ruta: Path) -> dict[str, str]:
    return {f[0]: f[2] for f in auditar_taller.auditar(ruta).filas}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.taller = self.tmp / "taller"
        shutil.copytree(PLANTILLA, self.taller)

    def tearDown(self):
        self._tmp.cleanup()

    def proyecto(self, nombre: str = "ventas") -> Path:
        pr = self.taller / "area" / "proyectos" / nombre
        shutil.copytree(self.taller / "area" / "proyectos" / "_plantilla", pr)
        indice = self.taller / "EMPIECE_AQUI.md"
        indice.write_text(indice.read_text(encoding="utf-8") + f"\n| `{nombre}` |\n",
                          encoding="utf-8")
        return pr


class PlantillaLimpia(Base):
    def test_la_plantilla_pasa(self):
        r = correr(PLANTILLA)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 chequeos críticos en falla", r.stdout)

    def test_copia_con_proyecto_bien_hecho_pasa(self):
        pr = self.proyecto()
        (pr / "4_tecnico" / "procesar.py").write_text(
            "from pathlib import Path\nBASE = Path(__file__).resolve().parents[1]\n",
            encoding="utf-8")
        self.assertEqual(correr(self.taller).returncode, 0)

    def test_taller_dentro_de_una_carpeta_ignorada_no_se_salta(self):
        # Antes el filtro miraba la ruta ABSOLUTA: un taller en .../venv/ o
        # .../.claude/ quedaba ignorado entero y siempre "pasaba".
        destino = self.tmp / "venv" / "taller"
        shutil.copytree(self.taller, destino)
        pr = destino / "area" / "proyectos" / "_plantilla"
        (pr / "4_tecnico" / "malo.py").write_text("def (:\n", encoding="utf-8")
        e = estados(destino)
        self.assertEqual(e["Scripts de Python que compilan"], "FALLA")
        self.assertEqual(e["Proyectos con la estructura completa"], "OK")


class TallerRoto(Base):
    """Cada regla crítica rota por separado debe hacer fallar al auditor."""

    def assertFalla(self, chequeo: str):
        e = estados(self.taller)
        self.assertEqual(e[chequeo], "FALLA", e)
        r = correr(self.taller)
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_falta_una_carpeta(self):
        pr = self.proyecto()
        shutil.rmtree(pr / "2_trabajo")
        self.assertFalla("Proyectos con la estructura completa")

    def test_falta_leeme(self):
        (self.proyecto() / "LEEME.md").unlink()
        self.assertFalla("Proyectos con LEEME.md")

    def test_ruta_absoluta_posix(self):
        (self.proyecto() / "4_tecnico" / "a.py").write_text(
            'BASE = "/Users/alguien/taller"\n', encoding="utf-8")
        self.assertFalla("Código sin rutas absolutas")

    def test_ruta_absoluta_windows(self):
        (self.proyecto() / "4_tecnico" / "a.py").write_text(
            'BASE = r"C:\\datos\\taller"\n', encoding="utf-8")
        self.assertFalla("Código sin rutas absolutas")

    def test_script_que_no_compila(self):
        (self.proyecto() / "4_tecnico" / "a.py").write_text("def (:\n", encoding="utf-8")
        self.assertFalla("Scripts de Python que compilan")

    def test_binario_con_extension_py_no_rompe_el_auditor(self):
        (self.proyecto() / "4_tecnico" / "b.py").write_bytes(b"\x00\xff\xfe\x89PNG")
        self.assertFalla("Scripts de Python que compilan")
        self.assertNotIn("b.py:None", correr(self.taller).stdout)

    def test_archivo_no_utf8_no_rompe_el_auditor(self):
        (self.proyecto() / "4_tecnico" / "latin1.py").write_bytes(
            "# comentario en latin-1: año\nx = 1\n".encode("latin-1"))
        r = correr(self.taller)
        self.assertNotIn("Traceback", r.stderr)

    def test_credencial_por_nombre(self):
        (self.proyecto() / "4_tecnico" / ".env").write_text("X=1\n", encoding="utf-8")
        self.assertFalla("Sin credenciales dentro del taller")

    def test_credencial_por_contenido(self):
        llave = "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIabc\n"
        (self.proyecto() / "4_tecnico" / "conectar.py").write_text(
            f"K = '''{llave}'''\n", encoding="utf-8")
        self.assertFalla("Sin credenciales dentro del taller")

    def test_api_key_en_settings_local_de_claude(self):
        # .claude/ no entra a los demás chequeos, pero sí al de credenciales.
        llave = "sk-ant-" + "api03-" + "x" * 40
        (self.taller / "area" / ".claude" / "settings.local.json").write_text(
            json.dumps({"env": {"ANTHROPIC_API_KEY": llave}}), encoding="utf-8")
        self.assertFalla("Sin credenciales dentro del taller")

    def test_credencial_por_nombre_dentro_de_claude(self):
        (self.taller / "area" / ".claude" / "credentials.json").write_text(
            "{}", encoding="utf-8")
        self.assertFalla("Sin credenciales dentro del taller")

    def test_nombres_de_agente_o_hook_no_son_credenciales(self):
        cl = self.taller / "area" / ".claude"
        (cl / "agents" / "secret-scanner.md").write_text(
            "---\nname: secret-scanner\ndescription: Busca secretos en el código\n"
            "tools: Read, Grep\n---\nRevisa.\n", encoding="utf-8")
        (cl / "hooks").mkdir()
        (cl / "hooks" / "check_password.py").write_text("import sys\n", encoding="utf-8")
        e = estados(self.taller)
        self.assertEqual(e["Sin credenciales dentro del taller"], "OK", e)
        self.assertEqual(correr(self.taller).returncode, 0)

    def test_credencial_en_un_worktree_de_claude(self):
        # .claude/worktrees/<x>/ es una copia de trabajo dentro del taller, y
        # .worktreeinclude copia ahí la .env. (Antes una prueba exigía «OK» aquí.)
        wt = self.taller / "area" / ".claude" / "worktrees" / "rama" / "4_tecnico"
        wt.mkdir(parents=True)
        (wt / ".env").write_text("X=1\n", encoding="utf-8")
        self.assertFalla("Sin credenciales dentro del taller")

    @unittest.skipIf(os.name == "nt", "enlaces simbólicos requieren permisos en Windows")
    def test_credenciales_detras_de_un_enlace_en_claude(self):
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        (fuera / "local.json").write_text(
            json.dumps({"env": {"ANTHROPIC_API_KEY": "sk-ant-" + "y" * 40}}), encoding="utf-8")
        (fuera / "cred.json").write_text("{}", encoding="utf-8")
        cl = self.taller / "area" / ".claude"
        for enlace, destino in (("settings.local.json", "local.json"),
                                ("credentials.json", "cred.json")):
            with self.subTest(enlace=enlace):
                (cl / enlace).symlink_to(fuera / destino)
                self.assertFalla("Sin credenciales dentro del taller")
                self.assertIn(f"area/.claude/{enlace}",
                              correr(self.taller).stdout.replace("\\", "/"))
                (cl / enlace).unlink()

    @unittest.skipIf(os.name == "nt", "enlaces simbólicos requieren permisos en Windows")
    def test_enlace_roto(self):
        (self.proyecto() / "1_datos_originales" / "mgn").symlink_to("no_existe")
        self.assertFalla("Enlaces simbólicos que resuelven")

    @unittest.skipIf(os.name == "nt", "Windows no deja crear estos nombres")
    def test_nombre_que_windows_rechaza(self):
        (self.proyecto() / "2_trabajo" / "base ").mkdir()
        self.assertFalla("Nombres compatibles con Drive y Windows")

    def test_settings_json_invalido(self):
        (self.taller / "area" / ".claude" / "settings.json").write_text(
            '{"permissions": {"deny": [}', encoding="utf-8")
        self.assertFalla("Configuración de Claude Code válida")

    def test_regla_write_que_claude_code_ignora(self):
        cfg = self.taller / "area" / ".claude" / "settings.json"
        datos = json.loads(cfg.read_text(encoding="utf-8"))
        datos["permissions"]["ask"].append("Write(./**/3_entregable/**)")
        cfg.write_text(json.dumps(datos), encoding="utf-8")
        self.assertFalla("Configuración de Claude Code válida")

    def test_reglas_notebookedit_y_multiedit_que_claude_code_ignora(self):
        cfg = self.taller / "area" / ".claude" / "settings.json"
        original = cfg.read_text(encoding="utf-8")
        for regla in ("NotebookEdit(./**/2_trabajo/**)", "MultiEdit(./**/3_entregable/**)"):
            with self.subTest(regla=regla):
                datos = json.loads(original)
                datos["permissions"]["ask"].append(regla)
                cfg.write_text(json.dumps(datos), encoding="utf-8")
                self.assertFalla("Configuración de Claude Code válida")

    def test_sin_archivo_indice(self):
        # Sin EMPIECE_AQUI.md, INDICE.md ni README.md es falla, no solo aviso.
        (self.taller / "EMPIECE_AQUI.md").unlink()
        self.assertFalla("El índice existe y nombra los proyectos")

    def test_regla_glob_que_claude_code_ignora(self):
        cfg = self.taller / "area" / ".claude" / "settings.json"
        datos = json.loads(cfg.read_text(encoding="utf-8"))
        datos["permissions"]["deny"].append("Glob(./**/credentials/**)")
        cfg.write_text(json.dumps(datos), encoding="utf-8")
        self.assertFalla("Configuración de Claude Code válida")
        r = correr(self.taller)
        self.assertIn("use Read(...)", r.stdout)

    def test_herramienta_sin_ruta_no_es_falla(self):
        # "Write" o "Glob" solos sí se aplican, a nivel de herramienta.
        cfg = self.taller / "area" / ".claude" / "settings.json"
        datos = json.loads(cfg.read_text(encoding="utf-8"))
        datos["permissions"]["deny"] += ["Write", "Glob"]
        cfg.write_text(json.dumps(datos), encoding="utf-8")
        self.assertEqual(estados(self.taller)["Configuración de Claude Code válida"], "OK")

    def test_agente_sin_frontmatter(self):
        (self.taller / "area" / ".claude" / "agents" / "suelto.md").write_text(
            "Eres un agente sin cabecera.\n", encoding="utf-8")
        self.assertFalla("Configuración de Claude Code válida")

    def test_agente_sin_description(self):
        (self.taller / "area" / ".claude" / "agents" / "corto.md").write_text(
            "---\nname: corto\ntools: Read\n---\nHola\n", encoding="utf-8")
        self.assertFalla("Configuración de Claude Code válida")

    def test_agente_roto_en_subcarpeta(self):
        sub = self.taller / "area" / ".claude" / "agents" / "finanzas"
        sub.mkdir()
        (sub / "suelto.md").write_text("Sin cabecera.\n", encoding="utf-8")
        self.assertFalla("Configuración de Claude Code válida")

    def test_name_entre_comillas_es_valido(self):
        agentes = self.taller / "area" / ".claude" / "agents"
        (agentes / "citado.md").write_text(
            '---\nname: "data-engineer-b"\ndescription: \'Con comillas\'\n---\nHola\n',
            encoding="utf-8")
        self.assertEqual(estados(self.taller)["Configuración de Claude Code válida"], "OK")

    def test_name_que_empieza_con_guion(self):
        # Claude Code se salta ese agente (solo lo dice en el log de --debug).
        (self.taller / "area" / ".claude" / "agents" / "guion.md").write_text(
            "---\nname: -guion\ndescription: x\n---\nHola\n", encoding="utf-8")
        self.assertFalla("Configuración de Claude Code válida")

    def test_dos_agentes_con_el_mismo_name(self):
        agentes = self.taller / "area" / ".claude" / "agents"
        shutil.copy(agentes / "data-engineer.md", agentes / "data-engineer-v2.md")
        self.assertFalla("Configuración de Claude Code válida")
        self.assertIn("repetido", correr(self.taller).stdout)

    def test_comando_con_frontmatter_sin_cerrar(self):
        (self.taller / "area" / ".claude" / "commands" / "abierto.md").write_text(
            "---\ndescription: nunca cierra\n\nHaz algo\n", encoding="utf-8")
        self.assertFalla("Configuración de Claude Code válida")


SIN_PERMISOS = os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0)


@unittest.skipIf(SIN_PERMISOS, "chmod no quita la lectura en Windows ni a root")
class Ilegible(Base):
    """Lo que no se puede leer no rompe el auditor ni se calla: avisa."""

    def setUp(self):
        super().setUp()
        self.cerradas: list[Path] = []

    def tearDown(self):
        for p in self.cerradas:  # devolver el permiso antes de borrar la carpeta temporal
            p.chmod(0o755)
        super().tearDown()

    def cerrar(self, p: Path):
        p.chmod(0)
        self.cerradas.append(p)

    def test_carpeta_claude_ilegible(self):
        self.cerrar(self.taller / "area" / ".claude")
        r = correr(self.taller)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(estados(self.taller)["Carpetas que se pudieron leer"], "AVISO")
        self.assertIn("area/.claude — sin permiso de lectura", r.stdout.replace("\\", "/"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_indice_ilegible_es_falla_sin_traza(self):
        self.cerrar(self.taller / "EMPIECE_AQUI.md")
        r = correr(self.taller)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("EMPIECE_AQUI.md no se puede leer", r.stdout)

    def test_proyecto_ilegible(self):
        self.cerrar(self.proyecto("cerrado"))
        r = correr(self.taller)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("cerrado — sin permiso de lectura", r.stdout)


class Avisos(Base):
    """Lo no crítico avisa pero no cambia el código de salida."""

    def test_nombre_flojo_solo_avisa(self):
        (self.proyecto() / "3_entregable" / "reporte final.xlsx").write_bytes(b"x")
        self.assertEqual(estados(self.taller)["Nombres sin 'final', 'copia' ni 'nuevo'"],
                         "AVISO")
        self.assertEqual(correr(self.taller).returncode, 0)

    def test_carpeta_extra_solo_avisa(self):
        (self.proyecto() / "otros").mkdir()
        self.assertEqual(estados(self.taller)["Proyectos sin carpetas fuera de las cuatro"],
                         "AVISO")
        self.assertEqual(correr(self.taller).returncode, 0)


class Entrada(unittest.TestCase):
    def test_carpeta_sin_proyectos_no_pasa(self):
        # Una ruta equivocada (otro repositorio con README.md) no debe dar verde.
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "README.md").write_text("# otro repo\n", encoding="utf-8")
            r = correr(Path(d))
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("ningún proyecto", r.stdout)
            fila = next(x for x in r.stdout.splitlines() if "estructura completa" in x)
            self.assertTrue(fila.rstrip().endswith("0 / 0"), fila)

    def test_ruta_inexistente(self):
        r = correr(Path(tempfile.gettempdir()) / "no-existe-este-taller-123")
        self.assertEqual(r.returncode, 2)
        self.assertIn("No es una carpeta", r.stderr)

    def test_ruta_que_es_un_archivo(self):
        r = correr(AUDITOR)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
