import unittest

from app.models.script import default_script
from app.models.script_validate import normalize_script, validate_script


class ScriptValidateTest(unittest.TestCase):
    def test_default_script_passes_validation(self):
        script = default_script()
        validate_script(normalize_script(script))

    def test_default_script_full_mode_enables_system_support(self):
        script = default_script("full")

        self.assertEqual(script["settings"]["mode"], "full")
        self.assertTrue(script["settings"]["system_support_enabled"])

    def test_default_script_vanilla_mode_disables_system_support(self):
        script = default_script("vanilla")

        self.assertEqual(script["settings"]["mode"], "vanilla")
        self.assertFalse(script["settings"]["system_support_enabled"])

    def test_rejects_script_without_duration_column(self):
        script = default_script()
        script["columns"] = [column for column in script["columns"] if column["type"] != "duration"]

        with self.assertRaises(ValueError):
            validate_script(script)

    def test_normalize_aligns_cells_to_columns(self):
        script = default_script()
        script["columns"] = script["columns"][:2]
        script["rows"][0]["cells"] = script["rows"][0]["cells"][:1]

        normalized = normalize_script(script)
        validate_script(normalized)
        self.assertEqual(len(normalized["rows"][0]["cells"]), 2)


if __name__ == "__main__":
    unittest.main()
