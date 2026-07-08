"""hooks_manifest.json (init's hand-merge source of truth) and hooks/hooks.json
(the Claude Code plugin's own source of truth) are two independently
hand-maintained files — nothing else enforces they stay in sync. If a relay
hook binding is added to one and not the other, `downbeat init`'s hand-merge
and the plugin would silently diverge on which events actually run relay
hooks. This is the exact bug class a sibling project (claude-core) hit for
real (a UserPromptSubmit gap between its two lists) during review of
downbeat's --migrate-to-plugin design (relay msg d5159d102bb7)."""
import json
from pathlib import Path

import downbeat


def _manifest_bindings() -> set[tuple[str, str | None, str]]:
    manifest_path = Path(downbeat.__file__).parent / "assets" / "hooks_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    # Path(...).name here (not just e["command"] as-is) keeps this symmetric
    # with _plugin_hooks_json_bindings() rather than relying on the
    # documented-but-unenforced invariant that manifest "command" is always
    # already a bare basename.
    return {(e["event"], e["matcher"], Path(e["command"]).name) for e in manifest["events"]}


def _plugin_hooks_json_bindings() -> set[tuple[str, str | None, str]]:
    hooks_json_path = Path(__file__).resolve().parents[1] / "hooks" / "hooks.json"
    plugin_hooks = json.loads(hooks_json_path.read_text())
    bindings = set()
    for event, entries in plugin_hooks["hooks"].items():
        for entry in entries:
            matcher = entry.get("matcher")
            for h in entry.get("hooks", []):
                bindings.add((event, matcher, Path(h["command"]).name))
    return bindings


def test_hooks_manifest_and_plugin_hooks_json_agree_on_bindings():
    manifest_set = _manifest_bindings()
    plugin_set = _plugin_hooks_json_bindings()
    assert manifest_set == plugin_set, (
        "hooks_manifest.json and hooks/hooks.json disagree on relay hook "
        f"(event, matcher, command) bindings.\n"
        f"Only in hooks_manifest.json: {manifest_set - plugin_set}\n"
        f"Only in hooks/hooks.json: {plugin_set - manifest_set}\n"
        "Both files must be updated together when a relay hook binding "
        "changes — see docs/superpowers/specs/2026-07-08-migrate-to-plugin-design.md."
    )
