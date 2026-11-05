import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('ios_version', Path(__file__).resolve().parents[1] / 'scripts/ios_version.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_preview_version_preserves_release_and_apple_numeric_version():
    result = module.version_metadata('0.4.4-preview.1\n', '123', 'a' * 40)
    assert result['CFBundleShortVersionString'] == '0.4.4'
    assert result['CFBundleVersion'] == '123'
    assert result['MikeReleaseVersion'] == '0.4.4-preview.1'
    assert result['MikeSourceCommit'] == 'a' * 40


@pytest.mark.parametrize('version,build,sha', [('bad', '1', 'a'*40), ('0.4.4', '0', 'a'*40), ('0.4.4', '12x', 'a'*40), ('0.4.4', '1', 'short')])
def test_invalid_provenance_refused(version, build, sha):
    with pytest.raises(ValueError): module.version_metadata(version, build, sha)
