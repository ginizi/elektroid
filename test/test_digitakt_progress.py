import io
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from digitakt.execution import process_job
from digitakt.presentation import print_progress
from digitakt.transport import Config


class ProgressTest(unittest.TestCase):
    def test_measured_phases_keep_command_order(self):
        events = []
        session = Mock()
        def command(*args):
            events.append(args[0])
            return 'SAMPLE_INFO id=0000021f size=35172 hash=386982b5'
        session.command.side_effect = command
        job = {'slot': 1, 'bank': 'D', 'label': 'CLAP', 'source_folder': '03 Claps',
               'remote': '01_CLAPS', 'remote_name': 'sample', 'wav': Path('sample.wav')}
        with patch('digitakt.execution.time.monotonic', side_effect=range(10)), \
                patch('digitakt.execution.make_sound_data'):
            timings = process_job(job, Config(Path('cli'), '13', Path('work')),
                                  session, Mock(side_effect=lambda args: events.append('ffmpeg')))
        self.assertEqual(events, ['ffmpeg', 'SAMPLE_UL', 'META', 'DATA_CL', 'DATA_UL'])
        self.assertEqual(timings, dict.fromkeys(
            ('ffmpeg', 'sample_upload', 'metadata', 'generate', 'sound_upload'), 1))

    def test_dashboard_and_no_escape_in_logs(self):
        stream = io.StringIO()
        job = {'bank': 'D', 'slot': 1, 'wav': Path('sample.wav')}
        with patch('sys.stdout', stream):
            print_progress(1, 2, job, [10], {'ffmpeg': 1, 'sound_upload': 3}, verbose=True)
        text = stream.getvalue()
        self.assertNotIn('\033', text)
        for label in ('Conversion', 'WAV upload', 'Metadata', 'Generation',
                      'Clear + sound', 'Elapsed', 'Remaining', 'Estimated finish', '50.0%'):
            self.assertIn(label, text)

    def test_terminal_refresh(self):
        stream = io.StringIO()
        stream.isatty = lambda: True
        with patch('sys.stdout', stream):
            print_progress(1, 1, {'bank': 'D', 'slot': 1, 'wav': Path('sample.wav')}, [1], {})
        self.assertTrue(stream.getvalue().startswith('\033[2J\033[H'))

    def test_default_progress_hides_phase_timings(self):
        stream = io.StringIO()
        with patch('sys.stdout', stream):
            print_progress(1, 2, {'bank': 'D', 'slot': 1, 'wav': Path('sample.wav')},
                           [10], {'ffmpeg': 1, 'sound_upload': 3})
        text = stream.getvalue()
        self.assertNotIn('Conversion', text)
        self.assertNotIn('Measured total', text)
        for label in ('Progress', 'Elapsed', 'Remaining', 'Estimated finish'):
            self.assertIn(label, text)


if __name__ == '__main__':
    unittest.main()
