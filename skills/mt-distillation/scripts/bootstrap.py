"""Create/check this skill's own environment; never bundle an existing venv."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv


def main():
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', action='store_true', help='Also install the optional Origin Python interface.')
    parser.add_argument('--check', action='store_true', help='Check existing environment without installing anything.')
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error('Python 3.10 or newer is required.')
    if args.origin and os.name != 'nt':
        parser.error('Origin integration requires Windows.')
    skill = Path(__file__).resolve().parent.parent
    envdir = skill / '.venv'
    runtime = envdir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not args.check:
        if not runtime.is_file():
            print(f'Creating environment: {envdir}', flush=True)
            venv.EnvBuilder(with_pip=True).create(envdir)
        requirements = skill / 'scripts' / ('requirements-origin.txt' if args.origin else 'requirements.txt')
        subprocess.run([str(runtime), '-m', 'pip', 'install', '--disable-pip-version-check',
                        '-r', str(requirements)], check=True)
    if not runtime.is_file():
        raise RuntimeError('Environment missing. Run setup.bat or bootstrap.py without --check.')
    # Importing originpro here may start Origin: check discovery only.
    probe = "import matplotlib, tkinter; from importlib.util import find_spec; "
    if args.origin:
        probe += "assert find_spec('originpro') is not None, 'originpro is missing'; "
    probe += "print('Environment ready. Origin application/license is checked only on export.')"
    subprocess.run([str(runtime), '-c', probe], check=True)
    print(f'Python: {runtime}', flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'Setup failed: {exc}', file=sys.stderr)
        sys.exit(1)
