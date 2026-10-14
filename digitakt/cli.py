"""CLI configuration and orchestration; dependencies passed to execution."""

import argparse
from pathlib import Path
import time
import uuid
import shlex
from .planning import (MapAction, MapOptionAction, parse_map, parse_range,
                       parse_folder_spec, build_plan, build_maps_plan, DEFAULT_MAPPING_HELP,
                       CapacityError)
from .sound import create_default_sound, make_sound_data, FOLDER_TAGS, TAG_NAMES, TAGS
from .transport import Config, cmd, DTSession, verify_device
from .transport import check_destinations as list_destinations
from .execution import execute_jobs, replace_sound
from .presentation import print_plan, confirm_execution
from .reporting import TransferReport

BASE = Path(__file__).resolve().parents[1]
CLI = BASE / 'src/elektroid-cli'
DEVICE = '1'  # Compatibility default only; never changed by main().


def check_destinations(jobs, config=None):
    config = config or Config(CLI, DEVICE, BASE / 'generated_sounds')
    return list_destinations(jobs, config, runner=cmd)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='Build Digitakt I sound banks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=DEFAULT_MAPPING_HELP + '\n\nExample usage:\n'
               '  ./dt-build-banks "/path/to/sample-library" \\\n'
               '    -m "03 Claps:D" --tag CLAP -r 1:10 -f 1 -n\n\n'
               '  ROOT is "/path/to/sample-library", containing the "03 Claps" folder.\n'
               '  -n previews transfers without MIDI connection or writes.\n\n'
               'Combine multiple mappings in one command:\n'
               '  ./dt-build-banks "/path/to/sample-library" \\\n'
               '    -m "03 Claps:D" --tag CLAP -r 1:10 -f 1 \\\n'
               '    -m "02 Snares:B" --tag SNARE -l 10 -f 20 -n\n\n'
               '  Repeat -m/--map to combine folders and destination banks.\n'
               '  --tag is required for each mapping; folder names are unrestricted.\n'
               '  --tag, -r, -l and -f apply to the preceding mapping until the next -m/--map.\n\n'
               'Available tags (Digitakt I):\n  ' + ', '.join(TAGS) + '\n\n'
               'Populate banks A-H (up to 256 available samples per bank):\n'
               '  ./src/elektroid-cli ld\n'
               '  Replace INDEX below with the current Digitakt MIDI index.\n'
               '  Preview first:\n'
               '    ./dt-build-banks "/path/to/sample-library" --limit 256 --device INDEX -n\n'
               '  Write after reviewing the preview (confirmation required):\n'
               '    ./dt-build-banks "/path/to/sample-library" --limit 256 --device INDEX\n\n'
               '  Filling all 2,048 slots requires 256 eligible WAVs per category after filters.\n'
               '  Samples are not repeated; fewer WAVs leave remaining slots unchanged.\n'
               '  Target slots are cleared and overwritten; no automatic backup.')
    parser.add_argument('root', type=Path, help='root directory containing sample folders')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='Preview planned transfers without MIDI connection or writes. '
                             'Without this option, execute after confirmation.')
    parser.add_argument('-l', '--limit', type=int, action=MapOptionAction, help='maximum per selection')
    parser.add_argument('--folder', action='append', type=parse_folder_spec,
                        metavar='FOLDER[:FIRST:LAST]', help='legacy selection, repeatable')
    parser.add_argument('-b', '--bank', help='bank A–H (one --folder only)')
    parser.add_argument('-s', '--start-slot', type=int, help='first destination slot (one --folder only)')
    parser.add_argument('-m', '--map', dest='maps', type=parse_map, action=MapAction,
                        help='FOLDER:BANK; repeatable; starts a selection group')
    parser.add_argument('--tag', type=str.upper, choices=TAGS, action=MapOptionAction,
                        metavar='TAG', help='required tag for the preceding --map; see available tags below')
    parser.add_argument('-r', '--range', type=parse_range, action=MapOptionAction,
                        help='FIRST:LAST source range for the preceding --map')
    parser.add_argument('-f', '--from-slot', type=int, action=MapOptionAction,
                        help='first destination slot for the preceding --map, default 1')
    parser.add_argument('-d', '--device', type=int, default=int(DEVICE), help='MIDI device index, default 1')
    parser.add_argument('-v', '--verbose', action='store_true', help='show individual files and phase timings')
    parser.add_argument('--report', type=Path, metavar='PATH',
                        help='CSV mapping and outcomes; default: a new file in generated_sounds. '
                             'Existing files are never overwritten.')
    args = parser.parse_args(argv)
    if args.device < 0:
        parser.error('--device must be a non-negative integer')
    if args.maps and (args.folder or args.bank or args.start_slot is not None or args.limit is not None):
        parser.error('--map cannot be combined with --folder, --bank, --start-slot or a global limit')
    for mapping in args.maps or []:
        if 'tag' not in mapping:
            parser.error(f"--map {mapping['path']}:{mapping['bank']} requires --tag TAG")
    return args


def main(argv=None):
    args = parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f'Root directory not found: {root}')
    create_default_sound()
    if not CLI.is_file():
        raise SystemExit(f'elektroid-cli not found: {CLI}')
    if not args.maps and not args.folder:
        print('No --map/--folder provided: samples use category-based banks A-H.')
        print(DEFAULT_MAPPING_HELP + '\n')
    try:
        jobs, summary = (build_maps_plan(root, args.maps) if args.maps else
                         build_plan(root, args.limit, args.folder, args.bank, args.start_slot))
    except CapacityError as exc:
        if args.maps or args.folder:
            raise
        command = shlex.join(['./dt-build-banks', str(root), '--limit', '256',
                              '--device', str(args.device), '-n'])
        raise SystemExit(f'{exc}\nPreview up to 256 WAVs per default bank from slot 1:\n'
                         f'  {command}') from None
    config = Config(CLI, str(args.device), BASE / 'generated_sounds')
    print_plan(jobs, summary, args.verbose, config.device)
    if not jobs:
        raise SystemExit('No WAV files found.')
    report_path = args.report or config.work / f'transfer-report-{uuid.uuid4().hex}.csv'
    try:
        report = TransferReport(report_path, jobs, config.work, dry_run=args.dry_run)
    except OSError as exc:
        raise SystemExit(f'Cannot create transfer report: {exc}') from exc
    print(f'Report: {report.path}')
    if args.dry_run:
        print('\nNo uploads performed. Remove --dry-run to execute after confirmation.')
        return
    verify_device(config, runner=cmd)
    occupied = check_destinations(jobs, config)
    confirm_execution(jobs, occupied)
    print('Starting in 3 seconds (Ctrl-C to cancel)...')
    time.sleep(3)
    execute_jobs(jobs, config, runner=cmd, session_factory=DTSession,
                 verbose=args.verbose, report=report)
