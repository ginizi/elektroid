"""Persistent source-to-slot mappings and transfer outcomes, without MIDI."""

import csv
import os
from pathlib import Path
import tempfile
from .sound import FOLDER_TAGS, TAG_NAMES


def sound_name(job):
    return f"{job['slot']:02d}_{job['label']}"


class TransferReport:
    def __init__(self, path, jobs, work, dry_run=False):
        self.path = Path(path).expanduser().resolve()
        self.rows = []
        for job in jobs:
            name = sound_name(job)
            self.rows.append(dict(
                slot=f"{job['bank']}{job['slot']:03d}", sound_name=name,
                source_path=str(job['wav'].resolve()),
                sample_path=f"/{job['remote']}/{job['remote_name']}",
                tag=TAG_NAMES[FOLDER_TAGS[job['source_folder']]],
                sound_path=str((work / f"{job['bank']}{job['slot']:03d}_{name}.data").resolve()),
                status='planned' if dry_run else 'not_executed',
                attempts=0, phase='', last_error=''))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Reserve a new destination; never silently overwrite another report.
        with self.path.open('x', encoding='utf-8', newline='') as stream:
            self._write(stream)

    def _write(self, stream):
        fields = ('slot', 'sound_name', 'source_path', 'sample_path', 'tag',
                  'sound_path', 'status', 'attempts', 'phase', 'last_error')
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(self.rows)

    def update(self, index, status, phase='', error=''):
        row = self.rows[index]
        row.update(status=status, phase=phase, attempts=row['attempts'] + 1)
        if error:
            row['last_error'] = error
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                             dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                self._write(stream)
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
