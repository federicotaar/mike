"""Stamp and verify final IPA provenance without changing published assets."""
from pathlib import Path
import argparse
import plistlib
import re
import zipfile


def version_metadata(version: str, build: str, commit: str) -> dict:
    version = version.strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?', version):
        raise ValueError('VERSION must be a three-part version with optional prerelease suffix')
    if not re.fullmatch(r'[1-9]\d*', build):
        raise ValueError('build must be a positive integer')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('commit must be a full SHA')
    return {'CFBundleShortVersionString': version.split('-')[0], 'CFBundleVersion': build,
            'MikeReleaseVersion': version, 'MikeSourceCommit': commit}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version-file', default='VERSION')
    parser.add_argument('--build', required=True)
    parser.add_argument('--commit', required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--stamp-plist')
    group.add_argument('--verify-ipa')
    args = parser.parse_args()
    expected = version_metadata(Path(args.version_file).read_text(), args.build, args.commit)
    if args.stamp_plist:
        path = Path(args.stamp_plist)
        data = plistlib.loads(path.read_bytes())
        data.update(expected)
        path.write_bytes(plistlib.dumps(data))
    else:
        with zipfile.ZipFile(args.verify_ipa) as archive:
            data = plistlib.loads(archive.read('Payload/Mike.app/Info.plist'))
        for key, value in expected.items():
            if data.get(key) != value:
                raise ValueError(f'Packaged IPA metadata mismatch for {key}')
    print(expected)


if __name__ == '__main__': main()
