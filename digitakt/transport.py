"""Process and MIDI boundaries, injectable for offline tests."""

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class Config:
    cli: Path
    device: str
    work: Path


def cmd(args, cwd=None):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(result.stdout.strip() or f'Command failed: {args}')
    return result.stdout


class DTSession:
    def __init__(self, cli, device):
        self.proc = subprocess.Popen([str(cli), 'dt-session', str(device)],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
        try:
            for line in self.proc.stdout:
                if line.strip() == 'DT_SESSION_READY':
                    return
            raise RuntimeError('dt-session exited while connecting')
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def command(self, *parts):
        if self.proc is None or self.proc.poll() is not None:
            raise RuntimeError('dt-session is no longer active')
        values = [str(part) for part in parts]
        if any(any(c in value for c in '\t\r\n') for value in values):
            raise RuntimeError('Invalid session command field')
        self.proc.stdin.write('\t'.join(values) + '\n')
        self.proc.stdin.flush()
        output = []
        for line in self.proc.stdout:
            line = line.rstrip('\n')
            output.append(line)
            if line.startswith('DT_ERROR\t'):
                raise RuntimeError('\n'.join(output))
            if line.startswith('DT_OK\t'):
                return '\n'.join(output)
        raise RuntimeError('dt-session interrupted')

    def close(self):
        if self.proc is None:
            return
        try:
            if self.proc.poll() is None:
                try:
                    self.proc.stdin.write('QUIT\n')
                    self.proc.stdin.flush()
                    self.proc.wait(timeout=3)
                except (OSError, subprocess.TimeoutExpired):
                    self.proc.terminate()
                    try:
                        self.proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                        self.proc.wait()
        finally:
            for stream in (self.proc.stdin, self.proc.stdout):
                stream.close()
            self.proc = None


def check_destinations(jobs, config, runner=cmd):
    occupied = []
    for bank in dict.fromkeys(job['bank'] for job in jobs):
        listing = runner([config.cli, 'elektron:data:ls',
                          f'{config.device}:/soundbanks/{bank}'])
        slots = set()
        for line in listing.splitlines():
            fields = line.split(maxsplit=6)
            if (len(fields) < 7 or fields[0] != 'F' or fields[2] not in ('0', '1')
                    or fields[3] not in ('0', '1') or not fields[5].isdigit()
                    or not 1 <= int(fields[5]) <= 256):
                raise SystemExit('Unrecognized slot listing; no writes allowed')
            slots.add(int(fields[5]))
        occupied.extend(f"{bank}{job['slot']:03d}" for job in jobs
                        if job['bank'] == bank and job['slot'] in slots)
    return occupied


def verify_device(config, runner=cmd):
    expected = (f'{config.device}: id: Elektron Digitakt :: Elektron Digitakt; '
                'name: Elektron Digitakt :: Elektron Digitakt')
    if expected not in runner([config.cli, 'ld']).splitlines():
        raise SystemExit('Configured MIDI index does not identify the Digitakt; no writes allowed')
