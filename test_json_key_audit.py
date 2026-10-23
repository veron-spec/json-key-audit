import codecs
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from json_key_audit import audit_file, audit_text, main


class KeyAuditTests(unittest.TestCase):
    def test_repeated_key_counted_once(self):
        self.assertEqual(audit_text('{"port":1,"port":2,"port":3}'),
                         [{"pointer": "/port", "key": "port", "count": 3, "object_index": 1}])

    def test_nested_objects_arrays_and_pointer_escaping(self):
        result = audit_text('{"servers":[{"a/b~c":1,"a/b~c":2}],"":{"":1,"":2}}')
        self.assertEqual([row["pointer"] for row in result], ["/servers/0/a~1b~0c", "//"])

    def test_escaped_keys_are_compared_after_decoding(self):
        self.assertEqual(audit_text(r'{"name":1,"\u006eame":2}')[0]["count"], 2)
        self.assertEqual(audit_text('{"Name":1,"name":2}'), [])

    def test_all_duplicate_parent_occurrences_are_checked(self):
        result = audit_text('{"x":{"y":1,"y":2},"x":{"y":3,"y":4}}')
        self.assertEqual([row["pointer"] for row in result], ["/x", "/x/y", "/x/y"])
        self.assertEqual([row["object_index"] for row in result], [1, 2, 3])

    def test_valid_roots_and_large_exponents(self):
        for text in ('null', '[]', '"text"', 'true', '1e9999', '[1,{"a":1},{"a":2}]'):
            with self.subTest(text=text):
                self.assertEqual(audit_text(text), [])

    def test_nonstandard_constants_and_syntax_rejected(self):
        for text in ('NaN', 'Infinity', '-Infinity', '{"a":1,}', '{"a":1} {}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                audit_text(text)

    def test_files_bom_encoding_size_limit_and_no_rewrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.json"
            original = codecs.BOM_UTF8 + b'{"a":1,"a":2}'
            path.write_bytes(original)
            self.assertEqual(audit_file(path)["status"], "fail")
            self.assertEqual(path.read_bytes(), original)
            with patch("json_key_audit.MAX_BYTES", 4):
                self.assertEqual(audit_file(path)["status"], "error")
            path.write_bytes(b"\xff")
            self.assertEqual(audit_file(path)["error"], "Input is not valid UTF-8")

    def test_error_messages_do_not_echo_values(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.json"
            path.write_bytes(b'{"key":PRIVATE_VALUE}')
            result = audit_file(path)
            self.assertEqual(result["status"], "error")
            self.assertNotIn("PRIVATE_VALUE", json.dumps(result))
            self.assertIn("line 1", result["error"])
            with patch("json_key_audit.json.loads", side_effect=RecursionError):
                self.assertEqual(audit_file(path)["status"], "error")

    def test_cli_exit_codes_and_json(self):
        with tempfile.TemporaryDirectory() as temp:
            good, bad, missing = (Path(temp) / name for name in ("good.json", "bad.json", "missing.json"))
            good.write_bytes(b'{"a":1}')
            bad.write_bytes(b'{"a":1,"a":2}')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(good)]), 0)
                self.assertEqual(main([str(bad)]), 1)
                self.assertEqual(main([str(missing), str(bad)]), 2)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(good), str(bad), "--json"]), 1)
            self.assertEqual([row["status"] for row in json.loads(output.getvalue())], ["ok", "fail"])


if __name__ == "__main__":
    unittest.main()
