import os
import re
import shutil
import subprocess
import _test_subprocess_safety  # noqa: F401
import tempfile
import unittest
from pathlib import Path
import _no_real_sqlcl  # noqa: F401  (keeps tests away from a real SQLcl)
import fake_sqlcl
from fake_sqlcl import BASH


ROOT = Path(__file__).resolve().parents[1]
PWSH = _test_subprocess_safety.working_pwsh()
# On Windows both wrappers pass '%' for the every-object prefix '*', because the SQLcl launcher there
# expands an unquoted '*'; backup_db.sql treats the two the same.
EVERY_PREFIX = "%" if os.name == "nt" else "*"


def plain(text: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return re.sub(r"\s*\n\s*\|?\s*", " ", text)


class BackupDbCliTests(unittest.TestCase):
    def make_checkout(self, root: Path, powershell: bool) -> Path:
        scripts = root / "scripts"
        scripts.mkdir(parents=True)
        if powershell:
            names = (
                "backup_db.ps1",
                "backup_db.sql",
                "backup_manifest.py",
                "load_env.ps1",
                "check_db_target.ps1",
                "invoke_sqlcl.ps1", "resolve_python.ps1",
                "replace_mirror.ps1",
            )
        else:
            names = (
                "backup_db.sh",
                "backup_db.sql",
                "backup_manifest.py",
                "load_env.sh",
                "check_db_target.sh",
                "sqlcl_safe.sh",
                "replace_mirror.sh",
            )
        for name in names:
            shutil.copy2(ROOT / "scripts" / name, scripts / name)
        shutil.copy2(ROOT / "template-manifest.json", root / "template-manifest.json")
        if (ROOT / "scripts" / "template_release.ps1").exists():
            shutil.copy2(ROOT / "scripts" / "template_release.ps1", scripts / "template_release.ps1")

        if powershell:
            ps_spy = scripts / "replace_mirror.ps1"
            content = ps_spy.read_text(encoding="utf-8")
            marker = '$ErrorActionPreference = "Stop"\n'
            idx = content.find(marker) + len(marker)
            spy_code = "[System.IO.File]::WriteAllText((Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path '.replace_mirror_called'), 'called')\n"
            ps_spy.write_text(content[:idx] + spy_code + content[idx:], encoding="utf-8")
        else:
            sh_spy = scripts / "replace_mirror.sh"
            content = sh_spy.read_text(encoding="utf-8")
            sh_spy.write_text("#!/usr/bin/env bash\ntouch \"$(cd \"$(dirname \"$0\")/..\" && pwd -P)/.replace_mirror_called\"\n" + content[content.find("\n") + 1:], encoding="utf-8")

        env_text = (ROOT / ".env.example").read_text(encoding="utf-8")
        env_text = env_text.replace("TABLES_SCHEMA=DEMO", "TABLES_SCHEMA=DEMO$")
        env_text = env_text.replace("CODE_SCHEMA=DEMO", "CODE_SCHEMA=DEMO$")
        (root / ".env").write_text(env_text, encoding="utf-8")

        (root / "README.md").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Backup Test"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "backup@example.test"], check=True)
        subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed"], check=True)

        fake_bin = root / "bin"
        fake_bin.mkdir()
        fake_sql = fake_bin / "sql"
        fake_sql.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "cat > /dev/null\n"
            "# SQLcl prints this advisory for backup_db.sql's large LONG setting.\n"
            "printf '%s\\n' 'Warning: This LONG setting may cause Java memory problems.' 'It is recommended to reduce the setting and/or increase the memory available to Java.' 'FAKE SQLCL PROGRESS LINE'\n"
            "schema=\"$6\"\n"
            "scope=\"$7\"\n"
            "spool_schema=\"${11:-}\"\n"
            "tables_prefixes=\"${12:-}\"\n"
            "if [[ -n \"${FAKE_SQL_ARGS:-}\" ]]; then printf '%s|%s|%s|%s|%s\\n' \"$scope\" \"$schema\" \"${10:-}\" \"$tables_prefixes\" \"$spool_schema\" >> \"$FAKE_SQL_ARGS\"; fi\n"
            "if [[ -z \"$spool_schema\" || \"$spool_schema\" == *'$'* ]]; then\n"
            "  printf '%s\\n' 'SP2-0332: Cannot create spool file'\n"
            "  exit 0\n"
            "fi\n"
            "case \"$scope\" in\n"
            "  tables) scope_dir=tables; object=FAKE_TABLE ;;\n"
            "  code) scope_dir=views; object=FAKE_VIEW ;;\n"
            "  *) exit 4 ;;\n"
            "esac\n"
            "mkdir -p \"database/$spool_schema/$scope_dir\"\n"
            "printf 'CREATE FAKE OBJECT;\\n' > \"database/$spool_schema/$scope_dir/$object.sql\"\n"
            "# FAKE_SHARED_TRIGGER: both scopes write the same triggers/ file, which the merge must refuse.\n"
            "if [[ -n \"${FAKE_SHARED_TRIGGER:-}\" ]]; then\n"
            "  mkdir -p \"database/$spool_schema/triggers\"\n"
            "  printf 'CREATE SHARED TRIGGER;\\n' > \"database/$spool_schema/triggers/SHARED_TRG.sql\"\n"
            "fi\n"
            "# Mirrors the real driver's complete, alphabetically ordered type rows.\n"
            "if [[ -n \"${FAKE_MANIFEST_CODE:-}\" && \"$scope\" == code ]]; then\n"
            "  printf '%s' \"$FAKE_MANIFEST_CODE\" > \"database/$spool_schema/manifest-$scope.txt\"\n"
            "elif [[ -n \"${FAKE_MANIFEST_TABLES:-}\" && \"$scope\" == tables ]]; then\n"
            "  printf '%s' \"$FAKE_MANIFEST_TABLES\" > \"database/$spool_schema/manifest-$scope.txt\"\n"
            "elif [[ \"$scope\" == tables ]]; then\n"
            "  printf 'SEQUENCE=0\\nTABLE=1\\nTRIGGER=0\\n' > \"database/$spool_schema/manifest-$scope.txt\"\n"
            "else\n"
            "  printf 'FUNCTION=0\\nPACKAGE=0\\nPACKAGE BODY=0\\nPROCEDURE=0\\nSYNONYM=0\\nTRIGGER=0\\nVIEW=1\\n' > \"database/$spool_schema/manifest-$scope.txt\"\n"
            "fi\n",
            encoding="utf-8",
        )
        fake_sql.chmod(0o755)
        fake_sqlcl.add_launcher(fake_bin)
        return scripts / ("backup_db.ps1" if powershell else "backup_db.sh")

    def run_backup(
        self, script: Path, powershell: bool, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PATH"] = f"{script.parents[1] / 'bin'}{os.pathsep}{environment['PATH']}"
        environment["PROJECT_ENV_FILE"] = str(script.parents[1] / ".env")
        if extra_env:
            environment.update(extra_env)
        command = (
            [PWSH, "-NoProfile", "-File", str(script)]
            if powershell
            else [BASH, str(script)]
        )
        return subprocess.run(
            command,
            cwd=script.parents[1],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def assert_dollar_schema_mirror_installed(self, script: Path, output: str) -> None:
        mirror = script.parents[1] / "database" / "DEMO$"
        self.assertTrue(mirror.is_dir(), output)
        self.assertEqual((mirror / "manifest-tables.txt").read_text(encoding="utf-8"), "SEQUENCE=0\nTABLE=1\nTRIGGER=0\n")
        self.assertEqual(
            (mirror / "manifest-code.txt").read_text(encoding="utf-8"),
            "FUNCTION=0\nPACKAGE=0\nPACKAGE BODY=0\nPROCEDURE=0\nSYNONYM=0\nTRIGGER=0\nVIEW=1\n",
        )
        self.assertTrue((mirror / "tables" / "FAKE_TABLE.sql").is_file())
        self.assertTrue((mirror / "views" / "FAKE_VIEW.sql").is_file())
        # The LONG advisory is dropped; the rest of SQLcl's output is kept.
        self.assertNotIn("LONG setting may cause Java memory problems", output)
        self.assertNotIn("increase the memory available to Java", output)
        self.assertIn("FAKE SQLCL PROGRESS LINE", output)
        database_entries = [path.name for path in (script.parents[1] / "database").iterdir()]
        self.assertEqual(database_entries, ["DEMO$"])

    def seed_old_mirror(self, root: Path) -> tuple[Path, str]:
        old_mirror_dir = root / "database" / "DEMO$" / "tables"
        old_mirror_dir.mkdir(parents=True)
        old_file = old_mirror_dir / "OLD_TABLE.sql"
        old_content = "CREATE TABLE OLD_TABLE (ID NUMBER);\n"
        old_file.write_text(old_content, encoding="utf-8")
        (root / "database" / "DEMO$" / "manifest-tables.txt").write_text("TABLE=1\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "database"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed old mirror"], check=True)
        return old_file, old_content

    def assert_malformed_manifest_refused_and_old_mirror_preserved(self, powershell: bool) -> None:
        malformed_cases = [
            ("negative_count", "FUNCTION=0\nPACKAGE=0\nPACKAGE BODY=0\nPROCEDURE=0\nSYNONYM=0\nTRIGGER=-1\nVIEW=1\n"),
            ("duplicate_row", "FUNCTION=0\nPACKAGE=0\nPACKAGE BODY=0\nPROCEDURE=0\nSYNONYM=0\nTRIGGER=0\nVIEW=1\nTRIGGER=0\n"),
            ("unknown_type", "FUNCTION=0\nPACKAGE=0\nPACKAGE BODY=0\nPROCEDURE=0\nSYNONYM=0\nTRIGGER=0\nVIEW=1\nUNKNOWN=0\n"),
            ("missing_row", "FUNCTION=0\nPACKAGE=0\nPACKAGE BODY=0\nPROCEDURE=0\nSYNONYM=0\nVIEW=1\n"),
            ("count_mismatch", "FUNCTION=0\nPACKAGE=0\nPACKAGE BODY=0\nPROCEDURE=0\nSYNONYM=0\nTRIGGER=0\nVIEW=2\n"),
            ("non_ascii_separator", "FUNCTION=0\nPACKAGE=0\nPACKAGE BODY=0\nPROCEDURE=0\nSYNONYM=0\nTRIGGER=0\nVIEW=1\u0085\n"),
        ]
        for name, manifest_code in malformed_cases:
            with self.subTest(case=name):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    script = self.make_checkout(root, powershell=powershell)
                    old_file, old_content = self.seed_old_mirror(root)

                    result = self.run_backup(script, powershell=powershell, extra_env={"FAKE_MANIFEST_CODE": manifest_code})

                    self.assertEqual(result.returncode, 2, f"Failed on {name}: {result.stdout}\n{result.stderr}")
                    self.assertFalse((root / ".replace_mirror_called").exists(), f"replace_mirror was invoked on {name}")
                    self.assertEqual(old_file.read_text(encoding="utf-8"), old_content, f"Old mirror was overwritten on {name}")
                    self.assertFalse((root / "database" / "DEMO$" / "views").exists(), f"New views directory was installed on {name}")

    def assert_valid_manifest_installed(self, powershell: bool) -> None:
        valid_code = "\v\f\r\n" + "".join(
            f"\v{kind}\f=\v{count}\f\r\n"
            for kind, count in (("FUNCTION", 0), ("PACKAGE", 0), ("PACKAGE BODY", 0),
                                ("PROCEDURE", 0), ("SYNONYM", 0), ("TRIGGER", 0), ("VIEW", 1))
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = self.make_checkout(root, powershell=powershell)
            result = self.run_backup(script, powershell=powershell, extra_env={"FAKE_MANIFEST_CODE": valid_code})

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((root / ".replace_mirror_called").exists())
            self.assertTrue((root / "database" / "DEMO$" / "views" / "FAKE_VIEW.sql").is_file())

    def test_bash_backup_refuses_malformed_manifest_and_preserves_old_mirror(self) -> None:
        self.assert_malformed_manifest_refused_and_old_mirror_preserved(powershell=False)

    @unittest.skipUnless(PWSH, "PowerShell Core is not installed")
    def test_powershell_backup_refuses_malformed_manifest_and_preserves_old_mirror(self) -> None:
        self.assert_malformed_manifest_refused_and_old_mirror_preserved(powershell=True)

    def test_bash_backup_accepts_valid_crlf_and_whitespace_manifest(self) -> None:
        self.assert_valid_manifest_installed(powershell=False)

    @unittest.skipUnless(PWSH, "PowerShell Core is not installed")
    def test_powershell_backup_accepts_valid_crlf_and_whitespace_manifest(self) -> None:
        self.assert_valid_manifest_installed(powershell=True)

    def test_bash_backup_spools_safely_then_installs_original_dollar_schema_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            script = self.make_checkout(Path(temporary), powershell=False)

            result = self.run_backup(script, powershell=False)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assert_dollar_schema_mirror_installed(script, result.stdout + result.stderr)

    @unittest.skipUnless(PWSH, "PowerShell Core is not installed")
    def test_powershell_backup_spools_safely_then_installs_original_dollar_schema_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            script = self.make_checkout(Path(temporary), powershell=True)

            result = self.run_backup(script, powershell=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assert_dollar_schema_mirror_installed(script, result.stdout + result.stderr)

    def test_sql_driver_uses_wrapper_supplied_safe_schema_directory(self) -> None:
        script = (ROOT / "scripts" / "backup_db.sql").read_text(encoding="utf-8")
        self.assertIn("DEFINE spool_schema = '&6'", script)
        self.assertIn("SPOOL database/&&spool_schema/", script)
        self.assertNotIn("SPOOL database/&&target_schema/", script)


    def test_sql_driver_mirrors_private_synonyms_and_counts_them(self) -> None:
        script = (ROOT / "scripts" / "backup_db.sql").read_text(encoding="utf-8")
        self.assertIn("SPOOL database/&&spool_schema/synonyms/", script)
        self.assertIn("GET_DDL(''SYNONYM''", script)
        self.assertIn("SELECT 'SYNONYM', 'code', COUNT(*)", script)
        self.assertIn("'VIEW', 'PACKAGE', 'PACKAGE BODY', 'PROCEDURE', 'FUNCTION', 'TRIGGER', 'SYNONYM'", script)
        # Only the schema's own (private) synonyms: filtered by owner, never PUBLIC.
        self.assertIn(
            "AND objects_to_export.owner = UPPER('&&target_schema')\n  AND objects_to_export.object_type = 'SYNONYM'",
            script,
        )

    # A committed DEMO$ mirror holding every output of both scopes, plus an ORDS export. triggers/ is written by both
    # scopes: a tables-only run must not carry the committed trigger over, and a both-scopes run replaces it.
    COMMITTED_MIRROR = {
        "tables/OLD_TABLE.sql": "CREATE TABLE OLD_TABLE (ID NUMBER);\n",
        "manifest-tables.txt": "TABLE=1\n",
        "triggers/OLD_TRIGGER.sql": "CREATE TRIGGER OLD_TRIGGER;\n",
        "views/OLD_VIEW.sql": "CREATE VIEW OLD_VIEW AS SELECT 1 AS ID FROM dual;\n",
        "packages/OLD_PACKAGE.sql": "CREATE PACKAGE OLD_PACKAGE AS END;\n",
        "manifest-code.txt": "FUNCTION=0\nPACKAGE=1\nPACKAGE BODY=0\nPROCEDURE=0\nSYNONYM=0\nTRIGGER=0\nVIEW=1\n",
        "ords/OLD_MODULE.json": '{"module": "old"}\n',
    }
    # What the fake SQLcl in make_checkout writes for each scope.
    TABLES_OUTPUT = {
        "tables/FAKE_TABLE.sql": "CREATE FAKE OBJECT;\n",
        "manifest-tables.txt": "SEQUENCE=0\nTABLE=1\nTRIGGER=0\n",
    }
    CODE_OUTPUT = {
        "views/FAKE_VIEW.sql": "CREATE FAKE OBJECT;\n",
        "manifest-code.txt": "FUNCTION=0\nPACKAGE=0\nPACKAGE BODY=0\nPROCEDURE=0\nSYNONYM=0\nTRIGGER=0\nVIEW=1\n",
    }

    def committed(self, *paths: str) -> dict[str, str]:
        return {path: self.COMMITTED_MIRROR[path] for path in paths}

    def backup_over_committed_mirror(
        self,
        powershell: bool,
        env_changes: dict[str, str],
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Run the backup over a committed DEMO$ mirror with the real replace helper; return the mirror it left."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = self.make_checkout(root, powershell=powershell)
            # make_checkout installs a spy replace_mirror; these tests need the real one.
            helper = "replace_mirror.ps1" if powershell else "replace_mirror.sh"
            shutil.copy2(ROOT / "scripts" / helper, root / "scripts" / helper)
            env_path = root / ".env"
            env_text = env_path.read_text(encoding="utf-8")
            for old, new in env_changes.items():
                self.assertIn(old, env_text)
                env_text = env_text.replace(old, new)
            env_path.write_text(env_text, encoding="utf-8")
            mirror = root / "database" / "DEMO$"
            for relative, text in self.COMMITTED_MIRROR.items():
                target = mirror / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "database"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed committed mirror"], check=True)

            result = self.run_backup(script, powershell=powershell, extra_env=extra_env)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(sorted(entry.name for entry in (root / "database").iterdir()), ["DEMO$"])
            return {
                path.relative_to(mirror).as_posix(): path.read_text(encoding="utf-8")
                for path in mirror.rglob("*")
                if path.is_file()
            }

    def assert_tables_only_run_keeps_committed_code_scope(self, powershell: bool) -> None:
        # PROJECT_SCHEMA narrows the run to DEMO$ tables; CODE lists another owner, which this run does not refresh.
        files = self.backup_over_committed_mirror(
            powershell,
            env_changes={
                "CODE_SCHEMA=DEMO$": "CODE_SCHEMA=CODEONLY$",
                "CODE_EXPECTED_USER=DEMO": "CODE_EXPECTED_USER=CODEONLY$",
                "CODE_SQLCL_CONNECTION=docker-demo": "CODE_SQLCL_CONNECTION=docker-codeonly",
            },
            extra_env={"PROJECT_SCHEMA": "DEMO$"},
        )
        # The tables scope is replaced whole; the committed code scope, its manifest and the ORDS export survive.
        self.assertEqual(
            files,
            {
                **self.TABLES_OUTPUT,
                **self.committed("views/OLD_VIEW.sql", "packages/OLD_PACKAGE.sql", "manifest-code.txt",
                                 "ords/OLD_MODULE.json"),
            },
        )

    def assert_code_only_run_keeps_committed_tables_scope(self, powershell: bool) -> None:
        # PROJECT_SCHEMA narrows the run to DEMO$ code; TABLES lists another owner, which this run does not refresh.
        files = self.backup_over_committed_mirror(
            powershell,
            env_changes={
                "TABLES_SCHEMA=DEMO$": "TABLES_SCHEMA=TABLESONLY$",
                "TABLES_EXPECTED_USER=DEMO": "TABLES_EXPECTED_USER=TABLESONLY$",
                "TABLES_SQLCL_CONNECTION=docker-demo": "TABLES_SQLCL_CONNECTION=docker-tablesonly",
            },
            extra_env={"PROJECT_SCHEMA": "DEMO$"},
        )
        # The code scope is replaced whole; the committed tables scope, its manifest and the ORDS export survive.
        self.assertEqual(
            files,
            {
                **self.CODE_OUTPUT,
                **self.committed("tables/OLD_TABLE.sql", "manifest-tables.txt", "ords/OLD_MODULE.json"),
            },
        )

    def assert_both_scopes_replace_committed_mirror(self, powershell: bool) -> None:
        files = self.backup_over_committed_mirror(powershell, env_changes={})
        # Both scopes ran, so their stale files (OLD_TABLE, OLD_VIEW, OLD_PACKAGE) are gone; the ORDS export is carried over.
        self.assertEqual(
            files,
            {**self.TABLES_OUTPUT, **self.CODE_OUTPUT, **self.committed("ords/OLD_MODULE.json")},
        )

    def test_bash_tables_only_run_keeps_committed_code_scope_and_manifest(self) -> None:
        self.assert_tables_only_run_keeps_committed_code_scope(powershell=False)

    @unittest.skipUnless(PWSH, "PowerShell Core is not installed")
    def test_powershell_tables_only_run_keeps_committed_code_scope_and_manifest(self) -> None:
        self.assert_tables_only_run_keeps_committed_code_scope(powershell=True)

    def test_bash_code_only_run_keeps_committed_tables_scope_and_manifest(self) -> None:
        self.assert_code_only_run_keeps_committed_tables_scope(powershell=False)

    @unittest.skipUnless(PWSH, "PowerShell Core is not installed")
    def test_powershell_code_only_run_keeps_committed_tables_scope_and_manifest(self) -> None:
        self.assert_code_only_run_keeps_committed_tables_scope(powershell=True)

    def test_bash_both_scopes_run_replaces_both_mirrors_and_their_stale_files(self) -> None:
        self.assert_both_scopes_replace_committed_mirror(powershell=False)

    @unittest.skipUnless(PWSH, "PowerShell Core is not installed")
    def test_powershell_both_scopes_run_replaces_both_mirrors_and_their_stale_files(self) -> None:
        self.assert_both_scopes_replace_committed_mirror(powershell=True)

    def sql_calls(self, log: Path) -> dict[str, list[str]]:
        # One line per SQLcl call: scope|schema|prefixes|tables-prefixes|spool directory.
        return {line.split("|")[0]: line.split("|") for line in log.read_text(encoding="utf-8").splitlines()}

    def assert_both_profiles_pass_the_seventh_argument(self, powershell: bool) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = self.make_checkout(root, powershell=powershell)
            env_path = root / ".env"
            env_path.write_text(env_path.read_text(encoding="utf-8").replace("TABLES_PREFIXES=*", "TABLES_PREFIXES=ABSH_"), encoding="utf-8")
            log = root / "sql-calls.txt"
            result = self.run_backup(script, powershell=powershell, extra_env={"FAKE_SQL_ARGS": str(log)})

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            calls = self.sql_calls(log)
            # DEMO$ is in both profiles: the tables scope and the code scope both get TABLES_PREFIXES.
            self.assertEqual(calls["tables"][1:4], ["DEMO$", "ABSH_", "ABSH_"])
            self.assertEqual(calls["code"][1:4], ["DEMO$", EVERY_PREFIX, "ABSH_"])
            # Each scope spools into its own staging directory.
            self.assertTrue(calls["tables"][4].endswith("-tables"), calls["tables"])
            self.assertTrue(calls["code"][4].endswith("-code"), calls["code"])

    def test_bash_driver_receives_tables_prefixes_as_seventh_argument(self) -> None:
        self.assert_both_profiles_pass_the_seventh_argument(powershell=False)

    @unittest.skipUnless(PWSH, "PowerShell Core is not installed")
    def test_powershell_driver_receives_tables_prefixes_as_seventh_argument(self) -> None:
        self.assert_both_profiles_pass_the_seventh_argument(powershell=True)

    def assert_code_only_schema_passes_a_dash(self, powershell: bool) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = self.make_checkout(root, powershell=powershell)
            env_path = root / ".env"
            env_text = env_path.read_text(encoding="utf-8")
            for old, new in {
                "TABLES_SCHEMA=DEMO$": "TABLES_SCHEMA=TABLESONLY$",
                "TABLES_EXPECTED_USER=DEMO": "TABLES_EXPECTED_USER=TABLESONLY$",
                "TABLES_SQLCL_CONNECTION=docker-demo": "TABLES_SQLCL_CONNECTION=docker-tablesonly",
            }.items():
                self.assertIn(old, env_text)
                env_text = env_text.replace(old, new)
            env_path.write_text(env_text, encoding="utf-8")
            log = root / "sql-calls.txt"
            result = self.run_backup(script, powershell=powershell, extra_env={"FAKE_SQL_ARGS": str(log)})

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            calls = self.sql_calls(log)
            # DEMO$ has no tables scope in this run, so its code scope keeps every trigger ('-').
            self.assertEqual(calls["code"][1:4], ["DEMO$", EVERY_PREFIX, "-"])
            self.assertEqual(calls["tables"][1], "TABLESONLY$")

    def test_bash_code_only_schema_passes_dash_as_tables_prefixes(self) -> None:
        self.assert_code_only_schema_passes_a_dash(powershell=False)

    @unittest.skipUnless(PWSH, "PowerShell Core is not installed")
    def test_powershell_code_only_schema_passes_dash_as_tables_prefixes(self) -> None:
        self.assert_code_only_schema_passes_a_dash(powershell=True)

    def assert_shared_trigger_refused_and_mirror_kept(self, powershell: bool) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = self.make_checkout(root, powershell=powershell)
            old_file, old_content = self.seed_old_mirror(root)
            result = self.run_backup(
                script,
                powershell=powershell,
                extra_env={
                    "FAKE_SHARED_TRIGGER": "1",
                    # Each scope's manifest counts the shared trigger, so only the merge can refuse it.
                    "FAKE_MANIFEST_TABLES": "SEQUENCE=0\nTABLE=1\nTRIGGER=1\n",
                    "FAKE_MANIFEST_CODE": "FUNCTION=0\nPACKAGE=0\nPACKAGE BODY=0\nPROCEDURE=0\nSYNONYM=0\nTRIGGER=1\nVIEW=1\n",
                },
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn(
                "both the tables and code exports wrote triggers/SHARED_TRG.sql for DEMO$; the mirror was not replaced",
                plain(result.stderr),
            )
            self.assertFalse((root / ".replace_mirror_called").exists(), "replace_mirror was invoked")
            self.assertEqual(old_file.read_text(encoding="utf-8"), old_content, "the committed mirror was overwritten")
            self.assertFalse((root / "database" / "DEMO$" / "triggers").exists())

    def test_bash_trigger_written_by_both_scopes_is_refused_and_mirror_kept(self) -> None:
        self.assert_shared_trigger_refused_and_mirror_kept(powershell=False)

    @unittest.skipUnless(PWSH, "PowerShell Core is not installed")
    def test_powershell_trigger_written_by_both_scopes_is_refused_and_mirror_kept(self) -> None:
        self.assert_shared_trigger_refused_and_mirror_kept(powershell=True)

    def assert_tables_only_run_keeps_committed_code_triggers_out_of_the_mirror(self, powershell: bool) -> None:
        # The tables scope owns triggers/: a tables-only run installs its own triggers/ and never the committed one.
        files = self.backup_over_committed_mirror(
            powershell,
            env_changes={
                "CODE_SCHEMA=DEMO$": "CODE_SCHEMA=CODEONLY$",
                "CODE_EXPECTED_USER=DEMO": "CODE_EXPECTED_USER=CODEONLY$",
                "CODE_SQLCL_CONNECTION=docker-demo": "CODE_SQLCL_CONNECTION=docker-codeonly",
            },
            extra_env={"PROJECT_SCHEMA": "DEMO$"},
        )
        self.assertNotIn("triggers/OLD_TRIGGER.sql", files)
        self.assertNotIn("triggers", {path.split("/")[0] for path in files})

    def test_bash_tables_only_run_does_not_carry_over_the_committed_triggers_folder(self) -> None:
        self.assert_tables_only_run_keeps_committed_code_triggers_out_of_the_mirror(powershell=False)

    @unittest.skipUnless(PWSH, "PowerShell Core is not installed")
    def test_powershell_tables_only_run_does_not_carry_over_the_committed_triggers_folder(self) -> None:
        self.assert_tables_only_run_keeps_committed_code_triggers_out_of_the_mirror(powershell=True)


if __name__ == "__main__":
    unittest.main()
