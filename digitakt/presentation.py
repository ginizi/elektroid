"""Console presentation, independent of MIDI and selection logic."""

from .sound import FOLDER_TAGS, TAG_NAMES


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
    print("\nPLAN D'ÉCRITURE")
    print(f'Indice MIDI : {device} (vérifié uniquement à l’exécution)\n')
    print(f"{'BANQUE':<8}{'SLOTS':<12}{'NB':>4}  {'TAG':<12}DOSSIER")
    for bank, label, count, folder, remote, first, last in summary:
        tag = TAG_NAMES[FOLDER_TAGS[folder.name]]
        slots = f'{first:03d}' if first == last else f'{first:03d}–{last:03d}'
        print(f'{bank:<8}{slots:<12}{count:>4}  {tag:<12}{folder.name}')
    print(f'\nTotal : {len(jobs)} sounds')
    print('Destinations : ' + format_slot_ranges(f"{j['bank']}{j['slot']:03d}" for j in jobs))
    if verbose:
        print('\nFICHIERS')
        for job in jobs:
            print(f"{job['wav']} (rang {job['source_rank']}) -> "
                  f"{job['bank']}{job['slot']:03d} {job['slot']:02d}_{job['label']} "
                  f"tag={TAG_NAMES[FOLDER_TAGS[job['source_folder']]]} "
                  f"sample=/{job['remote']}/{job['remote_name']}")


def confirm_execution(jobs, occupied):
    print(f'⚠ {len(jobs)} slots seront effacés puis réécrits.')
    print('  ' + format_slot_ranges(f"{j['bank']}{j['slot']:03d}" for j in jobs))
    print('Sounds remplacés : ' + (format_slot_ranges(occupied) or 'aucun'))
    print('Aucune sauvegarde automatique. Chaque slot sera effacé avant upload ; '
          'un échec peut le laisser vide.')
    try:
        answer = input('Confirmer les écritures en tapant OUI : ')
    except EOFError:
        raise SystemExit('Annulé : confirmation indisponible') from None
    if answer.strip() != 'OUI':
        raise SystemExit('Annulé : aucune écriture effectuée')


def print_progress(position, total, job, durations):
    elapsed = sum(durations)
    remaining = elapsed / position * (total - position)
    print(f"[{position}/{total}] {job['bank']}{job['slot']:03d} OK — "
          f'{durations[-1]:.2f}s ; restant estimé {remaining / 60:.1f} min', flush=True)
