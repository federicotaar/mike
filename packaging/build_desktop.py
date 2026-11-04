"""Build unsigned desktop previews; publication is a separate reviewed step."""
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'dist'


def main():
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
                    '--name', 'Mike', '--paths', str(ROOT), str(ROOT / 'desktop/launcher.py')], cwd=ROOT, check=True)
    system = platform.system()
    if system == 'Linux':
        arch = subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip()
        package = OUT / 'deb-root'
        shutil.rmtree(package, ignore_errors=True)
        (package / 'DEBIAN').mkdir(parents=True)
        (package / 'opt').mkdir()
        shutil.copytree(OUT / 'Mike', package / 'opt/mike')
        launch = package / 'usr/bin/mike'
        launch.parent.mkdir(parents=True)
        launch.write_text('#!/bin/sh\nexec /opt/mike/Mike "$@"\n')
        launch.chmod(0o755)
        app = package / 'usr/share/applications/mike.desktop'
        app.parent.mkdir(parents=True)
        app.write_text('[Desktop Entry]\nType=Application\nName=Mike\nExec=mike\nTerminal=false\nCategories=Utility;\n')
        (package / 'DEBIAN/control').write_text(f'Package: mike-desktop\nVersion: 0.1.0\nArchitecture: {arch}\nMaintainer: Mike contributors\nDepends: libc6, libx11-6, libxext6, libxrender1, libfontconfig1\nDescription: Mike desktop chat preview\n')
        subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(package), str(OUT / f'Mike-Ubuntu-{arch}.deb')], check=True)
    elif system == 'Windows':
        shutil.make_archive(str(OUT / 'Mike-Windows'), 'zip', OUT, 'Mike')
    elif system == 'Darwin':
        shutil.make_archive(str(OUT / 'Mike-macOS'), 'zip', OUT, 'Mike.app')
    else:
        raise SystemExit('Unsupported build platform')


if __name__ == '__main__': main()
