import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from contextlib import redirect_stdout
import io
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from digitakt.reporting import TransferReport
from digitakt.execution import execute_jobs
from digitakt import cli


class ReportTest(unittest.TestCase):
    def job(self):
        return dict(bank='D', slot=10, label='CLAP', source_folder='03 Claps',
                    wav=Path('/source/clap,one.wav'), remote='01_CLAPS', remote_name='clap', tag='CLAP')

    def rows(self, path):
        with path.open(newline='', encoding='utf-8') as stream:
            return list(csv.DictReader(stream))

    def test_mapping_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.csv'
            TransferReport(path, [self.job()], Path(directory), dry_run=True)
            row = self.rows(path)[0]
            self.assertEqual(row['slot'], 'D010')
            self.assertEqual(row['sound_name'], '10_CLAP')
            self.assertEqual(row['source_path'], '/source/clap,one.wav')
            self.assertEqual(row['sample_path'], '/01_CLAPS/clap')
            self.assertEqual(row['tag'], 'CLAP')
            self.assertEqual(row['status'], 'planned')
            with self.assertRaises(FileExistsError):
                TransferReport(path, [self.job()], Path(directory))

    def test_retry_updates_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.csv'
            jobs = [self.job()]
            report = TransferReport(path, jobs, Path(directory))
            session = Mock()
            session.__enter__ = Mock(return_value=session)
            session.__exit__ = Mock(return_value=False)
            with patch('digitakt.execution.prepare_directories'), \
                    patch('digitakt.execution.print_progress'), \
                    patch('digitakt.execution.process_job', side_effect=[RuntimeError('failed'), {}]), \
                    redirect_stdout(io.StringIO()):
                execute_jobs(jobs, Mock(), session_factory=Mock(return_value=session), report=report)
            row = self.rows(path)[0]
            self.assertEqual(row['status'], 'recovered')
            self.assertEqual(row['attempts'], '2')
            self.assertIn('failed', row['last_error'])

    def test_dry_run_creates_report_without_midi(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / '03 Claps'
            folder.mkdir()
            (folder / 'clap.wav').touch()
            binary = root / 'cli'
            binary.touch()
            path = root / 'report.csv'
            with patch.object(cli, 'CLI', binary), patch.object(cli, 'cmd') as midi, \
                    redirect_stdout(io.StringIO()):
                cli.main([str(root), '-m', '03 Claps:D', '--tag', 'CLAP', '-n', '--report', str(path)])
            midi.assert_not_called()
            self.assertEqual(self.rows(path)[0]['status'], 'planned')


if __name__ == '__main__':
    unittest.main()
