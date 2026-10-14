"""Single-pass execution; no retry, readback or implicit backup."""

import re
import time
from .sound import make_sound_data
from .transport import cmd, DTSession
from .presentation import format_slot_ranges, print_progress


def replace_sound(session, sound_file, bank, slot):
    path = f'/soundbanks/{bank}/{slot}'
    session.command('DATA_CL', path)
    session.command('DATA_UL', sound_file, path)


def prepare_directories(jobs, config, runner):
    config.work.mkdir(exist_ok=True)
    (config.work / '_upload_clean').mkdir(exist_ok=True)
    for remote in dict.fromkeys(job['remote'] for job in jobs):
        runner([config.cli, 'elektron:sample:mkdir', f'{config.device}:/{remote}'])


def parse_metadata(output):
    match = re.search(r'SAMPLE_INFO id=([0-9A-Fa-f]{8}) size=([0-9]+) '
                      r'hash=([0-9A-Fa-f]{8})', output)
    if not match:
        raise RuntimeError(f'SAMPLE_INFO not found:\n{output}')
    return int(match[1], 16), int(match[2]), int(match[3], 16)


def process_job(job, config, session, runner):
    timings = {}
    name = f"{job['slot']:02d}_{job['label']}"
    remote = f"/{job['remote']}/{job['remote_name']}"
    upload_wav = config.work / '_upload_clean' / f"{job['remote_name']}.wav"
    start = time.monotonic()
    runner(['ffmpeg', '-y', '-v', 'error', '-i', job['wav'],
            '-map_metadata', '-1', '-c:a', 'pcm_s16le', upload_wav])
    timings['ffmpeg'] = time.monotonic() - start
    start = time.monotonic()
    session.command('SAMPLE_UL', upload_wav, f"/{job['remote']}")
    timings['sample_upload'] = time.monotonic() - start
    start = time.monotonic()
    sample_id, size, sample_hash = parse_metadata(session.command('META', remote))
    timings['metadata'] = time.monotonic() - start
    start = time.monotonic()
    sound_file = config.work / f"{job['bank']}{job['slot']:03d}_{name}.data"
    make_sound_data(sound_file, job['bank'], job['slot'], name,
                    sample_id, size, sample_hash, job['source_folder'])
    timings['generate'] = time.monotonic() - start
    start = time.monotonic()
    replace_sound(session, sound_file, job['bank'], job['slot'])
    timings['sound_upload'] = time.monotonic() - start
    return timings


def execute_jobs(jobs, config, runner=cmd, session_factory=DTSession, verbose=False):
    prepare_directories(jobs, config, runner)
    durations = []
    with session_factory(config.cli, config.device) as session:
        for position, job in enumerate(jobs, 1):
            start = time.monotonic()
            try:
                timings = process_job(job, config, session, runner)
            except Exception as exc:
                completed = format_slot_ranges(f"{j['bank']}{j['slot']:03d}"
                                               for j in jobs[:position - 1]) or 'none'
                pending = format_slot_ranges(f"{j['bank']}{j['slot']:03d}"
                                             for j in jobs[position:]) or 'none'
                raise SystemExit(f"Stopped at {job['bank']}{job['slot']:03d}: {exc}. "
                                 f'Completed: {completed}. Not executed: {pending}. '
                                 'The failed slot may have been partially modified.') from exc
            durations.append(time.monotonic() - start)
            print_progress(position, len(jobs), job, durations, timings, verbose=verbose)
    print(f'DONE — {len(jobs)} successful, 0 failed, {sum(durations):.2f}s')
