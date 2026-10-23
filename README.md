# JSON Key Audit

Catch duplicate JSON keys before a configuration value silently disappears.

```json
{"port": 3000, "port": 8080}
```

Many parsers keep only the last value. JSON Key Audit retains every key-value pair during parsing and reports repeated keys, including those in nested objects and arrays.

Python 3.10+. No third-party dependencies. Read-only. Independently written. MIT licensed.

## Quick start

Clone or download this repository, then run:

```sh
python json_key_audit.py config.json
python json_key_audit.py config.json package.json --json
```

Use `python3` on systems where that is the Python command. Quote paths containing spaces. Pass explicit files; directories and literal wildcard patterns are not expanded.

For the example above:

```text
FAIL  'config.json'
      '/port': 2 occurrences (object #1)
```

The program never rewrites files or makes network requests. It reports paths, repeated key names, and counts, without printing JSON values.

## Output and exit codes

`--json` emits an array with one result per input file:

```json
[
  {
    "path": "config.json",
    "status": "fail",
    "duplicates": [
      {"pointer": "/port", "key": "port", "count": 2, "object_index": 1}
    ]
  }
]
```

Status is `ok`, `fail`, or `error`. Error results contain `error` instead of `duplicates`. Exit codes are `0` for clean inputs, `1` for duplicates, `2` for unreadable/unsupported input or invalid arguments, and `130` for cancellation. Errors take precedence over duplicates regardless of input order. Invalid files do not emit partial duplicate findings.

## Locating duplicates

Pointers use JSON Pointer escaping: `/` in a key becomes `~1`, and `~` becomes `~0`. For example, a repeated key named `a/b` inside the first array entry under `servers` is reported at `/servers/0/a~1b`. Empty keys are supported.

If a parent key is itself repeated, multiple objects can share the same pointer. `object_index` distinguishes them: it numbers objects from 1 in depth-first input order, visiting every occurrence. It is a report identifier, not a source line number. Arrays are not included in the object count. All occurrences of a repeated key are checked, including values normal parsers discard.

Keys are compared after JSON escape decoding, so `"name"` and `"\u006eame"` match. Comparison is case-sensitive, with no Unicode normalization. Keys in separate objects do not conflict.

## CI

After checking out your repository and setting up Python:

```yaml
- name: Reject duplicate configuration keys
  run: python json_key_audit.py config.json package.json
```

## Boundaries

- Inputs must be UTF-8 JSON; an initial UTF-8 BOM is accepted. Any JSON root type is accepted.
- Comments, trailing commas, NaN, and Infinity are rejected. JSON syntax errors report a line and column without echoing source text.
- Each file is limited to 16 MiB. Python's parser nesting and integer-size limits also apply. Extremely large numeric exponents may exceed Decimal's implementation limits and are reported as errors.
- Parsing retains the document in memory. The size cap limits input bytes, not peak memory. This is intended for trusted configuration files, not hostile payloads or huge datasets.
- Explicit file symlinks are followed. Use regular files: devices/pipes can block. Files changed during reading are not a consistent snapshot.
- Paths and repeated key names appear in reports; review them before sharing if those names are sensitive.

## Development

```sh
python -m unittest -v
```

Tests cover nested duplicates, arrays, repeated parent keys, pointer escaping, decoded key equality, invalid syntax, input limits, UTF-8/BOM handling, exit codes, and unchanged input bytes. CI runs Python 3.10 and 3.14 on Windows and Linux.
