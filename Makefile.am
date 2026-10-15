ACLOCAL_AMFLAGS = -I m4

SUBDIRS = src res test man

if ELEKTROID_BUILD_GUI
SUBDIRS += po
endif

format:
	indent src/*.[ch] src/connectors/*.[ch] src/mactions/*.[ch] test/*.[ch]

.PHONY: format
EXTRA_DIST = scripts/dt-build-banks scripts/dt-make-sound dt_sound_defaults.py \
	scripts/dt-sample-meta scripts/dt-sample-info
EXTRA_DIST += digitakt/__init__.py digitakt/cli.py digitakt/planning.py \
	digitakt/sound.py digitakt/transport.py digitakt/execution.py \
	digitakt/presentation.py digitakt/single.py digitakt/reporting.py
