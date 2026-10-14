import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digitakt.execution import execute_jobs
from digitakt.transport import DTSession, Config


class ExecutionTest(unittest.TestCase):
    def test_context_closes_on_error(self):
        with patch.object(DTSession, '__init__', return_value=None), \
                patch.object(DTSession, 'close') as close:
            with self.assertRaises(RuntimeError):
                with DTSession(Path('cli'), '13'):
                    raise RuntimeError('failure')
            close.assert_called_once()

    def test_abort_prevents_next_job_and_closes(self):
        jobs = [{'bank': 'D', 'slot': 1}, {'bank': 'D', 'slot': 2}]
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        process = Mock(side_effect=RuntimeError('failed'))
        with patch('digitakt.execution.process_job', process), \
                patch('digitakt.execution.prepare_directories'), \
                redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, 'D001'):
                execute_jobs(jobs, Config(Path('cli'), '13', Path('.')),
                             runner=Mock(), session_factory=Mock(return_value=session))
        self.assertEqual(process.call_count, 1)
        session.__exit__.assert_called_once()

    def test_configuration_is_immutable(self):
        config = Config(Path('cli'), '13', Path('.'))
        with self.assertRaises(AttributeError):
            config.device = '1'


if __name__ == '__main__':
    unittest.main()
