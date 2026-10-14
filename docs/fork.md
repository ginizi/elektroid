
## About this fork

This fork of [Elektroid](https://github.com/dagargo/elektroid) adds a
**Digitakt I sound-bank generator** and Elektron sample-metadata CLI support.
The upstream application's features, installation instructions and license
are preserved below. These additions are not an official upstream release;
the generator is intended to remain a fork-specific workflow.

### Generate and send sounds directly to Digitakt I

You can turn local WAV samples into tagged Digitakt I sounds and **send them
directly to the device's +Drive sound banks**, without manually importing each
sound. The workflow uploads the samples to +Drive, generates sounds referencing
those samples, and writes the sounds to the bank slots you select.

- Send a single sound to a chosen slot, or a selection of sounds.
- Fill one or several banks **A–H**, with up to **256 sounds per bank**.
- Populate all eight banks (**2,048 sounds**) using the historical category
  mapping, provided each category has 256 eligible WAVs after filtering.
- Combine freely named sample folders, explicit tags and destination banks
  in one command; preview the complete plan before sending anything.

There is no automatic repetition or overflow into other banks. Uploading
sounds does not load them into a project's tracks. Destination sound slots
are overwritten: see the safety instructions below before any transfer.

### Build and requirements

Install the dependencies in the [installation section](#dependencies) below,
then build the local CLI from the repository root:

```sh
autoreconf --install
./configure BUILD_GUI=no
make
```

The generator also requires Python 3 and runs from this checkout, using
`src/elektroid-cli`. Installing upstream Elektroid or its Flatpak alone does
not install these fork scripts. The generator targets **Digitakt I**, not II.

### Quick start: preview first

Discover the current MIDI device index (this command accesses MIDI):

```sh
./src/elektroid-cli ld
```

Inspect the available banks and tags without connecting to MIDI:

```sh
./dt-build-banks --help
./dt-build-banks --list-banks
./dt-build-banks --list-tags
```

Preview a plan, replacing `INDEX` with your device index:

```sh
./dt-build-banks "/path/to/sample-library" --device INDEX \
  -m "Claps folder":D --tag CLAP -r 1:10 -f 1 \
  -m "Snares folder":B --tag SNARE -l 10 -f 20 -n
```

Replace the quoted folder names with actual folders containing WAV files
under ROOT (`/path/to/sample-library`); absolute folder paths also work.
The letters outside the quotes are destination banks. Each `--map` requires
one explicit tag; quote tags containing spaces, such as `"SOUND FX"`.
Following `--tag`, `--range`, `--limit` and `--from-slot` belong to that mapping
until the next `--map`. Banks A–H each have 256 slots; tags do not depend on banks.

**`-n` / `--dry-run` does not connect to MIDI or write to the device**, but
does write a local CSV report. Review source paths, tags and destination slots
in the preview and report before considering an upload.

### Transfer safety and reports

**Execution clears and overwrites destination sound slots. There is no
automatic backup or rollback; a failed upload can leave a slot empty.**
Back up your device first. Only remove `-n` after reviewing the plan; execution
also asks for confirmation. Start with one sound in **B001** and verify it on
the device before increasing the selection.

The CSV records source files, tags, destination slots, exact generated names,
and transfer outcomes. `--report PATH` selects a report path; existing reports
are not overwritten. Failed transfers are queued for one final retry pass;
execution stops after ten consecutive transfer failures. A dead MIDI session
is not automatically reconnected. Offline tests do not replace hardware checks.

Without `--map`, historical category folders and bank assignments apply,
including the cowbell filter. Filling all A–H banks requires 256 eligible WAVs
per category; samples are not repeated and do not overflow into another bank.

See the [Digitakt generator guide](docs/digitakt-generator-tags.md) for full
bank usage, selection rules, sample destinations, CSV fields and retries, and
the [untagged sound-export note](docs/elektron-sound-export.md) for the export fix.

## Upstream Elektroid
