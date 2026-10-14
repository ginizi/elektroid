import io
import sys
import shlex
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from digitakt import cli


class ShortOptionsTest(unittest.TestCase):
    def test_capacity_suggestion_uses_real_root_and_device(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "User's sample library"
            folder = root / '01 Kicks'
            folder.mkdir(parents=True)
            binary = root / 'cli'
            binary.touch()
            files = [folder / f'kick{i}.wav' for i in range(300)]
            for selection in ([], ['-m', '01 Kicks:A']):
                with self.subTest(selection=selection), patch.object(cli, 'CLI', binary), \
                        patch('digitakt.planning.inventory', return_value=files), \
                        redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
                    cli.main([str(root), '-d', '13', *selection])
                text = str(error.exception)
                self.assertNotIn('/path/to/sample-library', text)
                if not selection:
                    command = text.splitlines()[-1].strip()
                    self.assertEqual(shlex.split(command),
                                     ['./dt-build-banks', str(root.resolve()),
                                      '--limit', '256', '--device', '13', '-n'])
                else:
                    self.assertNotIn('Preview up to 256', text)

    def test_default_capacity_error_explains_folder_bank_and_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / '01 Kicks'
            folder.mkdir()
            binary = root / 'cli'
            binary.touch()
            files = [folder / f'kick{i}.wav' for i in range(1976)]
            output = io.StringIO()
            with patch.object(cli, 'CLI', binary), patch.object(cli, 'cmd') as midi, \
                    patch('digitakt.planning.inventory', return_value=files), \
                    redirect_stdout(output), self.assertRaises(SystemExit) as error:
                cli.main([str(root)])
            text = str(error.exception)
            self.assertIn('01 Kicks', text)
            self.assertIn('1,976', text)
            self.assertIn('bank A', text)
            self.assertIn('including to other banks', text)
            self.assertIn('--limit 256', text)
            self.assertNotIn('-1719', text)
            self.assertIn('No --map/--folder provided', output.getvalue())
            self.assertIn('Samples do not overflow', output.getvalue())
            midi.assert_not_called()

    def test_help_explains_default_bank_mapping(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            cli.parse_args(['--help'])
        self.assertIn('Default mapping', output.getvalue())
        self.assertIn('A Kicks', output.getvalue())
        self.assertIn('cowbell filter', output.getvalue())

    def test_help_explains_repeatable_maps(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            cli.parse_args(['--help'])
        text = output.getvalue()
        self.assertIn('repeatable; starts a selection group', ' '.join(text.split()))
        self.assertIn('Combine multiple mappings in one command:', text)
        self.assertIn('-m "02 Snares:B" -l 10 -f 20 -n', text)
        self.assertIn('until the next -m/--map', text)

    def test_help_shows_full_bank_preview_and_write(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            cli.parse_args(['--help'])
        text = output.getvalue()
        self.assertIn('Populate banks A-H', text)
        self.assertIn('--limit 256 --device INDEX -n', text)
        self.assertIn('--limit 256 --device INDEX\n', text)
        self.assertIn('256 eligible WAVs per category after filters', text)
        self.assertIn('Samples are not repeated', text)

    def test_help_shows_example_with_placeholder_root(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as exit:
            cli.parse_args(['--help'])
        self.assertEqual(exit.exception.code, 0)
        text = output.getvalue()
        self.assertIn('Example usage:', text)
        self.assertIn('./dt-build-banks "/path/to/sample-library"', text)
        self.assertIn('-m "03 Claps:D" -r 1:10 -f 1 -n', text)
        self.assertIn('containing the "03 Claps" folder', text)

    def test_dry_run_help_explains_preview_and_execution(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as exit:
            cli.parse_args(['--help'])
        self.assertEqual(exit.exception.code, 0)
        help_text = ' '.join(output.getvalue().split())
        self.assertIn('-n, --dry-run', help_text)
        self.assertIn('without MIDI connection or writes', help_text)
        self.assertIn('Without this option, execute after confirmation.', help_text)

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
