"""Verify the original handoff checksum manifest without rewriting any spec."""
from hashlib import sha256
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "spec"
    lines = (root / "CHECKSUMS.sha256").read_text(encoding="utf-8").splitlines()
    count = 0
    for line in lines:
        digest, name = line.split(maxsplit=1)
        path = (root / name.strip()).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Invalid manifest path")
        if sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Specification checksum mismatch: {name}")
        count += 1
    print(f"{count} original specification checksums verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
