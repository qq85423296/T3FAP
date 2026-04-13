from __future__ import annotations

import json
import re
import sys
from pathlib import Path


PLUGIN_VERSION_PATTERN = re.compile(r'plugin_version\s*=\s*"([^"]+)"')


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    plugins_root = repo_root / "plugins"
    problems: list[str] = []

    for plugin_dir in sorted(path for path in plugins_root.iterdir() if path.is_dir()):
        manifest_path = plugin_dir / "plugin.json"
        backend_path = plugin_dir / "backend" / "plugin.py"

        if not manifest_path.exists():
            continue

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_version = str(manifest.get("version") or "").strip()
        plugin_id = str(manifest.get("id") or plugin_dir.name).strip()

        if not manifest_version:
            problems.append(f"{plugin_id}: plugin.json 缺少 version")

        if not backend_path.exists():
            continue

        backend_text = backend_path.read_text(encoding="utf-8")
        matched = PLUGIN_VERSION_PATTERN.search(backend_text)
        if not matched:
            problems.append(f"{plugin_id}: backend/plugin.py 缺少 plugin_version")
            continue

        backend_version = matched.group(1).strip()
        if backend_version != manifest_version:
            problems.append(
                f"{plugin_id}: plugin.json version={manifest_version or '<empty>'} "
                f"!= backend plugin_version={backend_version or '<empty>'}"
            )

    if problems:
        print("Plugin version validation failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("Plugin version validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
