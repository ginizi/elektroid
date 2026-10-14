import test_digitakt_generator_tags as tag_tests
from pathlib import Path
import tempfile
import unittest
import io
from contextlib import redirect_stdout
from unittest.mock import patch

generator = tag_tests.generator


class SelectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        folder = self.root / '02 Snares'
        folder.mkdir()
        for i in range(1, 41):
            (folder / f'sample{i}.wav').touch()

    def plan(self, selection='02 Snares', limit=None, bank=None, start=None):
        return generator.build_plan(self.root, limit,
                                    [generator.parse_folder_spec(selection)],
                                    bank, start)[0]

    def test_folder_only_and_limit(self):
        jobs = self.plan(limit=10)
        self.assertEqual(len(jobs), 10)
        self.assertEqual([j['wav'].name for j in jobs],
                         [f'sample{i}.wav' for i in range(1, 11)])

    def test_source_range_independent_of_destination(self):
        jobs = self.plan('02 Snares:21:40', bank='D', start=100)
        self.assertEqual([j['slot'] for j in jobs], list(range(100, 120)))
        self.assertEqual([j['source_rank'] for j in jobs], list(range(21, 41)))
        self.assertTrue(all(j['bank'] == 'D' and j['source_folder'] == '02 Snares' for j in jobs))

    def test_limit_after_range(self):
        jobs = self.plan('02 Snares:21:40', limit=5, start=100)
        self.assertEqual([j['source_rank'] for j in jobs], list(range(21, 26)))

    def test_capacity_boundaries(self):
        self.assertEqual(self.plan(limit=30, start=227)[-1]['slot'], 256)
        self.assertEqual(self.plan(limit=7, start=250)[-1]['slot'], 256)
        for start in (228, 250):
            with self.assertRaises(SystemExit):
                self.plan(limit=30, start=start)

    def test_missing_range_rejected(self):
        with self.assertRaises(SystemExit):
            self.plan('02 Snares:35:50')

    def test_multiple_folders_with_placement_rejected(self):
        with self.assertRaises(SystemExit):
            generator.build_plan(self.root, None,
                                 [('02 Snares', 1, 5), ('02 Snares', 6, 10)],
                                 'B', 1)

    def test_occupied_destination_reported(self):
        jobs = self.plan(limit=1)
        with patch.object(generator, 'cmd', return_value='F 0012 1 1 160B 001 EXISTING\n'):
            self.assertEqual(generator.check_destinations(jobs), ['B001'])

    def test_empty_destination_accepted(self):
        with patch.object(generator, 'cmd', return_value=''):
            generator.check_destinations(self.plan(limit=1))

    def test_unknown_listing_rejected(self):
        with patch.object(generator, 'cmd', return_value='unexpected output\n'):
            with self.assertRaises(SystemExit):
                generator.check_destinations(self.plan(limit=1))

    def test_cli_preview_never_connects(self):
        template = self.root / 'template.data'
        template.write_bytes(tag_tests.SoundTagsTest().generate('01 Kicks'))
        cli = self.root / 'elektroid-cli'
        cli.touch()
        argv = ['dt-build-banks', str(self.root),
                '--folder', '02 Snares:21:40', '--bank', 'd', '--start-slot', '100',
                '--dry-run', '--verbose']
        output = io.StringIO()
        with patch('sys.argv', argv), patch.object(generator, 'CLI', cli), \
                patch.object(generator, 'cmd') as transport, \
                patch.object(generator, 'DTSession') as session, redirect_stdout(output):
            generator.main()
            transport.assert_not_called()
            session.assert_not_called()
        self.assertIn('D100', output.getvalue())
        self.assertIn('rank 21', output.getvalue())
        self.assertIn('D119', output.getvalue())

    def test_cli_overflow_never_connects_even_execute(self):
        template = self.root / 'template.data'
        template.write_bytes(tag_tests.SoundTagsTest().generate('01 Kicks'))
        cli = self.root / 'elektroid-cli'
        cli.touch()
        argv = ['dt-build-banks', str(self.root), '--folder',
                '02 Snares', '--limit', '30', '--start-slot', '250']
        with patch('sys.argv', argv), patch.object(generator, 'CLI', cli), \
                patch.object(generator, 'cmd') as transport, \
                patch.object(generator, 'DTSession') as session:
            with self.assertRaisesRegex(SystemExit, '7 slots available'):
                generator.main()
            transport.assert_not_called()
            session.assert_not_called()

    def test_source_rank_can_exceed_bank_capacity(self):
        folder = self.root / '02 Snares'
        for i in range(41, 301):
            (folder / f'sample{i}.wav').touch()
        jobs = self.plan('02 Snares:290:300', start=1)
        self.assertEqual([j['slot'] for j in jobs], list(range(1, 12)))
        self.assertEqual(jobs[0]['source_rank'], 290)

    def test_no_silent_truncation(self):
        folder = self.root / '02 Snares'
        for i in range(41, 301):
            (folder / f'sample{i}.wav').touch()
        with self.assertRaises(SystemExit):
            self.plan()

    def test_invalid_placement_rejected(self):
        for bank, start in [('Z', 1), ('BB', 1), ('B', 0), ('B', 257)]:
            with self.subTest(bank=bank, start=start), self.assertRaises(SystemExit):
                self.plan(bank=bank, start=start)

    def test_device_option_used_for_enumeration_and_slot_listing(self):
        cli = self.root / 'cli'
        cli.touch()
        argv = ['dt-build-banks', str(self.root), '--device', '13',
                '--map', '02 Snares:D', '--tag', 'SNARE', '--limit', '1']
        listing = ('13: id: Elektron Digitakt :: Elektron Digitakt; '
                   'name: Elektron Digitakt :: Elektron Digitakt\n')
        previous = generator.DEVICE
        try:
            with patch('sys.argv', argv), patch.object(generator, 'CLI', cli), \
                    patch.object(generator, 'cmd', side_effect=[listing, '']) as midi, \
                    patch('builtins.input', return_value='non'), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(SystemExit, 'Cancelled'):
                    generator.main()
                self.assertEqual(generator.DEVICE, previous)
                self.assertEqual(midi.call_args_list[1].args[0],
                                 [cli, 'elektron:data:ls', '13:/soundbanks/D'])
        finally:
            generator.DEVICE = previous

    def test_device_dry_run_and_invalid_values(self):
        cli = self.root / 'cli'
        cli.touch()
        previous = generator.DEVICE
        try:
            with patch('sys.argv', ['dt-build-banks', str(self.root), '--device', '13',
                                   '--map', '02 Snares:D', '--tag', 'SNARE', '--limit', '1', '--dry-run']), \
                    patch.object(generator, 'CLI', cli), patch.object(generator, 'cmd') as midi, \
                    redirect_stdout(io.StringIO()):
                generator.main()
                midi.assert_not_called()
            for value in ('-1', 'invalid'):
                with patch('sys.argv', ['dt-build-banks', str(self.root), '--device', value]), \
                        patch('sys.stderr', io.StringIO()), patch.object(generator, 'cmd') as midi:
                    with self.assertRaises(SystemExit) as error:
                        generator.main()
                    self.assertEqual(error.exception.code, 2)
                    midi.assert_not_called()
        finally:
            generator.DEVICE = previous

    def test_confirmation_declined_no_write(self):
        with patch('builtins.input', return_value='non'):
            with self.assertRaises(SystemExit):
                generator.confirm_execution(self.plan(limit=2), ['B001'])

    def test_confirmation_eof_no_write(self):
        with patch('builtins.input', side_effect=EOFError):
            with self.assertRaises(SystemExit):
                generator.confirm_execution(self.plan(limit=2), [])

    def test_clear_then_upload(self):
        with patch.object(generator, 'cmd') as cli, \
                patch.object(generator, 'DTSession') as fresh:
            session = unittest.mock.Mock()
            generator.replace_sound(session, Path('candidate.data'), 'D', 1)
            self.assertEqual(session.command.call_args_list, [
                unittest.mock.call('DATA_CL', '/soundbanks/D/1'),
                unittest.mock.call('DATA_UL', Path('candidate.data'), '/soundbanks/D/1')])
            session.close.assert_not_called()
            cli.assert_not_called()
            fresh.assert_not_called()

    def test_upload_failure_propagates(self):
        original = unittest.mock.Mock()
        with patch.object(generator, 'cmd') as cli:
            original.command.side_effect = [None, RuntimeError('upload failed')]
            with self.assertRaises(RuntimeError):
                generator.replace_sound(original, Path('candidate.data'), 'D', 1)
            cli.assert_not_called()

    def test_two_sounds_never_overlap_cli_and_session(self):
        original = unittest.mock.Mock()
        with patch.object(generator, 'cmd') as cli, \
                patch.object(generator, 'DTSession') as fresh:
            for slot in (1, 2):
                generator.replace_sound(original, Path('candidate.data'), 'D', slot)
            self.assertEqual(original.command.call_count, 4)
            original.close.assert_not_called()
            cli.assert_not_called()
            fresh.assert_not_called()

    def test_clear_failure_prevents_upload(self):
        session = unittest.mock.Mock()
        session.command.side_effect = RuntimeError('clear failed')
        with patch.object(generator, 'cmd') as cli:
            with self.assertRaises(RuntimeError):
                generator.replace_sound(session, Path('candidate.data'), 'D', 1)
            session.command.assert_called_once_with('DATA_CL', '/soundbanks/D/1')
            cli.assert_not_called()

    def test_old_options_rejected(self):
        for option in ('--execute', '--clear-sounds', '--clear-target-slots'):
            with patch('sys.argv', ['dt-build-banks', 'ROOT', option]), \
                    patch.object(generator, 'cmd') as transport, \
                    patch('sys.stderr', io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    generator.main()
                self.assertEqual(error.exception.code, 2)
                transport.assert_not_called()

    def test_cli_declined_before_any_write(self):
        template = self.root / 'template.data'
        template.write_bytes(tag_tests.SoundTagsTest().generate('01 Kicks'))
        cli = self.root / 'elektroid-cli'
        cli.touch()
        argv = ['dt-build-banks', str(self.root), '--folder',
                '02 Snares:1:2', '--bank', 'D', '--start-slot', '1']
        listing = (f'{generator.DEVICE}: id: Elektron Digitakt :: Elektron Digitakt; '
                   'name: Elektron Digitakt :: Elektron Digitakt\n')
        with patch('sys.argv', argv), patch.object(generator, 'CLI', cli), \
                patch.object(generator, 'cmd', side_effect=[listing, '']) as transport, \
                patch.object(generator, 'DTSession') as session, \
                patch('builtins.input', return_value='non'), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, 'Cancelled'):
                generator.main()
            self.assertEqual(transport.call_count, 2)
            session.assert_not_called()

    def test_english_confirmation(self):
        with patch('builtins.input', return_value='YES'), redirect_stdout(io.StringIO()):
            generator.confirm_execution(self.plan(limit=1), [])


if __name__ == '__main__':
    unittest.main()
