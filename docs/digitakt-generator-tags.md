# Digitakt I generator tags

The experimental generators use built-in Digitakt I sound parameters and
require no template file or template argument. Tag values were verified on
firmware 1.53.

The shared `dt_sound_defaults.py` module contains the hardware-validated A007
model as immutable bytes and returns an independent validated copy. This is
an internal model, not a complete decoded specification or a claim to match
factory INIT settings. The generators replace its name, tags, file index and
sample references and recalculate the CRC. Keep the module beside the scripts.

## Python organization

Both commands are thin entry points. Keep the `digitakt/` package beside
them; no installation framework or new Python dependency is required.

| Module | Responsibility |
| --- | --- |
| `cli` | Parse options, create immutable configuration, orchestrate preflight |
| `planning` | Inventory, ranges, destinations, capacity and collisions; no MIDI |
| `sound` | Shared pure binary generation, tags and CRC |
| `transport` | Process boundary and MIDI session lifecycle |
| `execution` | Convert sample, retrieve metadata, generate, clear and upload |
| `presentation` | Compact preview, confirmation and progress |
| `single` | Individual generator CLI using the shared sound implementation |

The configuration is passed explicitly: parsing `--device` does not mutate
a global device value. Execution accepts a command runner and session factory
for offline tests. The session is a context manager and closes on success,
failure or interruption. The batch has one pass, no retry and no automatic
download. Progress shows elapsed/remaining time and estimated finish.
With `--verbose`, it also shows conversion, WAV upload, metadata, generation
and clear/sound-upload timings and the measured phase total.
The dashboard refreshes an interactive terminal; redirected output contains
plain snapshots without terminal escape sequences. ETA is an indicative
average, not a promise. Elapsed time covers processed jobs, excluding preflight
and the confirmation delay.

Binary generation is shared instead of duplicated in shell-embedded Python.
The existing CLI arguments and destructive confirmation remain unchanged;
the individual wrapper still has its legacy upload device handling.

`dt-build-banks` replaces inherited tags according to the selected source
folder, not the bank or generated sound name. Closed and open hats both use
`HI-HAT`. The generic `10 Percussion` folder uses `PERCUSSION`, even though
the existing bank E selection filters cowbell filenames. Unknown categories
are rejected; no other bank selection or sample mapping is changed.

The individual generator now requires an explicit tag:

```sh
./dt-make-sound SAMPLE_PATH B 1 01_SNARE SNARE
```

Quote tags containing spaces. Add `--upload` only after checking the generated
file, device, destination slot and backup. Without it, generation does not
upload the sound; sample metadata retrieval still opens a MIDI connection.
The existing individual wrapper's hard-coded device handling is unchanged.

The four-byte big-endian tag field is at payload offset 8 (file offset 39).
It is replaced before recalculating the CRC. Template tags are not retained.
The built-in model is uncompressed; there is no new LZ4 dependency.

Run offline regression tests with:

```sh
python3 -m unittest discover -s test -p test_digitakt_generator_tags.py
```

The tests also run through `make check` when Python 3 is available.

## Source selection and destination slots

### Explicit folder-to-bank mappings

Use repeatable `--map "FOLDER":BANK` groups to choose each destination:

```sh
./dt-build-banks ROOT \
  --map "03 Claps":A --range 1:10 --from-slot 10 \
  --map "02 Snares":D --range 1:10 --from-slot 20 \
  --dry-run
```

This places claps in A010–A019 and snares in D020–D029. Every `--map`
starts a new group. Following `--range`, `--limit` and `--from-slot`
options belong to that group until the next `--map`. `--dry-run` is global.
The default range is the whole folder and the default destination start is 1.
A group's limit applies after its inclusive source range.

Paths are relative to ROOT or absolute. The directory basename must be a
supported category (for example `03 Claps`); arbitrary names are rejected
rather than assigned guessed tags. The source category controls the tag,
not the destination bank. Existing +Drive directory mappings and category
filters are unchanged.

Groups must not overlap destination slots, repeat source files, or collide
on remote sample names. Capacity is checked for every group before MIDI.
Options duplicated within a group or placed before its `--map` are rejected;
a legacy global `--limit` cannot be combined with mappings.

Do not mix `--map` with legacy `--folder`, `--bank` or `--start-slot`.
The legacy syntax below remains supported for compatibility.

**Remove `--dry-run` only when ready to clear and replace the displayed slots
after answering `YES`. There is no automatic backup.** The configured MIDI
device index still needs to match the Digitakt pair.

### Compact preview

The default preview is a table of bank, destination slots, count, actual tag
and source directory name, followed by the total and exact destination ranges.
The confirmation summarizes occupied and target slots without listing every
slot. Non-contiguous ranges remain separate; no gaps are implied to be cleared.
Add the global `--verbose` flag to display full source paths, source ranks,
sound names and remote sample paths. This changes display only, not selection
or MIDI operations. `--dry-run` remains necessary to avoid execution.

### MIDI device selection

Run `./src/elektroid-cli ld` and identify the exact
`Elektron Digitakt :: Elektron Digitakt` pair. Pass its current index using
the global `--device` option; indices may change between connections:

```sh
./dt-build-banks ROOT --device 13 \
  --map "03 Claps":D --range 1:2 --from-slot 1 --dry-run
```

The index must be a non-negative integer. It is used for all batch CLI
operations and sessions and checked against device enumeration before any
write. Dry-run displays the index but does not connect to MIDI. If omitted,
the historical default is 1; do not assume it identifies the Digitakt.
This option does not change the separate individual wrapper's device handling.

### Legacy selection syntax

`ROOT` contains the category directories. No external sound model is needed.
Preview the first ten snares without opening MIDI:

```sh
./dt-build-banks ROOT --folder '02 Snares' --limit 10 --dry-run
```

Select source ranks 21–40 and place them in D100–D119:

```sh
./dt-build-banks ROOT --folder '02 Snares:21:40' \
  --bank D --start-slot 100 --dry-run
```

Ranks start at 1 after existing category filters and natural sorting of
relative paths. A range is inclusive and must exist in full. `--limit`
applies after the range, per selection. Source ranks may exceed 256 if an
explicit destination start makes the selected sounds fit in one bank.

`--folder` may be repeated, but explicit `--bank` or `--start-slot` requires
exactly one selection. Without placement options, source ranks keep their
historical slots and category bank. Tags still follow the source folder.

There is no bank rollover or automatic truncation. Thirty sounds from slot
250 are rejected before MIDI: only seven slots remain. Select at most seven
sounds, or choose a start no greater than 227.

The preview lists source paths/ranks, sound names, tags, slots and remote
sample paths. **Only `--dry-run` guarantees no MIDI connection or hardware
write. Without it, execution is the default.** The script checks that the
configured MIDI index is the Digitakt pair, inventories target slots and
requires the exact interactive answer `YES` before any write (`OUI` is also
accepted for compatibility). Refusal or EOF
cancels. Occupied slots are listed and will be replaced after confirmation.

There is no automatic backup. Each sound is generated before clearing only
its target slot, then uploaded. **There is no automatic download after upload.**
Success means that sample metadata and clear/upload MIDI responses succeeded,
not that tags, audio or all parameters were read back. Inspect tags and load
representative sounds on tracks for a separate hardware check. On a transfer
error, processing stops and reports completed,
failed and pending slots; the failed slot may be empty or partially modified.

`--execute`, `--clear-sounds` and `--clear-target-slots` are not accepted.
No bank-wide clearing is performed. The individual `dt-make-sound` wrapper
retains its separate `--upload` interface.

## MIDI connection lifecycle

The clean integration uses the public `get_sample_metadata` filesystem
operation for `META`, with the generator's existing `SAMPLE_INFO` response
format. `dt-sample-info` wraps `elektron:sample:sample-info`, converting its
decimal sample ID to the legacy hexadecimal wrapper format. Sample existence
checks have no metadata-printing side effect. Normal download compression is
unchanged. The session supports only SAMPLE_UL, META, DATA_CL, DATA_UL and
QUIT; there is no session-wide CLEAR_SOUNDS command.

After preflight and confirmation, the batch keeps one MIDI session for sample
uploads, metadata, targeted sound clears and sound uploads. `DATA_CL` accepts
only `/soundbanks/A/1` through `/soundbanks/H/256`, never directories or
metadata paths, and reuses the existing data filesystem delete operation.
No separate clear/download CLI connection is opened during this session.
This avoids both per-sound reconnect delays and the competing connection
sequence problem observed previously.

On the first error, the batch stops and closes the session. Existing offline
tests cover clear/upload ordering, failures, multiple sounds without CLI
connections and strict slot path validation. Rebuild `src/elektroid-cli` before
using this script version: it needs the experimental session `DATA_CL` command.
Hardware throughput still needs measurement; no fixed runtime is guaranteed.

Run all offline generator tests with:

```sh
python3 -m unittest discover -s test -p 'test_digitakt*.py'
```
