"""CLI configuration and orchestration; dependencies passed to execution."""

import argparse
from pathlib import Path
import time
from .planning import (MapAction, MapOptionAction, parse_map, parse_range,
                       parse_folder_spec, build_plan, build_maps_plan)
from .sound import create_default_sound, make_sound_data, FOLDER_TAGS, TAG_NAMES
from .transport import Config, cmd, DTSession, verify_device
from .transport import check_destinations as list_destinations
from .execution import execute_jobs, replace_sound
from .presentation import print_plan, confirm_execution

BASE = Path(__file__).resolve().parents[1]
CLI = BASE / 'src/elektroid-cli'
DEVICE = '1'  # Compatibility default only; never changed by main().


def check_destinations(jobs, config=None):
    config = config or Config(CLI, DEVICE, BASE / 'generated_sounds')
    return list_destinations(jobs, config, runner=cmd)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Build Digitakt I sound banks')
    parser.add_argument('root', type=Path, help='root directory containing sample folders')
    parser.add_argument('-n', '--dry-run', action='store_true', help='preview without MIDI or writes')
    parser.add_argument('-l', '--limit', type=int, action=MapOptionAction, help='maximum per selection')
    parser.add_argument('--folder', action='append', type=parse_folder_spec,
                        metavar='FOLDER[:FIRST:LAST]', help='legacy selection, repeatable')
    parser.add_argument('-b', '--bank', help='bank A–H (one --folder only)')
    parser.add_argument('-s', '--start-slot', type=int, help='first destination slot (one --folder only)')
    parser.add_argument('-m', '--map', dest='maps', type=parse_map, action=MapAction,
                        help='FOLDER:BANK; starts a selection group')
    parser.add_argument('-r', '--range', type=parse_range, action=MapOptionAction,
                        help='FIRST:LAST source range for the preceding --map')
    parser.add_argument('-f', '--from-slot', type=int, action=MapOptionAction,
                        help='first destination slot for the preceding --map, default 1')
    parser.add_argument('-d', '--device', type=int, default=int(DEVICE), help='MIDI device index, default 1')
    parser.add_argument('-v', '--verbose', action='store_true', help='show individual files and phase timings')
    args = parser.parse_args(argv)
    if args.device < 0:
        parser.error('--device must be a non-negative integer')
    if args.maps and (args.folder or args.bank or args.start_slot is not None or args.limit is not None):
        parser.error('--map cannot be combined with --folder, --bank, --start-slot or a global limit')
    return args


def main(argv=None):
    args = parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f'Root directory not found: {root}')
    create_default_sound()
    if not CLI.is_file():
        raise SystemExit(f'elektroid-cli not found: {CLI}')
    jobs, summary = (build_maps_plan(root, args.maps) if args.maps else
                     build_plan(root, args.limit, args.folder, args.bank, args.start_slot))
    config = Config(CLI, str(args.device), BASE / 'generated_sounds')
    print_plan(jobs, summary, args.verbose, config.device)
    if not jobs:
        raise SystemExit('No WAV files found.')
    if args.dry_run:
        print('\nNo uploads performed. Remove --dry-run to execute after confirmation.')
        return
    verify_device(config, runner=cmd)
    occupied = check_destinations(jobs, config)
    confirm_execution(jobs, occupied)
    print('Starting in 3 seconds (Ctrl-C to cancel)...')
    time.sleep(3)
    execute_jobs(jobs, config, runner=cmd, session_factory=DTSession, verbose=args.verbose)
