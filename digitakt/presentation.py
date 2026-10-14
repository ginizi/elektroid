"""Console presentation, independent of MIDI and selection logic."""

from .sound import FOLDER_TAGS, TAG_NAMES
from datetime import datetime, timedelta
import sys


def format_slot_ranges(slots):
    groups = {}
    for slot in sorted(set(slots)):
        groups.setdefault(slot[0], []).append(int(slot[1:]))
    result = []
    for bank, numbers in groups.items():
        first = last = numbers[0]
        for number in numbers[1:] + [None]:
            if number is not None and number == last + 1:
                last = number
                continue
            result.append(f'{bank}{first:03d}' if first == last
                          else f'{bank}{first:03d}–{bank}{last:03d}')
            first = last = number
    return ' · '.join(result)


def print_plan(jobs, summary, verbose=False, device='1'):
    print('\nDESTINATION BANKS')
    banks = dict.fromkeys(job['bank'] for job in jobs)
    for bank in banks:
        bank_jobs = [job for job in jobs if job['bank'] == bank]
        slots = format_slot_ranges(f"{bank}{job['slot']:03d}" for job in bank_jobs)
        print(f'\nBANK {bank} — slots {slots} — {len(bank_jobs)} sounds')
        print(f"{'SLOT':<7}{'TAG':<13}SOURCE FILE")
        for job in bank_jobs:
            tag = TAG_NAMES[FOLDER_TAGS[job['source_folder']]]
            print(f"{bank}{job['slot']:03d}   {tag:<13}{job['wav'].name}")
            if verbose:
                print(f"       Source: {job['wav']} (rank {job['source_rank']})")
                print(f"       Sound: {job['slot']:02d}_{job['label']}")
                print(f"       +Drive WAV: /{job['remote']}/{job['remote_name']}")
    bank_label = 'bank' if len(banks) == 1 else 'banks'
    print(f'\nTotal: {len(jobs)} sounds across {len(banks)} {bank_label}')
    print(f'MIDI index: {device} (checked only when executing)')


def confirm_execution(jobs, occupied):
    print(f'⚠ {len(jobs)} slots will be cleared and overwritten.')
    print('  ' + format_slot_ranges(f"{j['bank']}{j['slot']:03d}" for j in jobs))
    print('Sounds to replace: ' + (format_slot_ranges(occupied) or 'none'))
    print('No automatic backup. Each slot will be cleared before upload; '
          'a failure may leave it empty.')
    try:
        answer = input('Type YES to confirm writes: ')
    except EOFError:
        raise SystemExit('Cancelled: confirmation unavailable') from None
    if answer.strip() not in ('YES', 'OUI'):
        raise SystemExit('Cancelled: no writes performed')


def format_duration(seconds):
    seconds = max(0, round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


def print_progress(position, total, job, durations, timings, verbose=False):
    elapsed = sum(durations)
    remaining = elapsed / position * (total - position)
    finish = datetime.now() + timedelta(seconds=remaining)
    filled = 30 * position // total
    bar = '#' * filled + '-' * (30 - filled)
    if sys.stdout.isatty():
        print('\033[2J\033[H', end='')
    print('=' * 72)
    print(f"[{position}/{total}] {job['bank']}{job['slot']:03d}  {job['wav'].name}")
    print(f'Progress: [{bar}] {100 * position / total:.1f}%')
    print(f'Successful: {position}  Failed: 0  Status: OK\n')
    if verbose:
        print('Last sound timings')
        for label, key in (('Conversion', 'ffmpeg'), ('WAV upload', 'sample_upload'),
                           ('Metadata', 'metadata'), ('Generation', 'generate'),
                           ('Clear + sound', 'sound_upload')):
            value = timings.get(key)
            text = '---' if value is None else f'{value:.2f} s'
            print(f'{label:<17}: {text}')
        print(f'Measured total   : {sum(timings.values()):.2f} s\n')
    print(f'Last sound       : {format_duration(durations[-1])}')
    print(f'Elapsed          : {format_duration(elapsed)}')
    print(f'Remaining        : ~{format_duration(remaining)}')
    print(f'Estimated finish : {finish:%H:%M:%S}', flush=True)
