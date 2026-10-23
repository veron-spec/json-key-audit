#!/usr/bin/env python3
"""Find duplicate JSON object keys without rewriting input files."""

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sys


MAX_BYTES = 16 * 1024 * 1024


class ObjectPairs(list):
    """Distinguish JSON objects from arrays while retaining repeated keys."""


def reject_constant(value):
    raise ValueError("Non-standard numeric constant")


def pointer_token(key):
    return key.replace("~", "~0").replace("/", "~1")


def audit_text(text):
    """Return each repeated decoded key once per containing object."""
    document = json.loads(text, object_pairs_hook=ObjectPairs,
                          parse_constant=reject_constant, parse_float=Decimal)
    pending = [(document, "")]
    duplicates = []
    object_index = 0
    while pending:
        node, path = pending.pop()
        if isinstance(node, ObjectPairs):
            object_index += 1
            counts = Counter(key for key, _ in node)
            for key, count in counts.items():
                if count > 1:
                    duplicates.append({"pointer": path + "/" + pointer_token(key),
                                       "key": key, "count": count,
                                       "object_index": object_index})
            # Visit every occurrence, including values a normal parser discards.
            pending.extend((value, path + "/" + pointer_token(key))
                           for key, value in reversed(node))
        elif isinstance(node, list):
            pending.extend((value, path + "/" + str(index))
                           for index, value in reversed(list(enumerate(node))))
    return duplicates


def audit_file(path):
    try:
        with path.open("rb") as source:
            data = source.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Input exceeds the 16 MiB limit")
        findings = audit_text(data.decode("utf-8-sig"))
        return {"path": str(path), "status": "fail" if findings else "ok", "duplicates": findings}
    except json.JSONDecodeError as exc:
        error = f"Invalid JSON at line {exc.lineno}, column {exc.colno}"
    except UnicodeError:
        error = "Input is not valid UTF-8"
    except RecursionError:
        error = "JSON nesting exceeds the parser limit"
    except InvalidOperation:
        error = "Unsupported JSON number"
    except OSError as exc:
        error = exc.strerror or type(exc).__name__
    except ValueError as exc:
        # Integer conversion errors can include input text; return only known messages.
        error = str(exc) if str(exc) in ("Input exceeds the 16 MiB limit", "Non-standard numeric constant") else "Unsupported JSON number"
    return {"path": str(path), "status": "error", "error": error}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="Explicit UTF-8 JSON file paths")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON array")
    args = parser.parse_args(argv)
    try:
        results = [audit_file(path) for path in args.files]
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=True))
        else:
            for result in results:
                print(f"{result['status'].upper():5} {str(result['path'])!a}")
                if result["status"] == "error":
                    print(f"      {result['error']!a}")
                else:
                    for finding in result["duplicates"]:
                        print(f"      {finding['pointer']!a}: {finding['count']} occurrences "
                              f"(object #{finding['object_index']})")
        return max({"ok": 0, "fail": 1, "error": 2}[row["status"]] for row in results)
    except KeyboardInterrupt:
        print("Audit cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
