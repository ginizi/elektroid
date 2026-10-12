#!/bin/sh
# Smoke tests for Elektron sample metadata batch command.
# These tests do not require a MIDI device.
set -eu

CLI="${1:-${ELEKTROID_CLI:-./src/elektroid-cli}}"
COMMAND="elektron:sample:sample-info-batch"

if [ ! -x "$CLI" ]; then
    echo "Executable not found: $CLI" >&2
    exit 1
fi

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT HUP INT TERM

check_failure()
{
    expected="$1"
    shift

    if "$CLI" "$@" >"$tmpdir/stdout" 2>"$tmpdir/stderr"; then
        echo "FAIL: command unexpectedly succeeded: $*" >&2
        exit 1
    fi

    if ! grep -F "$expected" "$tmpdir/stderr" >/dev/null; then
        echo "FAIL: expected error: $expected" >&2
        echo "Actual stderr:" >&2
        cat "$tmpdir/stderr" >&2
        exit 1
    fi

    if [ -s "$tmpdir/stdout" ]; then
        echo "FAIL: unexpected stdout on validation error" >&2
        cat "$tmpdir/stdout" >&2
        exit 1
    fi
}

# No paths supplied.
check_failure "Missing sample paths" "$COMMAND"

# A device number without a sample path is invalid.
check_failure "Expected device_number:path_to_file" \
    "$COMMAND" '13'

# The sample path cannot be empty.
check_failure "Expected device_number:path_to_file" \
    "$COMMAND" '13:'

# The device number must be numeric.
check_failure "Expected device_number:path_to_file" \
    "$COMMAND" 'abc:/KICK'

# All samples must belong to the same device.
# This must fail before opening any MIDI connection.
check_failure "All sample paths must use the same device" \
    "$COMMAND" \
    '13:/KICK' \
    '14:/SNARE'

# Help must advertise the batch operation.
"$CLI" >"$tmpdir/help" 2>&1 || true

if ! grep -F "sample-info-batch" "$tmpdir/help" >/dev/null; then
    echo "FAIL: sample-info-batch missing from CLI help" >&2
    exit 1
fi

echo "PASS: sample metadata batch CLI smoke tests"
