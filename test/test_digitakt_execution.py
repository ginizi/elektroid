import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digitakt.execution import execute_jobs, process_job
from digitakt.transport import DTSession, Config


class ExecutionTest(unittest.TestCase):
    def test_context_closes_on_error(self):
        with patch.object(DTSession, '__init__', return_value=None), \
                patch.object(DTSession, 'close') as close:
            with self.assertRaises(RuntimeError):
                with DTSession(Path('cli'), '13'):
                    raise RuntimeError('failure')
            close.assert_called_once()

    def test_failure_continues_and_retries_once(self):
        jobs = [{'bank': 'D', 'slot': 1}, {'bank': 'D', 'slot': 2}]
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        process = Mock(side_effect=[RuntimeError('failed'), {}, {}])
        with patch('digitakt.execution.process_job', process), \
                patch('digitakt.execution.prepare_directories'), \
                patch('digitakt.execution.print_progress'), \
                redirect_stdout(io.StringIO()):
            execute_jobs(jobs, Config(Path('cli'), '13', Path('.')),
                         runner=Mock(), session_factory=Mock(return_value=session))
        self.assertEqual([call.args[0]['slot'] for call in process.call_args_list],
                         [1, 2, 1])
        session.__exit__.assert_called_once()

    def run_attempts(self, count, effects):
        jobs = [{'bank': 'D', 'slot': i + 1} for i in range(count)]
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        process = Mock(side_effect=effects)
        output = io.StringIO()
        with patch('digitakt.execution.process_job', process), \
                patch('digitakt.execution.prepare_directories'), \
                patch('digitakt.execution.print_progress'), redirect_stdout(output):
            try:
                execute_jobs(jobs, Config(Path('cli'), '13', Path('.')),
                             runner=Mock(), session_factory=Mock(return_value=session))
            except SystemExit as exc:
                error = str(exc)
            else:
                error = None
        session.__exit__.assert_called_once()
        return process.call_count, error, output.getvalue()

    def test_ten_consecutive_failures_stop_without_retry(self):
        calls, error, output = self.run_attempts(12, RuntimeError('failed'))
        self.assertEqual(calls, 10)
        self.assertIn('10 consecutive failures', error)
        self.assertIn('D011–D012', error)

    def test_success_resets_consecutive_failures(self):
        effects = [RuntimeError('failed')] * 9 + [{}] + [RuntimeError('failed')] * 9
        calls, error, output = self.run_attempts(19, effects + [{}] * 18)
        self.assertEqual(calls, 37)
        self.assertIsNone(error)

    def test_retry_is_single_pass_and_failure_exits_nonzero(self):
        calls, error, output = self.run_attempts(2, RuntimeError('failed'))
        self.assertEqual(calls, 4)
        self.assertIn('D001–D002', error)

    def test_retry_stops_after_ten_consecutive_failures(self):
        effects = [RuntimeError('failed'), {}] * 11 + [RuntimeError('failed')] * 10
        calls, error, output = self.run_attempts(22, effects)
        self.assertEqual(calls, 32)
        self.assertIn('10 consecutive failures', error)

    def test_retry_upload_does_not_clear_again(self):
        job = dict(bank='D', slot=1, label='CLAP', remote='claps',
                   remote_name='clap', wav='clap.wav', source_folder='03 Claps')
        session = Mock()
        session.command.side_effect = [None,
            'SAMPLE_INFO id=00000001 size=100 hash=00000002', None,
            RuntimeError('upload failed'), None]
        state = {}
        with patch('digitakt.execution.make_sound_data'):
            with self.assertRaises(RuntimeError):
                process_job(job, Config(Path('cli'), '13', Path('.')),
                            session, Mock(), state=state)
            process_job(job, Config(Path('cli'), '13', Path('.')),
                        session, Mock(), state=state)
        commands = [call.args[0] for call in session.command.call_args_list]
        self.assertEqual(commands, ['SAMPLE_UL', 'META', 'DATA_CL', 'DATA_UL', 'DATA_UL'])

    def test_configuration_is_immutable(self):
        config = Config(Path('cli'), '13', Path('.'))
        with self.assertRaises(AttributeError):
            config.device = '1'


if __name__ == '__main__':
    unittest.main()
