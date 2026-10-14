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
    parser = argparse.ArgumentParser(description='Construction des Sound Banks Digitakt I')
    parser.add_argument('root', type=Path, help='racine des dossiers de samples')
    parser.add_argument('--dry-run', action='store_true', help='aperçu sans MIDI ni écriture')
    parser.add_argument('--limit', type=int, action=MapOptionAction, help='maximum par sélection')
    parser.add_argument('--folder', action='append', type=parse_folder_spec,
                        metavar='DOSSIER[:DÉBUT:FIN]', help='sélection historique, répétable')
    parser.add_argument('--bank', help='banque A–H (un seul --folder)')
    parser.add_argument('--start-slot', type=int, help='premier slot (un seul --folder)')
    parser.add_argument('--map', dest='maps', type=parse_map, action=MapAction,
                        help='DOSSIER:BANQUE ; ouvre un groupe')
    parser.add_argument('--range', type=parse_range, action=MapOptionAction,
                        help='DÉBUT:FIN du dernier --map')
    parser.add_argument('--from-slot', type=int, action=MapOptionAction,
                        help='premier slot du dernier --map, défaut 1')
    parser.add_argument('--device', type=int, default=int(DEVICE), help='indice MIDI, défaut 1')
    parser.add_argument('--verbose', action='store_true', help='détail des fichiers')
    args = parser.parse_args(argv)
    if args.device < 0:
        parser.error('--device doit être un entier non négatif')
    if args.maps and (args.folder or args.bank or args.start_slot is not None or args.limit is not None):
        parser.error('--map ne se mélange pas avec --folder, --bank, --start-slot ou une limite globale')
    return args


def main(argv=None):
    args = parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f'Racine introuvable: {root}')
    create_default_sound()
    if not CLI.is_file():
        raise SystemExit(f'elektroid-cli introuvable: {CLI}')
    jobs, summary = (build_maps_plan(root, args.maps) if args.maps else
                     build_plan(root, args.limit, args.folder, args.bank, args.start_slot))
    config = Config(CLI, str(args.device), BASE / 'generated_sounds')
    print_plan(jobs, summary, args.verbose, config.device)
    if not jobs:
        raise SystemExit('Aucun WAV trouvé.')
    if args.dry_run:
        print('\nAucun upload effectué. Relance sans --dry-run pour exécuter après confirmation.')
        return
    verify_device(config, runner=cmd)
    occupied = check_destinations(jobs, config)
    confirm_execution(jobs, occupied)
    print('Démarrage dans 3 secondes (Ctrl-C pour annuler)...')
    time.sleep(3)
    execute_jobs(jobs, config, runner=cmd, session_factory=DTSession)
