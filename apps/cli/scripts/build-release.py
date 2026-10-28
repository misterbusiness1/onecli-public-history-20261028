#!/usr/bin/env python3
"""Build the standalone CLI release channel; never publish server images."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [(system, arch) for system in ('linux', 'darwin', 'windows') for arch in ('amd64', 'arm64')]


def build(output: Path, tag: str, go: str) -> dict:
    version = (ROOT / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', version):
        raise ValueError('Invalid CLI version')
    if tag != 'cli/v' + version:
        raise ValueError('Release tag must match the independent CLI VERSION')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Release output must be empty; existing assets are not overwritten')
    output.mkdir(parents=True, exist_ok=True)
    workspace = output / '.build'
    workspace.mkdir()
    records = []
    try:
        for system, arch in TARGETS:
            binary = 'onecli.exe' if system == 'windows' else 'onecli'
            target = workspace / (system + '-' + arch)
            target.mkdir()
            env = dict(os.environ, GOOS=system, GOARCH=arch, CGO_ENABLED='0')
            subprocess.run([go, 'build', '-trimpath', '-buildvcs=false', '-ldflags', '-s -w -X main.version=' + version, '-o', str(target / binary), './cmd/onecli'], cwd=ROOT, env=env, check=True)
            members = [(binary, (target / binary).read_bytes(), 0o755), ('LICENSE', (ROOT / 'LICENSE').read_bytes(), 0o644)]
            suffix = '.zip' if system == 'windows' else '.tar.gz'
            archive = output / f'onecli_{version}_{system}_{arch}{suffix}'
            if suffix == '.zip':
                with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                    for name, content, mode in members:
                        info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                        info.external_attr = mode << 16
                        info.compress_type = zipfile.ZIP_DEFLATED
                        z.writestr(info, content)
            else:
                with archive.open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as gz, tarfile.open(fileobj=gz, mode='w|') as t:
                    for name, content, mode in members:
                        info = tarfile.TarInfo(name)
                        info.size = len(content)
                        info.mode = mode
                        info.mtime = 0
                        t.addfile(info, io.BytesIO(content))
            records.append({'name': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'bytes': archive.stat().st_size, 'os': system, 'arch': arch})
    finally:
        shutil.rmtree(workspace)
    (output / 'checksums.txt').write_text(''.join(f"{row['sha256']}  {row['name']}\n" for row in sorted(records, key=lambda x: x['name'])))
    manifest = {'tag': tag, 'version': version, 'targets': records, 'channel': 'cli', 'server_release': False}
    (output / 'release-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--go', default='go')
    args = parser.parse_args()
    print(json.dumps(build(args.output.resolve(), args.tag, args.go), indent=2))
