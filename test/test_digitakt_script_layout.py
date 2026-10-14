from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ScriptLayoutTest(unittest.TestCase):
    def test_commands_live_in_scripts(self):
        for name in ('dt-build-banks', 'dt-make-sound',
                     'dt-sample-info', 'dt-sample-meta'):
            with self.subTest(name=name):
                self.assertTrue((ROOT / 'scripts' / name).is_file())
                self.assertFalse((ROOT / name).exists())

    def test_help_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ('dt-build-banks', 'dt-make-sound'):
                with self.subTest(name=name):
                    result = subprocess.run(
                        [str(ROOT / 'scripts' / name), '--help'], cwd=directory,
                        capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('usage:', result.stdout.lower())
