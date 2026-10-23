from pathlib import Path
import tempfile
import shutil
import subprocess
import hashlib
import sys
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from digitakt import cli as generator


class SoundTagsTest(unittest.TestCase):
    def generate(self, folder):
        data = bytearray(203)
        data[:4] = bytes.fromhex("ac11d303")
        data[25:29] = (160).to_bytes(4, "big")
        data[30] = 12
        data[39:43] = (1).to_bytes(4, "big")
        data[-8:-4] = (160).to_bytes(4, "big")
        data[-4:] = bytes.fromhex("aaa1daaa")
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "template.data"
            output = Path(directory) / "sound.data"
            template.write_bytes(data)
            generator.make_sound_data(output, "B", 1, "01_SNARE",
                                      543, 35172, 946439349, folder)
            return output.read_bytes()

    def test_matches_validated_hardware_model(self):
        self.assertEqual(hashlib.sha256(self.generate('02 Snares')).hexdigest(),
                         '4d01ff7bdcf6570bb2aff49b695c81629d8c85e2e4117cdf71c99f2577153869')

    def test_default_sound_is_independent_and_valid(self):
        first = generator.create_default_sound()
        original = bytes(first)
        first[43] = 255
        self.assertEqual(bytes(generator.create_default_sound()), original)
        self.assertEqual(len(original), 203)
        self.assertEqual(int.from_bytes(original[-12:-8], 'big'),
                         zlib.crc32(original[31:-12], 0xFFFFFFFF) & 0xFFFFFFFF)

    def test_replace_kick_with_snare_only(self):
        kick = self.generate("01 Kicks")
        snare = self.generate("02 Snares")
        self.assertEqual(snare[39:43], (2).to_bytes(4, "big"))
        self.assertEqual(kick[:39], snare[:39])
        self.assertEqual(kick[43:-12], snare[43:-12])
        self.assertEqual(kick[-8:], snare[-8:])
        self.assertEqual(int.from_bytes(snare[-12:-8], "big"),
                         zlib.crc32(snare[31:-12], 0xFFFFFFFF) & 0xFFFFFFFF)

    def test_verified_folder_categories(self):
        for folder, value in [("03 Claps", 8), ("04 Hats Closed", 64),
                              ("05 Hats Open", 64), ("07 Toms", 16),
                              ("08 Rims", 4), ("09 Cymbals", 128),
                              ("10 Percussion", 32)]:
            with self.subTest(folder=folder):
                self.assertEqual(int.from_bytes(self.generate(folder)[39:43], "big"), value)

    def test_unknown_folder_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "category"):
            self.generate("99 Unclassified")

    def test_individual_generator_explicit_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / 'scripts').mkdir()
            shutil.copy(ROOT / "scripts/dt-make-sound", root / "scripts/dt-make-sound")
            shutil.copytree(ROOT / 'scripts/digitakt', root / 'scripts/digitakt',
                            ignore=shutil.ignore_patterns('__pycache__'))
            for path in [root / "src/elektroid-cli", root / "scripts/dt-sample-meta"]:
                path.write_text("#!/bin/sh\nprintf 'ID=0000021F\\nSIZE=35172\\nHASH=386982B5\\n'\n")
                path.chmod(0o755)
            template = root / "template.data"
            template.write_bytes(self.generate("01 Kicks"))
            for tag, value in [("SNARE", 2), ("FAVOURITE", 0x80000000)]:
                result = subprocess.run(
                    ["bash", str(root / "scripts/dt-make-sound"),
                     "13:/sample", "B", "1", "01_SNARE", tag],
                    cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                data = (root / "B001_01_SNARE.data").read_bytes()
                self.assertEqual(int.from_bytes(data[39:43], "big"), value)
                self.assertEqual(int.from_bytes(data[-12:-8], "big"),
                                 zlib.crc32(data[31:-12], 0xFFFFFFFF) & 0xFFFFFFFF)

    def test_metadata_wrapper_uses_public_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src').mkdir()
            (root / 'scripts').mkdir()
            shutil.copy(ROOT / 'scripts/dt-sample-info', root / 'scripts/dt-sample-info')
            cli = root / 'src/elektroid-cli'
            cli.write_text('''#!/bin/sh
[ "$1" = "elektron:sample:sample-info" ] || exit 25
printf 'id=543\\nsize=35172\\nhash=386982b5\\n'
''')
            cli.chmod(0o755)
            result = subprocess.run(['bash', str(root / 'scripts/dt-sample-info'), '13:/sample'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout,
                             'SAMPLE_INFO id=0000021f size=35172 hash=386982b5\n')
            cli.write_text('#!/bin/sh\nexit 23\n')
            result = subprocess.run(['bash', str(root / 'scripts/dt-sample-info'), '13:/sample'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 23)
            self.assertEqual(result.stdout, '')


if __name__ == "__main__":
    unittest.main()
