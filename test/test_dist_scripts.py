from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DistScriptsTest(unittest.TestCase):
    def test_script_distribution_paths(self):
        makefile = (ROOT / 'Makefile.am').read_text()
        entries = []
        for line in makefile.replace('\\\n', ' ').splitlines():
            if line.startswith('EXTRA_DIST '):
                entries.extend(line.split('=', 1)[1].split())
        for name in ('dt-build-banks', 'dt-make-sound',
                     'dt-sample-meta', 'dt-sample-info'):
            with self.subTest(script=name):
                self.assertIn('scripts/' + name, entries)
                self.assertNotIn(name, entries)
                self.assertTrue((ROOT / 'scripts' / name).is_file())
        self.assertIn('dt_sound_defaults.py', entries)
