# Digitakt I generator tags

The experimental generators use built-in Digitakt I sound parameters and require no template file or template argument. Tag values were verified on firmware 1.53.
The shared `dt_sound_defaults.py` module contains the hardware-validated A007 model as immutable bytes and returns an independent validated copy. This is an internal model, not a complete decoded specification or a claim to match factory INIT settings.
The generators replace its name, tags, file index and sample references and recalculate the CRC. Keep `dt_sound_defaults.py` at the repository root.

## Python organization

The commands in `scripts/` are thin entry points. Keep the `digitakt/` package at the repository root; no installation framework or new Python dependency is required.

| Module | Responsibility |
| --- | --- |
| `cli` | Parse options, create immutable configuration, orchestrate preflight |
| `planning` | Inventory, ranges, destinations, capacity and collisions; no MIDI |
| `sound` | Shared pure binary generation, tags and CRC |
| `transport` | Process boundary and MIDI session lifecycle |
| `execution` | Convert sample, retrieve metadata, generate, clear and upload |
| `presentation` | Compact preview, confirmation and progress |
| `single` | Individual generator CLI using the shared sound implementation |

The configuration is passed explicitly:

- Parsing `--device` does not mutate a global device value.
- Execution accepts a command runner and session factory for offline tests.
- The session is a context manager and closes on success, failure or interruption.
- The batch collects failed transfers and retries them once at the end,
  without automatic download.

Progress shows elapsed/remaining time and estimated finish. With `--verbose`, it also shows conversion, WAV upload, metadata, generation and clear/sound-upload timings and the measured phase total.
The dashboard refreshes an interactive terminal; redirected output contains plain snapshots without terminal escape sequences. ETA is an indicative average, not a promise.
Elapsed time covers processed jobs, excluding preflight and the confirmation delay. Binary generation is shared instead of duplicated in shell-embedded Python.
The destructive confirmation remains unchanged; the individual wrapper still has its legacy upload device handling. `dt-build-banks` replaces inherited tags with the explicit `--tag` of each `--map` group, independently of folder name and destination bank.
Without `--map`, tags retain their historical source-category mapping: closed and open hats use `HI-HAT`, and `10 Percussion` uses `PERCUSSION` with a cowbell filename filter. Legacy categories remain restricted; mapping folder names are free.
The individual generator now requires an explicit tag:

```sh
./scripts/dt-make-sound SAMPLE_PATH B 1 01_SNARE SNARE
```

Quote tags containing spaces. Add `--upload` only after checking the generated file, device, destination slot and backup.
Without it, generation does not upload the sound; sample metadata retrieval still opens a MIDI connection. The existing individual wrapper's hard-coded device handling is unchanged.
The four-byte big-endian tag field is at payload offset 8 (file offset 39). It is replaced before recalculating the CRC.
Template tags are not retained. The built-in model is uncompressed; there is no new LZ4 dependency.
Run offline regression tests with:

```sh
python3 -m unittest discover -s test -p test_digitakt_generator_tags.py
```

The tests also run through `make check` when Python 3 is available.

## Source selection and destination slots

### Explicit folder-to-bank mappings

Short and long options may be mixed without changing selection groups:

| Short | Long |
| --- | --- |
| `-m` | `--map` |
| `-r` | `--range` |
| `-f` | `--from-slot` |
| `-l` | `--limit` |
| `-d` | `--device` |
| `-n` | `--dry-run` |
| `-v` | `--verbose` |
| `-b` | `--bank` (legacy) |
| `-s` | `--start-slot` (legacy) |
| `-h` | `--help` |

`-n` / `--dry-run` previews planned transfers without a MIDI connection or device writes. **Without this option, transfers execute after confirmation.**
This distinction is also explained in `--help`.
`--help` includes a complete example with a placeholder library path:

```sh
./scripts/dt-build-banks "/path/to/sample-library" \
  -m "Claps folder":D --tag CLAP -r 1:10 -f 1 -n
```

Replace `/path/to/sample-library` with your ROOT directory, containing the `Claps folder` directory in this example. Replace this name with your actual folder name; the bank letter stays outside the quotes.
`-m` / `--map` can be repeated to combine several selections in one command; `--help` also includes this example:

```sh
./scripts/dt-build-banks "/path/to/sample-library" \
  -m "Claps folder":D --tag CLAP -r 1:10 -f 1 \
  -m "Snares folder":B --tag SNARE -l 10 -f 20 -n
```

Selection options `--tag`, `-r`, `-l` and `-f` apply to the preceding mapping until the next `-m` / `--map`, so each group can have its own range, limit and start slot.

### Populate default banks A–H

To populate banks A-H using the default category mappings, first find the current Digitakt MIDI index with `./src/elektroid-cli ld`. Replace `INDEX` in the commands below.
Without `--map` or `--folder`, category assignment is fixed:

| Bank | Category |
| --- | --- |
| A | Kicks |
| B | Snares |
| C | Toms |
| D | Claps |
| E | Cowbells |
| F | Closed hats |
| G | Open hats |
| H | Cymbals |

Missing category folders are skipped. This is not an even distribution of all WAVs across banks: a category never overflows into the next bank.
The CLI explains this mapping before building the default plan and also lists it with `--list-banks`. If a selection exceeds capacity, the diagnostic names the source folder, eligible WAV count, selected count, destination bank and available slot range.
The entire command is cancelled before any transfer, including to other banks. Use `--limit 256` to select up to 256 WAVs per default bank, or use explicit mappings and smaller ranges.
A later starting slot requires a smaller limit. In default mode, a capacity error includes a copyable preview command using the actual resolved ROOT path and selected MIDI device index.
Shell quoting preserves spaces and apostrophes. Explicit `--map`/`--folder` selections do not receive a default-bank command that would change their destinations.
Paths in the static `--help` examples remain placeholders.

```sh
# Preview all selected slots first.
./scripts/dt-build-banks "/path/to/sample-library" --limit 256 --device INDEX -n
# Write only after reviewing the preview; confirmation is required.
./scripts/dt-build-banks "/path/to/sample-library" --limit 256 --device INDEX
```

Filling all 2,048 slots requires 256 eligible WAVs per category after filters (including the historical cowbell filter for `10 Percussion`). Samples are not repeated: categories with fewer files leave the remaining slots unchanged.
Target slots are cleared and overwritten, with no automatic backup. A complete A-H hardware fill has not been validated.

### Transfer report

Every invocation with a non-empty plan creates a new CSV report in `generated_sounds/` and prints its path. Use `--report PATH` to choose a file.
An existing file is never overwritten when starting a run. For each bank/slot, the report records:

- Exact generated sound name.
- Absolute WAV source path.
- Sample path on the +Drive.
- Verified tag and generated `.data` path.
- Status, attempt count, phase and last failure message.

The name is the generated name, not a readback of the previously occupied slot.

- With `-n`, rows are `planned`; no MIDI connection is opened.
- During execution, rows start as `not_executed`.
- After each attempt, they become `successful`, `failed` or `recovered`.
- Ctrl-C during a transfer records `interrupted` when possible.

Successful retries retain the previous error for diagnosis. Updates replace the report atomically.
A report write failure stops execution to avoid losing the audit trail; this does not undo device writes already made. Forced process termination can leave the latest device operation absent from the report.

```sh
./scripts/dt-build-banks ROOT -m "03 Claps":D --tag CLAP -n --report ./claps-plan.csv
```

### Mapping rules and examples

`--folder` has no short alias. For example, preview without MIDI:

```sh
./scripts/dt-build-banks ROOT -d 13 \
  -m "03 Claps":D --tag CLAP -r 1:10 -f 1 \
  -m "02 Snares":B --tag SNARE -l 10 -f 20 -n -v
```

Use repeatable `--map "FOLDER":BANK` groups to choose each destination:

```sh
./scripts/dt-build-banks ROOT \
  --map "03 Claps":A --tag CLAP --range 1:10 --from-slot 10 \
  --map "02 Snares":D --tag SNARE --range 1:10 --from-slot 20 \
  --dry-run
```

This places claps in A010–A019 and snares in D020–D029.

- Every `--map` starts a new group.
- Following `--tag`, `--range`, `--limit` and `--from-slot` options belong
  to that group until the next `--map`.
- `--dry-run` is global.

The default range is the whole folder and the default destination start is 1. A group's limit applies after its inclusive source range.
Paths are relative to ROOT or absolute, with unrestricted directory names. Each mapping requires one explicit `--tag`.

- Missing, invalid or duplicate tags are rejected before MIDI.
- Tag input is case-insensitive.
- Quote tags with spaces.

`--tag` is not accepted without `--map`. All WAVs in a mapped folder are eligible: there is no implicit cowbell filter, even for a folder named `10 Percussion`.

```sh
./scripts/dt-build-banks "/path/to/sample-library" \
  -m "My textures":H --tag TEXTURE \
  -m "Vintage effects":A --tag "SOUND FX" -n
```

`--help` provides a compact option reference and two mapping examples. This document covers the full workflow, default banks and transfer safety.
In help examples, `"Claps folder":D` and `"Snares folder":B` refer to directories: replace the quoted names with your actual folder names under ROOT, or absolute folder paths. Bank letters remain outside the quotes.

### List banks and tags

List banks A-H (256 slots each) and historical default mappings without ROOT, MIDI access or file writes:

```sh
./scripts/dt-build-banks --list-banks
```

Default assignments apply only without explicit mappings. With `--map`, any bank can receive any tag.
List all tags without a sample root, MIDI connection or file writes:

```sh
./scripts/dt-build-banks --list-tags
```

All 32 validated Digitakt I tags are supported (listed by `--list-tags`):

| Tag | Tag | Tag | Tag |
| --- | --- | --- | --- |
| `KICK` | `SNARE` | `RIMSHOT` | `CLAP` |
| `TOM` | `PERCUSSION` | `HI-HAT` | `CYMBAL` |
| `COWBELL` | `SYNTH` | `BASS` | `LEAD` |
| `PAD` | `TEXTURE` | `CHORD` | `SOUND FX` |
| `ELECTRONIC` | `METALLIC` | `ACOUSTIC` | `ATMOSPHERIC` |
| `NOISY` | `GLITCH` | `HARD` | `SOFT` |
| `DARK` | `BRIGHT` | `VINTAGE` | `EPIC` |
| `FAIL` | `LOOP` | `MINE` | `FAVOURITE` |

**Only one tag per group is supported**; combinations have not been hardware-validated.

### Sample destinations and collisions

Known category folders retain their historical +Drive directories. Free-name folders use `mapped_<sanitized-name>-<path-hash>` directories, separating folders with identical basenames.
Moving a folder changes its path hash and destination. Mapped sound names use the slot number and an ASCII tag label shortened to fit the 15-character sound-name limit.
The report records the exact name and paths. Groups must not overlap destination slots, repeat source files, or collide on remote sample names.
Capacity is checked for every group before MIDI. Options duplicated within a group or placed before its `--map` are rejected; a legacy global `--limit` cannot be combined with mappings.
Do not mix `--map` with legacy `--folder`, `--bank` or `--start-slot`. The legacy syntax below remains supported for compatibility.

### Before execution

**Remove `--dry-run` only when ready to clear and replace the displayed slots after answering `YES`. There is no automatic backup.**
The configured MIDI device index still needs to match the Digitakt pair.

### Compact preview

The preview starts with destination banks in mapping order. Each bank shows, including without `--verbose`:

- Exact destination slot ranges.
- Every source filename next to its destination slot and actual tag.

The total count and MIDI index follow the bank/file listing. The confirmation summarizes occupied and target slots without listing every slot.
Non-contiguous ranges remain separate; no gaps are implied to be cleared. Add the global `--verbose` flag to display:

- Full source paths and source ranks.
- Sound names and +Drive WAV destinations.

This changes display only, not selection or MIDI operations. **`--dry-run` remains necessary to avoid execution.**

### MIDI device selection

Run `./src/elektroid-cli ld` and identify the exact `Elektron Digitakt :: Elektron Digitakt` pair. Pass its current index using the global `--device` option; indices may change between connections:

```sh
./scripts/dt-build-banks ROOT --device 13 \
  --map "03 Claps":D --tag CLAP --range 1:2 --from-slot 1 --dry-run
```

- The index must be a non-negative integer.
- It is used for all batch CLI operations and sessions.
- It is checked against device enumeration before any write.
- Dry-run displays the index but does not connect to MIDI.

If omitted, the historical default is 1: **do not assume it identifies the Digitakt.** This option does not change the separate individual wrapper's device handling.

### Legacy selection syntax

`ROOT` contains the category directories. No external sound model is needed.
Preview the first ten snares without opening MIDI:

```sh
./scripts/dt-build-banks ROOT --folder '02 Snares' --limit 10 --dry-run
```

Select source ranks 21–40 and place them in D100–D119:

```sh
./scripts/dt-build-banks ROOT --folder '02 Snares:21:40' \
  --bank D --start-slot 100 --dry-run
```

Ranks start at 1 after existing category filters and natural sorting of relative paths. A range is inclusive and must exist in full.
`--limit` applies after the range, per selection. Source ranks may exceed 256 if an explicit destination start makes the selected sounds fit in one bank.
`--folder` may be repeated, but explicit `--bank` or `--start-slot` requires exactly one selection. Without placement options, source ranks keep their historical slots and category bank.
Tags still follow the source folder. There is no bank rollover or automatic truncation.
Thirty sounds from slot 250 are rejected before MIDI: only seven slots remain. Select at most seven sounds, or choose a start no greater than 227.
The preview lists source paths/ranks, sound names, tags, slots and remote sample paths. **Only `--dry-run` guarantees no MIDI connection or hardware write.
Without it, execution is the default.** Before any write, the script:

1. Checks that the configured MIDI index is the Digitakt pair.
2. Inventories target slots.
3. Requires the exact interactive answer `YES` (`OUI` is also accepted
   for compatibility).

Refusal or EOF cancels. Occupied slots are listed and will be replaced after confirmation.
There is no automatic backup. Each sound is generated before clearing only its target slot, then uploaded.
**There is no automatic download after upload.** Success means that sample metadata and clear/upload MIDI responses succeeded, not that tags, audio or all parameters were read back.
Inspect tags and load representative sounds on tracks for a separate hardware check. Transfer errors are recorded and queued for the final retry pass described below.
The failed slot may be empty or partially modified. `--execute`, `--clear-sounds` and `--clear-target-slots` are not accepted.
No bank-wide clearing is performed. The individual `dt-make-sound` wrapper retains its separate `--upload` interface.

## MIDI connection lifecycle

The clean integration uses the public `get_sample_metadata` filesystem operation for `META`, with the generator's existing `SAMPLE_INFO` response format. `dt-sample-info` wraps `elektron:sample:sample-info`, converting its decimal sample ID to the legacy hexadecimal wrapper format.
Sample existence checks have no metadata-printing side effect. Normal download compression is unchanged.
The session supports only SAMPLE_UL, META, DATA_CL, DATA_UL and QUIT; there is no session-wide CLEAR_SOUNDS command. After preflight and confirmation, the batch keeps one MIDI session for sample uploads, metadata, targeted sound clears and sound uploads.
`DATA_CL` accepts only `/soundbanks/A/1` through `/soundbanks/H/256`, never directories or metadata paths, and reuses the existing data filesystem delete operation. No separate clear/download CLI connection is opened during this session.
This avoids both per-sound reconnect delays and the competing connection sequence problem observed previously.

### Failures and final retry

After a transfer error, the batch records the slot, phase and error, then continues. A successful transfer resets the consecutive-failure counter.
Ten consecutive failures stop execution immediately, without starting or continuing the final retry pass. The counter carries over between passes.
Otherwise, each failed transfer gets one final attempt, starting at its failed phase. A confirmed clear is not repeated if the sound upload failed.
The final summary lists completed, recovered, failed and unexecuted slots. Unresolved failures or unexecuted slots produce a nonzero exit status.
There is no rollback: earlier writes remain, and a failed slot may be empty or partially modified. Initial connection and directory preparation remain blocking prerequisites.
Disconnected sessions are not automatically reopened.

### Offline validation

Existing offline tests cover retry limits, clear/upload ordering, failures, multiple sounds without CLI connections and strict slot path validation. Rebuild `src/elektroid-cli` before using this script version: it needs the experimental session `DATA_CL` command.
Hardware throughput still needs measurement; no fixed runtime is guaranteed. Run all offline generator tests with:

```sh
python3 -m unittest discover -s test -p 'test_digitakt*.py'
```
