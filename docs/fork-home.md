---
layout: page
title: Digitakt I Sound Bank Generator
description: Turn WAV samples into tagged Digitakt I sounds and upload them directly to +Drive sound banks with ginizi's Elektroid fork.
permalink: /
---

Generate tagged **Digitakt I sounds from WAV samples** and send them directly to the device's +Drive sound banks. This experimental [Elektroid fork by ginizi](https://github.com/ginizi/elektroid) adds sound generation and bank workflows to the existing sample and MIDI device manager.
The generator targets **Digitakt I**, not Digitakt II, and does not require an external sound template.

## From WAV libraries to sound banks

- Generate one sound or prepare selections for several banks.
- Choose from 32 Digitakt I tags, independently of folder names and destination banks.
- Target banks A–H, with up to 256 sounds per bank.
- Preview source files and destination slots before connecting to MIDI.
- Keep a CSV report linking each sample to its generated sound and transfer outcome.
- Retry failed transfers once, with a stop after ten consecutive transfer failures.

Samples are uploaded to +Drive and generated sounds reference those samples. Uploading a sound does not load it onto a project's tracks.
There is no automatic repetition or rollover into another bank; filling all eight banks requires enough eligible samples in each selection.

## Get started safely

Clone [the fork](https://github.com/ginizi/elektroid) and follow the [build instructions](https://github.com/ginizi/elektroid#build-and-requirements). Python 3 and the locally built Elektroid CLI are required; installing upstream Elektroid alone does not install these scripts.
Run these commands from the repository root:

```sh
./scripts/dt-build-banks --help
./scripts/dt-build-banks --list-tags
./scripts/dt-build-banks --list-banks
```

Preview ten claps destined for bank D:

```sh
./scripts/dt-build-banks "/path/to/sample-library" --device INDEX \
  --map "Claps folder":D --tag CLAP --limit 10 --from-slot 1 --dry-run
```

Replace the library path and `Claps folder` with your actual sample directory names. Replace `INDEX` with the current Digitakt MIDI index reported by `./src/elektroid-cli ld`; that discovery command accesses MIDI.
**`--dry-run` does not connect to MIDI or write to the device**, but creates a local CSV report. Without it, execution asks for confirmation and then clears and overwrites the selected sound slots.

**Back up your device first: there is no automatic backup or rollback.** Start with one sound in B001, verify its tags and audio on a track, then increase the selection.

## Guides and source code

- [Complete generator guide](https://github.com/ginizi/elektroid/blob/master/docs/digitakt-generator-tags.md)
- [Single and batch sample metadata commands](https://github.com/ginizi/elektroid/blob/master/docs/elektron-sample-metadata.md)
- [Source code and installation](https://github.com/ginizi/elektroid)
- [Report a fork-specific issue](https://github.com/ginizi/elektroid/issues)

## Built on Elektroid

[Elektroid](https://github.com/dagargo/elektroid) is the upstream sample and MIDI device manager created by David García Goñi and its contributors. This fork is maintained by ginizi; its generator is not an official upstream release.
The upstream application supports many devices, but that does not imply generator support for those devices. The project retains the [GPLv3 license]({{ '/license.html' | relative_url }}).
