"""Validated sound parameters and shared binary generation."""

from pathlib import Path
import zlib
from dt_sound_defaults import create_default_sound

TAGS = (
    'KICK', 'SNARE', 'RIMSHOT', 'CLAP', 'TOM', 'PERCUSSION', 'HI-HAT',
    'CYMBAL', 'COWBELL', 'SYNTH', 'BASS', 'LEAD', 'PAD', 'TEXTURE', 'CHORD',
    'SOUND FX', 'ELECTRONIC', 'METALLIC', 'ACOUSTIC', 'ATMOSPHERIC', 'NOISY',
    'GLITCH', 'HARD', 'SOFT', 'DARK', 'BRIGHT', 'VINTAGE', 'EPIC', 'FAIL',
    'LOOP', 'MINE', 'FAVOURITE',
)
TAG_VALUES = {name: 1 << bit for bit, name in enumerate(TAGS)}
TAG_NAMES = {value: name for name, value in TAG_VALUES.items()}
FOLDER_TAGS = {
    '01 Kicks': 1, '02 Snares': 2, '03 Claps': 8,
    '04 Hats Closed': 64, '05 Hats Open': 64, '07 Toms': 16,
    '08 Rims': 4, '09 Cymbals': 128, '10 Percussion': 32,
    '11 Bass': 1024, '13 Synth': 512, '15 FX': 32768, '16 Loops': 0x20000000,
}


def generate_sound(bank, slot, name, sample_id, sample_size, sample_hash, tag):
    """Return a sound without I/O; replace all variable fields before CRC."""
    if len(bank) != 1 or bank not in 'ABCDEFGH':
        raise RuntimeError(f'Banque invalide: {bank}')
    if not 1 <= slot <= 256:
        raise RuntimeError(f'Slot invalide: {slot}')
    if tag not in TAG_VALUES:
        raise RuntimeError(f'Tag inconnu: {tag}')
    encoded = name.encode('ascii')
    if len(encoded) > 15:
        raise RuntimeError(f'Nom Sound trop long: {name}')
    data = create_default_sound()
    index = (ord(bank) - ord('A')) * 256 + slot - 1
    data[21:25] = index.to_bytes(4, 'big')
    data[39:43] = TAG_VALUES[tag].to_bytes(4, 'big')
    data[43:59] = encoded.ljust(16, b'\0')
    references = (sample_id, sample_hash, sample_size + 16, sample_id + 0x28B8)
    data[0xA3:0xB3] = b''.join(value.to_bytes(4, 'big') for value in references)
    data[-12:-8] = (zlib.crc32(data[31:-12], 0xFFFFFFFF) & 0xFFFFFFFF).to_bytes(4, 'big')
    return bytes(data)


def make_sound_data(output, bank, slot, name, sample_id, sample_size, sample_hash, source_folder):
    if source_folder not in FOLDER_TAGS:
        raise RuntimeError(f'Aucune catégorie vérifiée pour: {source_folder}')
    tag = TAG_NAMES[FOLDER_TAGS[source_folder]]
    Path(output).write_bytes(generate_sound(bank, slot, name, sample_id, sample_size, sample_hash, tag))
