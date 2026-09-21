"""Managed external solver runtime. No bpy imports; safe for background workers."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import zipfile

UV_VERSION = '0.12.17'
REQUIREMENTS = ('numpy>=1.26,<3', 'scipy>=1.11,<2', 'osqp>=1.0,<2')
PROBE = '''import json, sys, numpy as np, scipy, scipy.sparse as sp, osqp
def version(v): return tuple(int(x) for x in v.split('.')[:2])
assert (1,26)<=version(np.__version__)<(3,0)
assert (1,11)<=version(scipy.__version__)<(2,0)
assert (1,0)<=version(osqp.__version__)<(2,0)
s=osqp.OSQP()
s.setup(P=sp.csc_matrix([[2.]]),q=np.array([-2.]),A=sp.eye(1,format='csc'),l=np.array([0.]),u=np.array([2.]),verbose=False)
r=s.solve()
assert r.info.status_val==1 and abs(r.x[0]-1)<.01
print(json.dumps(dict(python=sys.executable,numpy=np.__version__,scipy=scipy.__version__,osqp=osqp.__version__)))
'''


def runtime_root():
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    return base / 'KKModderBatchTool' / 'solver'


def clean_env():
    env = os.environ.copy()
    for name in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
        env.pop(name, None)
    env['PYTHONNOUSERSITE'] = '1'
    return env


def interpreter(directory):
    return Path(directory) / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def managed_python(root=None):
    root = Path(root or runtime_root()).resolve()
    try:
        value = json.loads((root / 'active.json').read_text(encoding='utf-8'))
        path = Path(value['python'])
        # Venv bin/python is a symlink on Unix; validate its parent, not the link target.
        if not path.parent.resolve().is_relative_to(root) or not path.is_file():
            return None
        return str(path)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def probe(executable, env=None):
    run = subprocess.run([str(executable), '-c', PROBE], env=env or clean_env(),
                         capture_output=True, text=True, timeout=30,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if run.returncode:
        raise ValueError((run.stderr or run.stdout)[-1000:].strip())
    return json.loads(run.stdout.strip().splitlines()[-1])


def candidates(configured='python', root=None):
    values = [managed_python(root)]
    if configured:
        values.append(shutil.which(configured) or (configured if Path(configured).is_file() else None))
    values += [shutil.which(name) for name in ('python3', 'python', 'python3.12', 'python3.11')]
    if os.name == 'nt' and shutil.which('py'):
        try:
            r = subprocess.run(['py', '-3', '-c', 'import sys; print(sys.executable)'], capture_output=True,
                               text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            if r.returncode == 0: values.append(r.stdout.strip())
        except (OSError, subprocess.TimeoutExpired): pass
    # Avoid Windows Store launch aliases, which may open interactive installers.
    return list(dict.fromkeys(str(v) for v in values if v and 'windowsapps' not in str(v).lower()))


def detect(configured='python', dependencies='', root=None):
    errors = []
    managed = managed_python(root)
    for path in candidates(configured, root):
        env = clean_env()
        if dependencies and path != managed:
            env['PYTHONPATH'] = dependencies
        try:
            info = probe(path, env)
            return path, env, info
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            errors.append(str(exc))
    raise ValueError('No working solver environment found. Click Install solver environment, or configure Python manually.')


@contextlib.contextmanager
def install_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'install.lock').open('a+b') as file:
        file.seek(0); file.write(b'0'); file.flush(); file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError('Another Blender instance is installing the solver environment.')
        try: yield
        finally:
            file.seek(0)
            if os.name == 'nt': msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def wheel_tag():
    machine = platform.machine().lower()
    arm = machine in ('arm64', 'aarch64')
    if sys.platform == 'win32': return 'win_arm64.whl' if arm else 'win_amd64.whl'
    if sys.platform == 'darwin': return 'macosx_11_0_arm64.whl' if arm else 'macosx_10_12_x86_64.whl'
    if sys.platform.startswith('linux') and machine in ('x86_64', 'aarch64'):
        return 'manylinux2014_aarch64.musllinux_1_1_aarch64.whl' if arm else 'manylinux2014_x86_64.whl'
    raise ValueError('Automatic installation is unavailable on this platform; configure an external Python manually.')


class Installer:
    def __init__(self, root=None, notify=lambda message: None):
        self.root = Path(root or runtime_root()).resolve()
        self.notify = notify
        self.cancelled = threading.Event()
        self.process = None

    def check_cancel(self):
        if self.cancelled.is_set(): raise ValueError('Solver environment installation canceled.')

    def cancel(self):
        self.cancelled.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def download(self, url):
        self.check_cancel()
        with urllib.request.urlopen(url, timeout=30) as response:
            chunks = []
            while True:
                self.check_cancel()
                block = response.read(1024 * 256)
                if not block: break
                chunks.append(block)
                if sum(map(len, chunks)) > 100 * 1024 * 1024:
                    raise ValueError('Installer download exceeded its size limit.')
            return b''.join(chunks)

    def bootstrap(self):
        self.notify('Downloading the environment installer...')
        meta = json.loads(self.download(f'https://pypi.org/pypi/uv/{UV_VERSION}/json'))
        entry = next((e for e in meta['urls'] if e['filename'].endswith(wheel_tag())), None)
        if not entry: raise ValueError('No compatible environment installer is available.')
        if not entry['url'].startswith('https://files.pythonhosted.org/'):
            raise ValueError('Unexpected installer download host.')
        content = self.download(entry['url'])
        if hashlib.sha256(content).hexdigest() != entry['digests']['sha256']:
            raise ValueError('Environment installer checksum mismatch.')
        name = 'uv.exe' if os.name == 'nt' else 'uv'
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            matches = [n for n in archive.namelist() if n.endswith('/scripts/' + name)]
            if len(matches) != 1: raise ValueError('Unexpected installer archive layout.')
            path = self.root / ('uv-' + UV_VERSION + ('.exe' if os.name == 'nt' else ''))
            path.write_bytes(archive.read(matches[0]))
            path.chmod(0o755)
            return str(path)

    def run_command(self, command, env, log):
        self.check_cancel()
        self.process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        started = time.monotonic()
        try:
            while self.process.poll() is None:
                if time.monotonic() - started > 1200:
                    self.process.terminate(); raise ValueError('Environment setup timed out; see the installation log.')
                if self.cancelled.wait(.2):
                    self.process.terminate(); self.check_cancel()
            if self.process.returncode:
                raise ValueError('Environment setup failed. Open the installation log for details.')
        finally:
            if self.process.poll() is None:
                try: self.process.wait(timeout=5)
                except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
            self.process = None

    def install(self):
        with install_lock(self.root):
            with (self.root / 'install.log').open('w', encoding='utf-8') as log:
                try:
                    uv = self.bootstrap()
                    directory = self.root / ('env-' + uuid.uuid4().hex)
                    env = clean_env()
                    env.update(UV_CACHE_DIR=str(self.root / 'cache'), UV_PYTHON_INSTALL_DIR=str(self.root / 'python'),
                               UV_NO_CONFIG='1', UV_NO_PROGRESS='1')
                    self.notify('Creating an isolated Python environment...')
                    self.run_command([uv, 'venv', '--python', '3.12', str(directory)], env, log)
                    self.notify('Installing NumPy, SciPy, and OSQP...')
                    exe = str(interpreter(directory))
                    self.run_command([uv, 'pip', 'install', '--python', exe, '--only-binary', ':all:',
                                      '--index-url', 'https://pypi.org/simple', *REQUIREMENTS], env, log)
                    self.notify('Validating the solver with a numerical smoke test...')
                    info = probe(exe)
                    self.check_cancel()
                    marker = self.root / 'active.tmp'
                    marker.write_text(json.dumps({'python': exe, 'versions': info}, indent=2), encoding='utf-8')
                    marker.replace(self.root / 'active.json')
                    return exe, clean_env(), info
                except Exception as exc:
                    log.write('\n' + str(exc) + '\n'); log.flush()
                    raise
