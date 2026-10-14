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
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ('03 Claps', '02 Snares'):
            path = self.root / folder
            path.mkdir()
            for i in range(1, 11):
                (path / f'{i}.wav').touch()

    def test_two_independent_maps(self):
        maps = [{'path': '03 Claps', 'bank': 'A', 'range': (2, 5), 'limit': 2,
                 'from_slot': 10},
                {'path': str(self.root / '02 Snares'), 'bank': 'D', 'range': (4, 5),
                 'from_slot': 20}]
        jobs, _ = generator.build_maps_plan(self.root, maps)
        self.assertEqual([(j['bank'], j['slot'], j['source_rank']) for j in jobs],
                         [('A', 10, 2), ('A', 11, 3), ('D', 20, 4), ('D', 21, 5)])
        self.assertEqual(jobs[0]['source_folder'], '03 Claps')
        self.assertEqual(jobs[2]['source_folder'], '02 Snares')

    def test_collision_rejected(self):
        with self.assertRaisesRegex(SystemExit, 'collision'):
            generator.build_maps_plan(self.root, [
                {'path': '03 Claps', 'bank': 'A', 'limit': 2},
                {'path': '02 Snares', 'bank': 'A', 'limit': 2}])

    def test_overflow_rejected(self):
        with self.assertRaises(SystemExit):
            generator.build_maps_plan(self.root, [
                {'path': '03 Claps', 'bank': 'D', 'limit': 3, 'from_slot': 255}])

    def test_cli_grouped_dry_run(self):
        template = self.root / 'template.data'
        template.write_bytes(tag_tests.SoundTagsTest().generate('01 Kicks'))
        cli = self.root / 'cli'
        cli.touch()
        argv = ['dt-build-banks', str(self.root),
                '--map', '03 Claps:a', '--range', '2:5', '--limit', '2', '--from-slot', '10',
                '--map', '02 Snares:D', '--range', '4:5', '--from-slot', '20', '--dry-run']
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
            {'path': '03 Claps', 'bank': 'D', 'range': (1, 2), 'from_slot': 10},
            {'path': '03 Claps', 'bank': 'D', 'range': (4, 5), 'from_slot': 20}])
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
            {'path': '03 Claps', 'bank': 'D', 'limit': 1},
            {'path': '02 Snares', 'bank': 'B', 'limit': 1, 'from_slot': 20}])
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

    def test_unknown_category_rejected(self):
        path = self.root / 'Unknown'
        path.mkdir()
        with self.assertRaisesRegex(SystemExit, 'category'):
            generator.build_maps_plan(self.root, [{'path': str(path), 'bank': 'A'}])

    def test_duplicate_source_rejected(self):
        with self.assertRaisesRegex(SystemExit, 'source'):
            generator.build_maps_plan(self.root, [
                {'path': '03 Claps', 'bank': 'A', 'limit': 2},
                {'path': '03 Claps', 'bank': 'B', 'limit': 2}])


if __name__ == '__main__':
    unittest.main()
