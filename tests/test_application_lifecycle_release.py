"""The 26.1 template's lifecycle release gate accepts APEX 26.1 and 26.2 (both verified), and nothing else.

The SQL adapter (scripts/application_lifecycle.sql) and the Python validator
(scripts/application_lifecycle.py) must agree; a mismatch would let one side
refuse what the other accepts.
"""
import re
import unittest
from pathlib import Path

import _no_real_sqlcl  # noqa: F401  (keeps tests away from a real SQLcl)
from scripts import application_lifecycle

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_FIELDS = ('db_unique_name', 'service_name', 'container_id', 'container_name', 'edition',
                   'server_host', 'session_user', 'current_schema')
ACCEPTED = ('26.1', '26.1.0', '26.1.5', '26.2.0', '26.2.1')
REFUSED = ('26.3.0', '26.20', '25.2.0', '27.1', '26.2.', '26.2-beta', ' 26.2.0', '26.1.0.x')


def snapshot(release):
    return {
        'schemaVersion': 1,
        'applicationPresent': True,
        'identity': dict(zip(IDENTITY_FIELDS, ('FREE', 'freepdb1', '3', 'FREEPDB1', 'ORA$BASE',
                                               'dbhost', 'E2E_WIN', 'E2E_WIN'), strict=True)),
        'release': release,
        'workspace': 'E2E_WIN',
        'workspaceId': '123',
        'appId': 2611,
        'startedAt': '2026-11-20T10:00:00Z',
        'completedAt': '2026-11-20T10:00:01Z',
        'coverage': dict.fromkeys(('application', 'workspace', 'automations', 'workflows', 'tasks'), True),
        'automations': [],
        'workflows': [],
        'tasks': [],
    }


def sql_gate_pattern():
    text = (ROOT / 'scripts' / 'application_lifecycle.sql').read_text(encoding='utf-8')
    match = re.search(r"REGEXP_LIKE\(v_release,'([^']+)'\)", text)
    if match is None:
        raise AssertionError('the SQL adapter has no release gate')
    # Oracle's POSIX class [[:digit:]] is [0-9] for Python's re.
    return match.group(1).replace('[[:digit:]]', '[0-9]')


class LifecycleReleaseGateTests(unittest.TestCase):
    def test_python_gate_accepts_26_1_and_26_2_only(self):
        for release in ACCEPTED:
            with self.subTest(release=release):
                application_lifecycle.validate_snapshot(snapshot(release))
        for release in REFUSED:
            with self.subTest(release=release), self.assertRaises(ValueError) as caught:
                application_lifecycle.validate_snapshot(snapshot(release))
            self.assertIn('requires APEX 26.1 or 26.2', str(caught.exception))

    def test_sql_gate_agrees_with_the_python_gate(self):
        pattern = sql_gate_pattern()
        for release in ACCEPTED + REFUSED:
            with self.subTest(release=release):
                sql_accepts = re.fullmatch(pattern, release) is not None
                python_accepts = re.fullmatch(r'26\.[12](?:\.[0-9]+)*', release) is not None
                self.assertEqual(sql_accepts, python_accepts)
                self.assertEqual(sql_accepts, release in ACCEPTED)


if __name__ == '__main__':
    unittest.main()
