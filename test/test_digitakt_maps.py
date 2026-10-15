import argparse
import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_digitakt_generator_tags as tag_tests

generator = tag_tests.generator


class MapsTest(unittest.TestCase):
    def test_output_base_is_temporary(self):
        self.assertEqual(generator.BASE, self.root)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        output_base = patch.object(generator, 'BASE', self.root)
        output_base.start()
        self.addCleanup(output_base.stop)
        for folder in ('03 Claps', '02 Snares'):
            path = self.root / folder
            path.mkdir()
            for i in range(1, 11):
                (path / f'{i}.wav').touch()

    def test_two_independent_maps(self):
        maps = [{'path': '03 Claps', 'bank': 'A', 'tag': 'CLAP', 'range': (2, 5), 'limit': 2,
                 'from_slot': 10},
                {'path': str(self.root / '02 Snares'), 'bank': 'D', 'tag': 'SNARE', 'range': (4, 5),
                 'from_slot': 20}]
        jobs, _ = generator.build_maps_plan(self.root, maps)
        self.assertEqual([(j['bank'], j['slot'], j['source_rank']) for j in jobs],
                         [('A', 10, 2), ('A', 11, 3), ('D', 20, 4), ('D', 21, 5)])
        self.assertEqual(jobs[0]['source_folder'], '03 Claps')
        self.assertEqual(jobs[2]['source_folder'], '02 Snares')

    def test_collision_rejected(self):
        with self.assertRaisesRegex(SystemExit, 'collision'):
            generator.build_maps_plan(self.root, [
                {'path': '03 Claps', 'bank': 'A', 'tag': 'CLAP', 'limit': 2},
                {'path': '02 Snares', 'bank': 'A', 'tag': 'SNARE', 'limit': 2}])

    def test_overflow_rejected(self):
        with self.assertRaises(SystemExit):
            generator.build_maps_plan(self.root, [
                {'path': '03 Claps', 'bank': 'D', 'tag': 'CLAP', 'limit': 3, 'from_slot': 255}])

    def test_cli_grouped_dry_run(self):
        template = self.root / 'template.data'
        template.write_bytes(tag_tests.SoundTagsTest().generate('01 Kicks'))
        cli = self.root / 'cli'
        cli.touch()
        argv = ['dt-build-banks', str(self.root),
                '--map', '03 Claps:a', '--tag', 'CLAP', '--range', '2:5', '--limit', '2', '--from-slot', '10',
                '--map', '02 Snares:D', '--tag', 'SNARE', '--range', '4:5', '--from-slot', '20', '--dry-run']
        out = io.StringIO()
        with patch('sys.argv', argv), patch.object(generator, 'CLI', cli), \
                patch.object(generator, 'cmd') as midi, redirect_stdout(out):
            generator.main()
            midi.assert_not_called()
        self.assertIn('A010', out.getvalue())
        self.assertIn('D020', out.getvalue())
        self.assertIn('SNARE', out.getvalue())

    def test_compact_preview_and_exact_ranges(self):
        jobs, summary = generator.build_maps_plan(self.root, [
            {'path': '03 Claps', 'bank': 'D', 'tag': 'CLAP', 'range': (1, 2), 'from_slot': 10},
            {'path': '03 Claps', 'bank': 'D', 'tag': 'CLAP', 'range': (4, 5), 'from_slot': 20}])
        out = io.StringIO()
        with redirect_stdout(out):
            generator.print_plan(jobs, summary)
        text = out.getvalue()
        self.assertIn('BANK', text)
        self.assertIn('SLOT', text)
        self.assertIn('D010–D011', text)
        self.assertIn('D020–D021', text)
        self.assertNotIn('D010–D021', text)
        self.assertNotIn(str(self.root), text)
        self.assertIn('Total: 4 sounds', text)
        self.assertIn('1.wav', text)
        self.assertIn('5.wav', text)
        self.assertIn('SOURCE FILE', text)
        out = io.StringIO()
        with redirect_stdout(out):
            generator.print_plan(jobs, summary, verbose=True)
        self.assertIn(str(self.root), out.getvalue())
        self.assertIn('rank 1', out.getvalue())

    def test_destination_banks_before_device_in_mapping_order(self):
        jobs, summary = generator.build_maps_plan(self.root, [
            {'path': '03 Claps', 'bank': 'D', 'tag': 'CLAP', 'limit': 1},
            {'path': '02 Snares', 'bank': 'B', 'tag': 'SNARE', 'limit': 1, 'from_slot': 20}])
        out = io.StringIO()
        with redirect_stdout(out):
            generator.print_plan(jobs, summary)
        text = out.getvalue()
        self.assertLess(text.index('BANK D'), text.index('BANK B'))
        self.assertLess(text.index('BANK B'), text.index('MIDI index'))
        self.assertIn('Total: 2 sounds across 2 banks', text)

    def test_invalid_map_syntax(self):
        for value in ('03 Claps', ':A', '03 Claps:Z', '03 Claps:AA'):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                generator.parse_map(value)

    def test_invalid_group_options_rejected_before_midi(self):
        cases = [
            ['--range', '1:2', '--map', '03 Claps:A'],
            ['--from-slot', '1', '--map', '03 Claps:A'],
            ['--limit', '2', '--map', '03 Claps:A'],
            ['--map', '03 Claps:A', '--folder', '02 Snares'],
            ['--map', '03 Claps:A', '--range', '1:2', '--range', '3:4'],
            ['--map', '03 Claps:A', '--limit', '2', '--limit', '3'],
            ['--map', '03 Claps:A', '--from-slot', '1', '--from-slot', '2'],
        ]
        for args in cases:
            with self.subTest(args=args), \
                    patch('sys.argv', ['dt-build-banks', str(self.root)] + args), \
                    patch('sys.stderr', io.StringIO()), patch.object(generator, 'cmd') as midi:
                with self.assertRaises(SystemExit) as error:
                    generator.main()
                self.assertEqual(error.exception.code, 2)
                midi.assert_not_called()

    def test_missing_tag_rejected(self):
        path = self.root / 'Unknown'
        path.mkdir()
        with self.assertRaisesRegex(SystemExit, 'tag'):
            generator.build_maps_plan(self.root, [{'path': str(path), 'bank': 'A'}])

    def test_duplicate_source_rejected(self):
        with self.assertRaisesRegex(SystemExit, 'source'):
            generator.build_maps_plan(self.root, [
                {'path': '03 Claps', 'bank': 'A', 'tag': 'CLAP', 'limit': 2},
                {'path': '03 Claps', 'bank': 'B', 'tag': 'CLAP', 'limit': 2}])

    def test_free_folder_all_tags_and_matching_payload(self):
        from digitakt.sound import TAGS, TAG_VALUES
        from digitakt.reporting import sound_name, TransferReport
        from digitakt.execution import process_job
        from digitakt.transport import Config
        from unittest.mock import Mock
        import csv
        folder = self.root / 'My textures'
        folder.mkdir()
        (folder / 'sample.wav').touch()
        for tag in TAGS:
            with self.subTest(tag=tag):
                jobs, _ = generator.build_maps_plan(self.root, [
                    {'path': folder.name, 'bank': 'A', 'tag': tag}])
                job = jobs[0]
                self.assertEqual(job['tag'], tag)
                session = Mock()
                session.command.return_value = 'SAMPLE_INFO id=00000001 size=100 hash=00000002'
                process_job(job, Config(Path('cli'), '13', self.root), session, Mock())
                data = (self.root / f'A001_{sound_name(job)}.data').read_bytes()
                self.assertEqual(int.from_bytes(data[39:43], 'big'), TAG_VALUES[tag])
                self.assertEqual(data[43:59].rstrip(b'\0').decode(), sound_name(job))
                out = io.StringIO()
                with redirect_stdout(out):
                    generator.print_plan(jobs, [])
                self.assertIn(tag, out.getvalue())
                report_path = self.root / f'report-{TAG_VALUES[tag]}.csv'
                TransferReport(report_path, jobs, self.root, dry_run=True)
                with report_path.open(newline='') as stream:
                    self.assertEqual(next(csv.DictReader(stream))['tag'], tag)

    def test_homonymous_free_folders_have_distinct_sample_destinations(self):
        maps = []
        for parent, bank in (('first', 'A'), ('second', 'B')):
            folder = self.root / parent / 'My drums'
            folder.mkdir(parents=True)
            (folder / 'sample.wav').touch()
            maps.append({'path': str(folder), 'bank': bank, 'tag': 'KICK'})
        jobs, _ = generator.build_maps_plan(self.root, maps)
        self.assertNotEqual(jobs[0]['remote'], jobs[1]['remote'])

    def test_map_does_not_apply_historical_cowbell_filter(self):
        folder = self.root / '10 Percussion'
        folder.mkdir()
        for name in ('cowbell.wav', 'shaker.wav'):
            (folder / name).touch()
        jobs, _ = generator.build_maps_plan(self.root, [
            {'path': folder.name, 'bank': 'E', 'tag': 'PERCUSSION'}])
        self.assertEqual(len(jobs), 2)
        jobs, _ = generator.build_plan(self.root, None, [(folder.name, 1, None)])
        self.assertEqual(len(jobs), 1)

    def test_cli_requires_one_valid_tag_per_map(self):
        cases = [ ['--map', 'My textures:A'], ['--tag', 'PAD'],
                  ['--map', 'My textures:A', '--tag', 'INVALID'],
                  ['--map', 'My textures:A', '--tag', 'PAD', '--tag', 'BASS'],
                  ['--map', 'My textures:A', '--tag', 'PAD', '--map', 'Other:B'] ]
        for args in cases:
            with self.subTest(args=args), patch('sys.stderr', io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    generator.parse_args([str(self.root), *args])
                self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
