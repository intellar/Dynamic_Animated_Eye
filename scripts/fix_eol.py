"""Normalise les fins de ligne d'une arborescence deployee, en place.

    python scripts/fix_eol.py [racine]

PowerShell ecrit du CRLF, bash et Python n'aiment pas : un shebang, un `.json`
ou un test qui compare des chaines gardent des `\\r` parasites une fois le
projet copie sur le Pi. `deploy.ps1` lance donc ce script sur le Pi juste apres
le `scp`.

Il vit dans un fichier et non en `python3 -c "..."` inline pour une raison
precise : le client OpenSSH de Windows supprime les guillemets doubles des
commandes distantes, donc un one-liner arrive mutile cote bash (`printf
"%s|%s\\n"` devient `printf %s|%s\\n`, ce qui est un tube vers `%sn`). Un script
deploye, appele sans guillemets, ne pose plus la question.

Seuls les suffixes texte connus sont reecrits, et seulement si le fichier
contient un CR : les images et le venv ne sont pas touches. Idempotent.
"""

from __future__ import annotations

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


def fix_file(path: Path) -> bool:
    data = path.read_bytes()
    if b"\r" not in data:
        return False
    path.write_bytes(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    return True


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("-")]
    root = Path(args[0]).resolve() if args else Path(".").resolve()
    if not root.is_dir():
        print(f"root directory not found: {root}", file=sys.stderr)
        return 2

    changed = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if SKIP_DIRS.intersection(rel.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if fix_file(path):
            changed += 1
            print(f"lf  {rel.as_posix()}")

    print(f"{changed} file(s) normalised")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
