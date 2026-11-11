# Project TODO

Keep project work and inherited-template feedback here. Follow
[the template feedback guide](docs/template-feedback.md) for confirmed issues
in inherited template files. This file belongs to the project and survives
template upgrades.

## Tracked feedback

<!-- Add one record per item. Keep evidence sanitized and useful to reproduce. -->

### Open: `setup_graphify_apx.py` cannot patch Graphify 0.9.105

- Symptom: on graphifyy 0.9.105, `python3 scripts/setup_graphify_apx.py` prints "could not patch .../graphify/extract.py; extractor routing anchors not found" and exits 1. It works on 0.9.76.
- Effect: a developer who installs or upgrades Graphify today (`uv tool install graphifyy --with tree-sitter-sql`, unpinned in `AGENTS.md` and in the `graph` extra) cannot set up the `.apx` extractor.
- Evidence: the first CI run of pull request 58, job `offline (latest Python 3.x)`, 2026-11-11.
- Current state: CI pins `graphifyy==0.9.76` for the pipeline tests. The patcher and the install instructions are not changed.
- Options: (a) update the patcher's anchors for the current release and keep supporting 0.9.76; (b) pin the documented install to a supported version.
