"""Regenerate SBCST figures/tables and compile the two-column LaTeX paper.

Example: python build_paper.py --build-dir /path/to/cache/sbcst
Requires Python + NumPy + Matplotlib and pdflatex on PATH.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def build(build_dir):
    build_dir = Path(build_dir).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / 'build_figures.py')], check=True)
    command = ['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
               f'-output-directory={build_dir}', 'sbcst.tex']
    for run in range(2):
        result = subprocess.run(command, cwd=ROOT, capture_output=True)
        log = build_dir / f'pdflatex-pass-{run + 1}.txt'
        log.write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'LaTeX failed. Read {log}')
    log = (build_dir / 'sbcst.log').read_text(errors='replace')
    if any(s in log for s in ('Overfull \\hbox', 'Overfull \\vbox',
                              'There were undefined references',
                              'Label(s) may have changed')):
        raise RuntimeError('Check unresolved references or layout overflow in sbcst.log')
    destination = ROOT / 'SBCST.pdf'
    shutil.copyfile(build_dir / 'sbcst.pdf', destination)
    print(destination)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', required=True,
                        help='Directory for disposable LaTeX build intermediates')
    build(parser.parse_args().build_dir)
