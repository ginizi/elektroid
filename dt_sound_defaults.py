"""Digitakt I 1.53 sound defaults from the hardware-validated A007 model.

These are model parameters, not a decoded specification of every sound field.
Generators replace the name, tags, file index and all sample references.
No external template file is required.
"""

import zlib


DEFAULT_SOUND = bytes.fromhex(
    "ac11d303020004000830313034000000030000000300000006000000a0000c"
    "beefbace000000030000000130375f4b49434b000000000000000000000070007000"
    "040004004000400000000000000001000000000000000000400040004000030000"
    "000b00000078000000640001007f0000004000000040000000400000007f000000"
    "000000007f00400000000000000040006e0000000000000000010008fffd674800"
    "0002273f9ae4350000f40200002adf0000001a001b0000bacef00c43777daf000000a0aaa1daaa"
)


def create_default_sound():
    """Return an independent, validated copy of the built-in sound model."""
    data = DEFAULT_SOUND
    if (len(data) != 203 or data[:4] != bytes.fromhex("ac11d303")
            or data[29:31] != bytes([0, 12])
            or int.from_bytes(data[25:29], "big") != 160
            or int.from_bytes(data[-8:-4], "big") != 160
            or data[-4:] != bytes.fromhex("aaa1daaa")
            or int.from_bytes(data[-12:-8], "big")
            != zlib.crc32(data[31:-12], 0xFFFFFFFF) & 0xFFFFFFFF):
        raise RuntimeError("Paramètres sound intégrés invalides")
    return bytearray(data)
