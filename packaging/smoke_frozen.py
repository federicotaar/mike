"""Verify the packaged executable really starts, not just that it links."""
from pathlib import Path
import os
import platform
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
if platform.system() == 'Windows': binary = root / 'dist/Mike/Mike.exe'
elif platform.system() == 'Darwin': binary = root / 'dist/Mike.app/Contents/MacOS/Mike'
else: binary = root / 'dist/Mike/Mike'
with tempfile.TemporaryDirectory() as directory:
    marker = Path(directory) / 'smoke.txt'
    env = dict(os.environ, MIKE_SMOKE_MARKER=str(marker))
    subprocess.run([str(binary), '--smoke-test'], env=env, check=True, timeout=30)
    assert marker.read_text() == 'PASS', 'packaged GUI did not confirm its smoke test'
print('FROZEN GUI SMOKE PASS')
