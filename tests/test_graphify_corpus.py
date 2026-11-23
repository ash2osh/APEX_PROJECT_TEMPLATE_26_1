#!/usr/bin/env python3
"""Verify the Graphify corpus remains limited to APEX domain sources."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import _test_subprocess_safety  # noqa: F401
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parent.parent
IGNORE_PATH = REPO_ROOT / ".graphifyignore"
EXTRACTOR_PATH = REPO_ROOT / "scripts" / "graphify_apexlang_extractor.py"

INCLUDED_PATHS = (
    "apps/DEMO/102/pages/p00004-home.apx",
    "apps/DEMO/102/shared-components/lists.apx",
    "database/DEMO/tables/SAMPLE_RESTAURANT.sql",
    "app_context/102/context.md",
)

EXCLUDED_PATHS = (
    ".agents/skills/superpowers/brainstorming/scripts/server.cjs",
    ".claude/skills/example/SKILL.md",
    "scripts/backup_db.sh",
    "scripts/setup_graphify_apx.py",
    "README.md",
    "ai_generate/2026-08-29/change.sql",
    "scratch/helper.sql",
    "graphify-out/graph.json",
    "apps/.gitkeep",
    "database/.gitkeep",
    "database/DEMO/manifest-code.txt",
    "database/DEMO/manifest-tables.txt",
    "app_context/README.md",
    "apps/DEMO/102/.apex/apexlang.json",
    "apps/DEMO/102/deployments/default.json",
    "apps/DEMO/102/workspace-components/app-groups/sample-applications.apx",
    "apps/DEMO/102/shared-components/static-files.apx",
    "apps/DEMO/102/shared-components/static-files/logo.png",
    "apps/DEMO/102/shared-components/themes/universal-theme/static-files/theme.css",
)


def graphify_python() -> Path | None:
    executable = shutil.which("graphify")
    if not executable:
        return None
    launcher = Path(executable).resolve()
    try:
        first_line = launcher.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeError, IndexError):
        return None
    if not first_line.startswith("#!"):
        return None
    interpreter = Path(first_line[2:].strip())
    return interpreter if interpreter.is_file() else None


class GraphifyCorpusTests(unittest.TestCase):
    def test_ignore_file_is_a_domain_allowlist(self) -> None:
        lines = {
            line.strip()
            for line in IGNORE_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        required = {
            "/*",
            "!/apps/",
            "!/database/",
            "!/app_context/",
            "/apps/**/.apex/",
            "/apps/**/deployments/",
            "/apps/**/workspace-components/",
            "/apps/**/static-files.apx",
            "/apps/**/static-files/",
            "/apps/.gitkeep",
            "/database/.gitkeep",
            "/database/**/manifest-code.txt",
            "/database/**/manifest-tables.txt",
            "/app_context/README.md",
        }
        self.assertTrue(required.issubset(lines), sorted(required - lines))
        self.assertNotIn("!/ai_generate/", lines)

    def test_graphify_matcher_includes_only_domain_sources(self) -> None:
        interpreter = graphify_python()
        if interpreter is None:
            self.skipTest("Graphify Python launcher is unavailable")
        script = r'''
import json
import sys
from pathlib import Path
from graphify.detect import _is_ignored, _load_graphifyignore

root = Path(sys.argv[1]).resolve()
paths = json.loads(sys.argv[2])
patterns = _load_graphifyignore(root)
print(json.dumps({path: _is_ignored(root / path, root, patterns) for path in paths}))
'''
        # Materialise every fixture path in a throwaway root rather than asking
        # the matcher about the working copy. Gitignore directory-only patterns
        # such as `/apps/**/.apex/` match only when the directory exists, so
        # querying the real tree made the answer depend on whichever demo
        # leftovers a given clone happened to have -- the assertion silently
        # became about local state instead of about .graphifyignore.
        #
        # The root has to sit outside the repository: `scratch/` is gitignored,
        # so a matcher that honours ignore rules reports every path under it as
        # ignored and the test passes for entirely the wrong reason. See the
        # filesystem section of .agents/rules/agent-safety.md.
        fixture_root = Path(tempfile.mkdtemp(prefix="graphify-corpus."))
        self.addCleanup(shutil.rmtree, fixture_root, ignore_errors=True)
        shutil.copyfile(IGNORE_PATH, fixture_root / ".graphifyignore")
        paths = list(INCLUDED_PATHS + EXCLUDED_PATHS)
        for path in paths:
            target = fixture_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")
        completed = subprocess.run(
            [str(interpreter), "-c", script, str(fixture_root), json.dumps(paths)],
            check=True,
            text=True,
            capture_output=True,
        )
        ignored = json.loads(completed.stdout)
        self.assertEqual(
            [path for path in INCLUDED_PATHS if ignored[path]],
            [],
            "approved domain sources were ignored",
        )
        self.assertEqual(
            [path for path in EXCLUDED_PATHS if not ignored[path]],
            [],
            "non-domain sources were included",
        )

    def test_documentation_exposes_persistent_domain_graph_workflow(self) -> None:
        rules = (REPO_ROOT / ".agents" / "rules" / "graphify.md").read_text(encoding="utf-8")
        workflow = (REPO_ROOT / ".agents" / "workflows" / "graphify.md").read_text(
            encoding="utf-8"
        )
        agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        combined = "\n".join((rules, workflow, agents, readme))

        for command in (
            "python3 scripts/setup_graphify_apx.py",
            "graphify extract . --force",
            "graphify update .",
        ):
            self.assertIn(command, combined)
        for phrase in ("app_context", "Graphify upgrade", "domain"):
            self.assertIn(phrase, combined)
        self.assertNotIn("--force --code-only", combined)
        self.assertNotIn('".apx": extract_sql', combined)

        self.assertIn("graphify extract . --force", workflow)
        self.assertIn("app_context", workflow)
        self.assertIn("Graphify upgrade", workflow)
        self.assertIn("python3 scripts/setup_graphify_apx.py", readme)

    def test_graphify_status_is_stated_consistently(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        rules = (REPO_ROOT / ".agents/rules/graphify.md").read_text(encoding="utf-8")
        # Every rule in the rules file is gated on graphify-out/ existing, and
        # the scripts work without Graphify. "Required" in the README was the
        # outlier, and agents read AGENTS.md as authoritative.
        self.assertNotIn("Graphify is required for this project", readme)
        self.assertIn("optional", agents.lower())
        self.assertIn("if `graphify-out/`", rules)
        self.assertIn('`AGENTS.md` "Optional Tooling"', rules)
        self.assertIn("uv tool install graphifyy --with tree-sitter-sql", rules)
        self.assertIn("python3 scripts/setup_graphify_apx.py --verify", rules)


@unittest.skipUnless(EXTRACTOR_PATH.is_file(), "canonical extractor is missing")
class MirroredSqlLinkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location("graphify_apexlang_extractor_sql_links", EXTRACTOR_PATH)
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    def setUp(self) -> None:
        self.module.DatabaseMirror.clear_cache()
        self.root = Path(tempfile.mkdtemp(prefix="graphify-sql-links."))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def write_database_object(self, relative: str, text: str = "-- ddl\n") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def linked_sql(self, relative: str, result: dict, text: str = "-- ddl\n") -> dict:
        self.module.DatabaseMirror.clear_cache()
        path = self.write_database_object(relative, text)
        fake_package = types.ModuleType("graphify")
        fake_extractors = types.ModuleType("graphify.extractors")
        fake_sql = types.ModuleType("graphify.extractors.sql")
        fake_sql.extract_sql = lambda _path: result
        modules = {
            "graphify": fake_package,
            "graphify.extractors": fake_extractors,
            "graphify.extractors.sql": fake_sql,
        }
        with mock.patch.dict(sys.modules, modules):
            return self.module.extract_sql_linked(path)

    def test_package_body_and_view_emit_mirrored_database_and_package_edges(self) -> None:
        self.write_database_object("database/DEMO/tables/STAFF.sql")
        self.write_database_object("database/DEMO/tables/STAFF_LOAD.sql")
        self.write_database_object("database/DEMO/views/STAFF_SERVICES_V.sql")
        self.write_database_object("database/DEMO/packages/HELPER_PKG_SPEC.sql")
        self.write_database_object("database/DEMO/packages/WORKER_PKG_SPEC.sql")
        body_sql = (
            'CREATE OR REPLACE PACKAGE BODY "DEMO"."WORKER_PKG" AS\n'
            "  PROCEDURE assign_worker IS\n"
            "  BEGIN\n"
            "    FOR r IN (SELECT s.id FROM staff s JOIN staff_services_v v ON v.id = s.id) LOOP\n"
            "      helper_pkg.check_worker(r.id);\n"
            "      UPDATE staff_load SET total = total + 1 WHERE id = r.id;\n"
            "    END LOOP;\n"
            "  END assign_worker;\n"
            "END worker_pkg;\n"
        )
        initial = {
            "nodes": [
                {
                    "id": "database_demo_packages_worker_pkg_body",
                    "label": "WORKER_PKG_BODY.sql",
                    "source_file": "database/DEMO/packages/WORKER_PKG_BODY.sql",
                    "source_location": None,
                }
            ],
            "edges": [],
        }
        result = self.linked_sql(
            "database/DEMO/packages/WORKER_PKG_BODY.sql", initial, text=body_sql
        )
        edges = {(e["source"], e["relation"], e["target"]) for e in result["edges"]}
        body_id = "database_demo_packages_worker_pkg_body"
        self.assertIn((body_id, "calls", "database_demo_packages_worker_pkg_spec"), edges)
        self.assertIn((body_id, "calls", "database_demo_packages_helper_pkg_spec"), edges)
        self.assertIn((body_id, "reads_from", "database_demo_tables_staff_demo_staff"), edges)
        self.assertIn(
            (body_id, "reads_from", "database_demo_views_staff_services_v_demo_staff_services_v"),
            edges,
        )
        self.assertIn(
            (body_id, "writes_to", "database_demo_tables_staff_load_demo_staff_load"),
            edges,
        )

    def test_ords_schema_extracts_handlers_and_package_calls(self) -> None:
        self.write_database_object("database/DEMO_CODE/packages/API_PKG_SPEC.sql")
        self.write_database_object("database/DEMO_DATA/tables/LOB_STORE.sql")
        ords_sql = (
            "BEGIN\n"
            "  ORDS.DEFINE_MODULE(\n"
            "      p_module_name => 'PUBLIC_API',\n"
            "      p_base_path   => '/public/');\n"
            "  ORDS.DEFINE_HANDLER(\n"
            "      p_module_name => 'PUBLIC_API',\n"
            "      p_pattern     => 'workers/list',\n"
            "      p_method      => 'POST',\n"
            "      p_source_type => 'plsql/block',\n"
            "      p_source      => 'BEGIN :status := DEMO_CODE.API_PKG.GET_WORKERS(:body_text); END;');\n"
            "  ORDS.DEFINE_HANDLER(\n"
            "      p_module_name => 'PUBLIC_API',\n"
            "      p_pattern     => 'media/:token',\n"
            "      p_method      => 'GET',\n"
            "      p_source_type => 'resource/lob',\n"
            "      p_source      => 'SELECT mime_type, blob_c FROM DEMO_DATA.LOB_STORE WHERE token = :token');\n"
            "END;\n"
        )
        initial = {
            "nodes": [
                {
                    "id": "database_demo_api_ords_schema",
                    "label": "schema.sql",
                    "source_file": "database/DEMO_API/ords/schema.sql",
                    "source_location": None,
                }
            ],
            "edges": [],
        }
        result = self.linked_sql("database/DEMO_API/ords/schema.sql", initial, text=ords_sql)
        labels = {node["label"]: node["id"] for node in result["nodes"]}
        self.assertIn("ORDS POST /public/workers/list", labels)
        self.assertIn("ORDS GET /public/media/:token", labels)
        post_id = labels["ORDS POST /public/workers/list"]
        get_id = labels["ORDS GET /public/media/:token"]
        edges = {(e["source"], e["relation"], e["target"]) for e in result["edges"]}
        self.assertIn(("database_demo_api_ords_schema", "contains", post_id), edges)
        self.assertIn((post_id, "calls", "database_demo_code_packages_api_pkg_spec"), edges)
        self.assertIn(
            (get_id, "reads_from", "database_demo_data_tables_lob_store_demo_data_lob_store"),
            edges,
        )


if __name__ == "__main__":
    unittest.main()
