"""One final retry pass; no readback or implicit backup."""

import re
import time
from .sound import make_sound_data
from .transport import cmd, DTSession
from .presentation import format_slot_ranges, print_progress
from .reporting import sound_name


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


def process_job(job, config, session, runner, state=None):
    state = state if state is not None else {}
    timings = state.setdefault('timings', {})
    name = sound_name(job)
    remote = f"/{job['remote']}/{job['remote_name']}"
    upload_wav = config.work / '_upload_clean' / f"{job['remote_name']}.wav"
    sound_file = config.work / f"{job['bank']}{job['slot']:03d}_{name}.data"
    path = f"/soundbanks/{job['bank']}/{job['slot']}"

    def metadata():
        state['metadata'] = parse_metadata(session.command('META', remote))

    steps = [
        ('ffmpeg', lambda: runner(['ffmpeg', '-y', '-v', 'error', '-i', job['wav'],
                                  '-map_metadata', '-1', '-c:a', 'pcm_s16le', upload_wav])),
        ('sample_upload', lambda: session.command('SAMPLE_UL', upload_wav, f"/{job['remote']}")),
        ('metadata', metadata),
        ('generate', lambda: make_sound_data(sound_file, job['bank'], job['slot'], name,
                                             *state['metadata'], job['source_folder'])),
        ('clear', lambda: session.command('DATA_CL', path)),
        ('sound_upload', lambda: session.command('DATA_UL', sound_file, path)),
    ]
    for phase, action in steps[state.get('next_step', 0):]:
        state['phase'] = phase
        start = (state.pop('clear_start') if phase == 'sound_upload' and 'clear_start' in state
                 else time.monotonic())
        action()
        if phase == 'clear':
            state['clear_start'] = start
        else:
            timings[phase] = time.monotonic() - start
        state['next_step'] = state.get('next_step', 0) + 1
    return timings


def execute_jobs(jobs, config, runner=cmd, session_factory=DTSession, verbose=False, report=None):
    prepare_directories(jobs, config, runner)
    durations = []
    states = [{} for job in jobs]
    completed = set()
    failures = {}
    recovered = 0
    consecutive = 0
    stopped = False

    def slots(indices):
        return format_slot_ranges(f"{jobs[i]['bank']}{jobs[i]['slot']:03d}"
                                  for i in sorted(indices)) or 'none'

    with session_factory(config.cli, config.device) as session:
        for retry in (False, True):
            indices = list(failures) if retry else list(range(len(jobs)))
            if retry and indices:
                print(f'Retrying {len(indices)} failed transfers (one final pass).')
            for i in indices:
                job = jobs[i]
                start = time.monotonic()
                try:
                    timings = process_job(job, config, session, runner, state=states[i])
                except KeyboardInterrupt:
                    if report is not None:
                        report.update(i, 'interrupted', states[i].get('phase', 'unknown'),
                                      'Interrupted by user; slot state may be uncertain')
                    raise
                except Exception as exc:
                    consecutive += 1
                    failures[i] = (states[i].get('phase', 'unknown'), str(exc))
                    if report is not None:
                        report.update(i, 'failed', *failures[i])
                    print(f"Failed {job['bank']}{job['slot']:03d} "
                          f"during {failures[i][0]}: {exc}")
                    if consecutive >= 10:
                        stopped = True
                        break
                    continue
                consecutive = 0
                completed.add(i)
                failures.pop(i, None)
                recovered += int(retry)
                if report is not None:
                    report.update(i, 'recovered' if retry else 'successful', 'complete')
                durations.append(time.monotonic() - start)
                print_progress(len(completed), len(jobs), job, durations, timings, verbose=verbose)
            if stopped:
                break
    pending = set(range(len(jobs))) - completed - set(failures)
    summary = (f'{len(completed)} successful ({recovered} recovered), '
               f'{len(failures)} failed. Completed: {slots(completed)}. '
               f'Failed: {slots(failures)}. Not executed: {slots(pending)}.')
    if failures or pending:
        details = '; '.join(f"{jobs[i]['bank']}{jobs[i]['slot']:03d} [{phase}]: {error}"
                            for i, (phase, error) in failures.items())
        reason = 'Stopped after 10 consecutive failures. ' if stopped else ''
        raise SystemExit(reason + summary + ' ' + details +
                         ' Failed slots may have been partially modified.')
    print(f'DONE — {summary} {sum(durations):.2f}s')
