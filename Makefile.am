ACLOCAL_AMFLAGS = -I m4

SUBDIRS = src res test man

if ELEKTROID_BUILD_GUI
SUBDIRS += po
endif

format:
	indent src/*.[ch] src/connectors/*.[ch] src/mactions/*.[ch] test/*.[ch]

.PHONY: format
EXTRA_DIST = scripts/dt-build-banks scripts/dt-make-sound scripts/digitakt/defaults.py \
	scripts/dt-sample-meta scripts/dt-sample-info
EXTRA_DIST += scripts/digitakt/__init__.py scripts/digitakt/cli.py scripts/digitakt/planning.py \
	scripts/digitakt/sound.py scripts/digitakt/transport.py scripts/digitakt/execution.py \
	scripts/digitakt/presentation.py scripts/digitakt/single.py scripts/digitakt/reporting.py
