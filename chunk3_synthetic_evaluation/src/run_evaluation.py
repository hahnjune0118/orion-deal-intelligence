"""Run the integrated offline benchmark from the repository root."""
import sys
from orion.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["evaluate", *sys.argv[1:]]))
