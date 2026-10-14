"""Local inventory and selection. No subprocess or MIDI dependencies."""

import argparse
from pathlib import Path
import re

BANKS = (
    ('A', 'KICK', ('01 Kicks',), '01_KICKS'),
    ('B', 'SNARE', ('02 Snares',), '01_SNARES'),
    ('C', 'TOM', ('07 Toms',), '01_TOMS'),
    ('D', 'CLAP', ('03 Claps',), '01_CLAPS'),
    ('E', 'COWBELL', ('10 Percussion',), '01_COWBELLS'),
    ('F', 'CLOSED_HAT', ('04 Hats Closed',), '01_CLOSED_HATS'),
    ('G', 'OPEN_HAT', ('05 Hats Open',), '01_OPEN_HATS'),
    ('H', 'CYMBAL', ('09 Cymbals',), '01_CYMBALS'),
)


def natural_key(value):
    return [int(part) if part.isdigit() else part.casefold()
            for part in re.split(r'(\d+)', value)]


def parse_range(value):
    try:
        first, last = (int(part) for part in value.split(':'))
    except ValueError:
        raise argparse.ArgumentTypeError('Expected format: FIRST:LAST') from None
    if not 1 <= first <= last:
        raise argparse.ArgumentTypeError('Range must satisfy 1 <= first <= last')
    return first, last


def category(name):
    for row in BANKS:
        if name in row[2]:
            return row
    raise SystemExit(f'Unsupported folder category: {name}')


def parse_folder_spec(value):
    if ':' in value:
        try:
            name, first, last = value.rsplit(':', 2)
        except ValueError:
            raise argparse.ArgumentTypeError('Expected format: FOLDER[:FIRST:LAST]') from None
        first, last = parse_range(f'{first}:{last}')
    else:
        name, first, last = value, 1, None
    if not any(name in row[2] for row in BANKS):
        raise argparse.ArgumentTypeError(f'Unknown folder: {name}')
    return name, first, last


def parse_map(value):
    try:
        path, bank = value.rsplit(':', 1)
    except ValueError:
        raise argparse.ArgumentTypeError('Expected format: FOLDER:BANK') from None
    bank = bank.upper()
    if not path or len(bank) != 1 or bank not in 'ABCDEFGH':
        raise argparse.ArgumentTypeError('A folder and a bank between A and H are required')
    return {'path': path, 'bank': bank}


class MapAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        namespace.maps = [*(namespace.maps or []), values]


class MapOptionAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not namespace.maps:
            if self.dest == 'limit':
                namespace.limit = values
                return
            parser.error(f'{option_string} must follow --map')
        if self.dest in namespace.maps[-1]:
            parser.error(f'{option_string} repeated in the same --map group')
        namespace.maps[-1][self.dest] = values


def inventory(folder):
    files = sorted((p for p in folder.rglob('*') if p.is_file()
                    and p.suffix.lower() == '.wav'),
                   key=lambda p: natural_key(str(p.relative_to(folder))))
    if folder.name == '10 Percussion':
        files = [p for p in files if re.search(r'cow[ _-]*bell|cowbell|cowbel|cowb',
                                             p.stem, re.IGNORECASE)]
    return files


def validate_jobs(jobs):
    slots, sources, names = set(), set(), set()
    for job in jobs:
        slot = (job['bank'], job['slot'])
        source = job['wav'].resolve()
        remote = (job['remote'], job['remote_name'].casefold())
        if slot in slots:
            raise SystemExit(f"Destination collision: {job['bank']}{job['slot']:03d}")
        if source in sources:
            raise SystemExit(f'Overlapping source selections: {source}')
        if remote in names:
            raise SystemExit(f'+Drive name collision: {remote}')
        slots.add(slot)
        sources.add(source)
        names.add(remote)


def plan_folder(folder, first, last, limit, bank=None, start=None):
    default_bank, label, _, remote = category(folder.name)
    if not folder.is_dir():
        raise SystemExit(f'Selected folder not found: {folder}')
    bank = (bank or default_bank).upper()
    if len(bank) != 1 or bank not in 'ABCDEFGH':
        raise SystemExit('Bank must be between A and H')
    if limit is not None and not 1 <= limit <= 256:
        raise SystemExit('--limit must be between 1 and 256')
    start = first if start is None else start
    if not 1 <= start <= 256:
        raise SystemExit('First destination slot must be between 1 and 256')
    files = inventory(folder)
    if not files:
        raise SystemExit(f'No selectable WAV files: {folder}')
    if first < 1 or (last is not None and last < first):
        raise SystemExit('Invalid source range')
    if first > len(files) or (last is not None and last > len(files)):
        raise SystemExit(f'Range unavailable in {folder}: {len(files)} samples available')
    files = files[first - 1:last]
    if limit is not None:
        files = files[:limit]
    available = 257 - start
    if len(files) > available:
        raise SystemExit(f'{len(files)} sounds requested, {available} slots available '
                         f'({start}–256). Choose a starting slot ≤ '
                         f'{257 - len(files)} or reduce the selection to {available} sounds.')
    jobs = []
    for offset, wav in enumerate(files):
        name = wav.stem[:32].rstrip(' .')
        if not name or any(c in name for c in '\t\r\n'):
            raise SystemExit(f'Invalid +Drive name: {wav.name}')
        try:
            wav.stem.encode('cp1252')
        except UnicodeEncodeError:
            raise SystemExit(f'Name cannot be encoded as CP1252: {wav.name}') from None
        jobs.append({'bank': bank, 'label': label, 'source_folder': folder.name,
                     'remote': remote, 'slot': start + offset, 'source_rank': first + offset,
                     'wav': wav, 'remote_name': name})
    return jobs, (bank, label, len(jobs), folder, remote, start, start + len(jobs) - 1)


def build_plan(root, limit, folders=None, bank=None, start_slot=None):
    if (bank is not None or start_slot is not None) and (not folders or len(folders) != 1):
        raise SystemExit('Explicit placement requires exactly one --folder')
    selections = folders if folders else [(row[2][0], 1, None) for row in BANKS
                                         if (root / row[2][0]).is_dir()]
    jobs, summary = [], []
    for name, first, last in selections:
        selected, details = plan_folder(root / name, first, last, limit, bank, start_slot)
        jobs.extend(selected)
        summary.append(details)
    validate_jobs(jobs)
    return jobs, summary


def build_maps_plan(root, maps):
    jobs, summary = [], []
    for mapping in maps:
        folder = Path(mapping['path']).expanduser()
        folder = (folder if folder.is_absolute() else root / folder).resolve()
        first, last = mapping.get('range', (1, None))
        selected, details = plan_folder(folder, first, last, mapping.get('limit'),
                                        mapping['bank'], mapping.get('from_slot', 1))
        jobs.extend(selected)
        summary.append(details)
    validate_jobs(jobs)
    return jobs, summary
