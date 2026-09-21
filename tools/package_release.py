"""Create clean source and skill archives without local environments or user data."""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile


def archive(folder, target):
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(folder.parent).as_posix())
    with zipfile.ZipFile(target) as bundle:
        assert bundle.testzip() is None
        assert not any('/.venv/' in p or '/__pycache__/' in p for p in bundle.namelist())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, required=True, help='New directory outside the source tree.')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    dest = args.dest.resolve()
    if dest == source or source in dest.parents:
        parser.error('Destination must be outside source tree.')
    dest.mkdir(parents=True, exist_ok=False)
    clean = dest / 'mt-distillation'
    shutil.copytree(source, clean, ignore=shutil.ignore_patterns(
        '.venv', '.git', '__pycache__', '*.pyc', 'outputs', 'work', 'cache', 'logs', '*.log', '*.zip'))
    # Archive downloads do not honor .gitattributes, so normalize batch files here.
    for batch in clean.rglob('*.bat'):
        data = batch.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        batch.write_bytes(data)
    archives = [dest / 'mt-distillation-v1.0.0.zip', dest / 'mt-distillation-skill-v1.0.0.zip']
    archive(clean, archives[0])
    archive(clean / 'skills' / 'mt-distillation', archives[1])
    hashes = ''.join(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n' for path in archives)
    (dest / 'SHA256SUMS.txt').write_text(hashes, encoding='ascii')
    print(f'Release created: {dest}')
    for path in archives:
        print(f'{path.name}: {path.stat().st_size} bytes')


if __name__ == '__main__':
    main()
