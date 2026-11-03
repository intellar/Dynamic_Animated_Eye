"""Empreintes SHA-256 d'une arborescence, insensibles aux fins de ligne.

    python scripts/hash_manifest.py <racine> [element ...] [--digest]

Sert a `deploy.ps1 -Verify` : on fabrique l'empreinte sur le PC, on la compare a
celle refabriquee sur le Pi. Les fichiers texte sont normalises CRLF -> LF avant
hachage, donc un fichier ecrit sous Windows et sa copie scp donnent la meme
empreinte. Les binaires (jpg, png) sont hashes tels quels.

Sans `--digest`, la commande liste `empreinte  chemin` trie par chemin, ce qui
permet de reperer un fichier precis. Avec `--digest`, elle n'affiche qu'une
empreinte globale, ce qui rend la comparaison triviale.

Les repertoires `.venv`, `__pycache__` et `preview` sont ignores : ils dependent
de la machine et n'ont pas a etre deployes.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

TEXT_SUFFIXES = {
    ".py",
    ".json",
    ".md",
    ".txt",
    ".sh",
    ".ps1",
    ".yml",
    ".yaml",
    ".ino",
    ".cfg",
    ".toml",
    ".service",
}

SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", ".pytest_cache", "preview"}


def iter_files(root: Path, items: list[str]):
    for item in items:
        path = root / item
        if not path.exists():
            continue
        if path.is_file():
            yield path
            continue
        for sub in sorted(path.rglob("*")):
            if sub.is_file() and not SKIP_DIRS.intersection(sub.parts):
                yield sub


def digest(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str]) -> int:
    args = [a for a in argv if a != "--digest"]
    summary = len(args) != len(argv)

    if not args:
        print(__doc__, file=sys.stderr)
        return 2

    root = Path(args[0]).resolve()
    if not root.is_dir():
        print(f"racine introuvable : {root}", file=sys.stderr)
        return 2
    items = args[1:] or ["."]

    lines = []
    for path in iter_files(root, items):
        lines.append(f"{digest(path)}  {path.relative_to(root).as_posix()}")
    lines.sort(key=lambda line: line.split("  ", 1)[1])

    if summary:
        joined = "\n".join(lines).encode("utf-8")
        print(hashlib.sha256(joined).hexdigest())
    else:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
