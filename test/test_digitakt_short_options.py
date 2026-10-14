import io
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from digitakt import cli


class ShortOptionsTest(unittest.TestCase):
    def test_grouped_aliases_match_long_options(self):
        short = ['ROOT', '-d', '13', '-m', '03 Claps:D', '-r', '1:10', '-f', '1',
                 '-m', '02 Snares:B', '-l', '10', '-f', '20', '-n', '-v']
        long = ['ROOT', '--device', '13', '--map', '03 Claps:D', '--range', '1:10',
                '--from-slot', '1', '--map', '02 Snares:B', '--limit', '10',
                '--from-slot', '20', '--dry-run', '--verbose']
        self.assertEqual(vars(cli.parse_args(short)), vars(cli.parse_args(long)))

    def test_legacy_aliases(self):
        short = ['ROOT', '--folder', '03 Claps', '-b', 'D', '-s', '10', '-l', '2']
        long = ['ROOT', '--folder', '03 Claps', '--bank', 'D', '--start-slot', '10', '--limit', '2']
        self.assertEqual(vars(cli.parse_args(short)), vars(cli.parse_args(long)))

    def test_mixed_options_and_scope(self):
        args = cli.parse_args(['ROOT', '-m', '03 Claps:D', '--range', '4:5',
                               '-f', '10', '--map', '02 Snares:B', '-l', '2', '-n'])
        self.assertEqual(args.maps[0]['range'], (4, 5))
        self.assertEqual(args.maps[0]['from_slot'], 10)
        self.assertNotIn('range', args.maps[1])
        self.assertEqual(args.maps[1]['limit'], 2)

    def test_dry_run_alias_never_connects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / '03 Claps'
            folder.mkdir()
            (folder / 'sample.wav').touch()
            binary = root / 'cli'
            binary.touch()
            with patch.object(cli, 'CLI', binary), patch.object(cli, 'cmd') as midi, \
                    patch.object(cli, 'DTSession') as session, redirect_stdout(io.StringIO()):
                cli.main([str(root), '-d', '13', '-m', '03 Claps:D', '-l', '1', '-n', '-v'])
                midi.assert_not_called()
                session.assert_not_called()

    def test_group_rules_apply_to_short_options(self):
        for args in (['ROOT', '-r', '1:2'], ['ROOT', '-f', '1'],
                     ['ROOT', '-m', '03 Claps:D', '-l', '1', '--limit', '2']):
            with self.subTest(args=args), patch('sys.stderr', io.StringIO()):
                with self.assertRaises(SystemExit):
                    cli.parse_args(args)


if __name__ == '__main__':
    unittest.main()
