"""Run all local regressions without recording video or sending real messages."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    node = shutil.which('node')
    if not node:
        print('Node.js 22+ is needed for browser regression tests; the app itself only needs Python 3.9+.', file=sys.stderr)
        return 1
    for path in sorted((ROOT / 'tests').iterdir()):
        if path.suffix in ('.cjs', '.mjs'):
            print(f'Running {path.name}', flush=True)
            subprocess.run([node, str(path)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'], cwd=ROOT, check=True)
    print('All local checks passed. Live camera, delivery, and second-device audio still require manual validation.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
