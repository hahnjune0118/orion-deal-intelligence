"""Private native parser process. No files, URLs, providers or user code loaded."""
import base64
import json
import sys
from .native import MAX_SOURCE_BYTES, ParserLimitError, _parse_bytes


def main():
    # Available on POSIX; byte/decompression/unit/time limits also apply on Windows.
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
    except (ImportError, OSError, ValueError):
        pass
    raw = sys.stdin.buffer.read(MAX_SOURCE_BYTES * 2)
    try:
        payload = json.loads(raw)
        parsed = _parse_bytes(base64.b64decode(payload["bytes"], validate=True), payload["metadata"])
        out = {"document": parsed.document.model_dump(mode="json"),
               "source_spans": [s.model_dump(mode="json") for s in parsed.source_spans],
               "warnings": list(parsed.warnings)}
    except ParserLimitError as exc:
        out = {"error": str(exc)}
    except Exception:
        out = {"error": "PARSER_REJECTED_DOCUMENT"}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
