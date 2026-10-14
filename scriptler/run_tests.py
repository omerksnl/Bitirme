"""Run repository tests using writable local scratch space; no paid API calls."""
import argparse
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pattern', default='test_*.py')
    args = parser.parse_args()
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    tempfile.tempdir = str(work)
    os.environ.setdefault('TIKTOKEN_CACHE_DIR', str(work / 'tiktoken_cache'))
    sys.path.insert(0, str(ROOT / 'scriptler'))
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'scriptler/tests'), pattern=args.pattern)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
