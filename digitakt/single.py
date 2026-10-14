"""Individual generator using the same binary implementation as the batch."""

import argparse
from pathlib import Path
from .sound import generate_sound, TAG_VALUES
from .transport import cmd

BASE = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description='Generate a Digitakt I sound')
    parser.add_argument('sample_path')
    parser.add_argument('bank', type=str.upper, choices=list('ABCDEFGH'))
    parser.add_argument('slot', type=int)
    parser.add_argument('name')
    parser.add_argument('tag', choices=TAG_VALUES)
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.slot <= 256:
        parser.error('slot must be between 1 and 256')
    metadata = dict(line.split('=', 1) for line in
                    cmd([BASE / 'scripts/dt-sample-meta', args.sample_path]).splitlines())
    data = generate_sound(args.bank, args.slot, args.name, int(metadata['ID'], 16),
                          int(metadata['SIZE']), int(metadata['HASH'], 16), args.tag)
    output = Path(f'{args.bank}{args.slot:03d}_{args.name}.data')
    output.write_bytes(data)
    print(f'Sound generated: {output}; tag={args.tag}')
    if args.upload:
        # Preserve the legacy individual wrapper's device behavior.
        cmd([BASE / 'src/elektroid-cli', 'elektron:data:ul', output,
             f'1:/soundbanks/{args.bank}/{args.slot}'])


if __name__ == '__main__':
    main()
