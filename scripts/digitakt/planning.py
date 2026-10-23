"""Local inventory and selection. No subprocess or MIDI dependencies."""

import argparse
from pathlib import Path
import re
import hashlib
from .sound import TAG_VALUES, TAG_NAMES, FOLDER_TAGS

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

DEFAULT_MAPPING_HELP = (
    'Default mapping (without --map/--folder):\n'
    '  A Kicks       B Snares      C Toms         D Claps\n'
    '  E Cowbells    F Closed hats G Open hats    H Cymbals\n'
    'Each category stays in its assigned bank (256 slots maximum).\n'
    'Samples do not overflow into another bank. Missing folders are skipped.\n'
    '"10 Percussion" uses the historical cowbell filter.\n'
    '--limit applies per bank in this default mode.'
)


class CapacityError(SystemExit):
    """Selection exceeds its bank; the CLI can supply a contextual suggestion."""


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


def inventory(folder, filter_cowbells=True):
    files = sorted((p for p in folder.rglob('*') if p.is_file()
                    and p.suffix.lower() == '.wav'),
                   key=lambda p: natural_key(str(p.relative_to(folder))))
    if filter_cowbells and folder.name == '10 Percussion':
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


def plan_folder(folder, first, last, limit, bank=None, start=None, tag=None):
    explicit_tag = tag is not None
    if explicit_tag:
        if tag not in TAG_VALUES:
            raise SystemExit(f'Unknown tag: {tag}')
        default_bank = bank
        label = tag.replace(' ', '_')[:11]
        known = next((row for row in BANKS if folder.name in row[2]), None)
        if known:
            remote = known[3]
        else:
            basename = re.sub(r'[^A-Za-z0-9_-]+', '_', folder.name).strip('_')[:32] or 'samples'
            digest = hashlib.sha256(str(folder.resolve()).encode()).hexdigest()[:12]
            remote = f'mapped_{basename}-{digest}'
    else:
        default_bank, label, _, remote = category(folder.name)
        tag = TAG_NAMES[FOLDER_TAGS[folder.name]]
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
    files = inventory(folder, filter_cowbells=not explicit_tag)
    eligible = len(files)
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
        raise CapacityError(
            f'The folder "{folder.name}" ({folder}) contains {eligible:,} eligible WAV files.\n'
            f'This selection sends {len(files):,} files to bank {bank}, starting at slot {start}.\n'
            f'Bank {bank} holds at most 256 sounds; {available} slots available '
            f'({bank}{start:03d}–{bank}256). This selection exceeds its capacity.\n'
            'The command was cancelled before any transfer, including to other banks.\n\n'
            f'Reduce this selection to at most {available} WAVs with --limit {available}, '
            'or choose a smaller --map/--range selection.\n'
            'Without --map/--folder, --limit applies to each default bank.')
    jobs = []
    for offset, wav in enumerate(files):
        name = wav.stem[:32].rstrip(' .')
        if not name or any(c in name for c in '\t\r\n'):
            raise SystemExit(f'Invalid +Drive name: {wav.name}')
        try:
            wav.stem.encode('cp1252')
        except UnicodeEncodeError:
            raise SystemExit(f'Name cannot be encoded as CP1252: {wav.name}') from None
        jobs.append({'bank': bank, 'label': label, 'source_folder': folder.name, 'tag': tag,
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
        if 'tag' not in mapping:
            raise SystemExit(f"Each --map requires --tag: {mapping['path']}")
        folder = Path(mapping['path']).expanduser()
        folder = (folder if folder.is_absolute() else root / folder).resolve()
        first, last = mapping.get('range', (1, None))
        selected, details = plan_folder(folder, first, last, mapping.get('limit'),
                                        mapping['bank'], mapping.get('from_slot', 1), mapping['tag'])
        jobs.extend(selected)
        summary.append(details)
    validate_jobs(jobs)
    return jobs, summary
