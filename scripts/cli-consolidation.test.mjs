import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  readFileSync,
  rmSync,
  existsSync,
  symlinkSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";

const root = fileURLToPath(new URL("../", import.meta.url));
const installer = join(root, "apps/cli/scripts/install.sh");
const read = (path) => readFileSync(join(root, path), "utf8");

test("CLI tags and version selection cannot select a server release", () => {
  const publish = read(".github/workflows/publish-cli.yml");
  assert.match(publish, /tags: \["cli\/v\*"\]/);
  assert.match(publish, /--latest=false/);
  assert.match(publish, /cli\/v\$\(cat apps\/cli\/VERSION\)/);
  assert.match(read(".github/workflows/publish.yml"), /- "v\*"/);
  const script = read("apps/cli/scripts/install.sh");
  assert.match(script, /ONECLI_CLI_VERSION/);
  assert.doesNotMatch(script, /\$\{ONECLI_VERSION/);
  assert.doesNotMatch(script, /releases\/latest|onecli\.sh\/cli\/version/);
  assert.match(script, /misterbusiness1\/onecli/);
  assert.match(script, /cli%2Fv\$VERSION/);
});

test("both CLI workflows resolve Go tooling from the relocated module", () => {
  for (const path of [
    ".github/workflows/cli-ci.yml",
    ".github/workflows/publish-cli.yml",
  ]) {
    assert.match(read(path), /go-version-file: apps\/cli\/go\.mod/);
    assert.match(read(path), /working-directory: apps\/cli/);
    assert.match(read(path), /go test -race/);
  }
  assert.equal(
    existsSync(join(root, "apps/cli/.github/workflows/release.yml")),
    false,
  );
});

test("server bootstrap scripts select the canonical CLI installer", () => {
  for (const path of [
    "packages/api/src/routes/install.ts",
    "packages/api/src/routes/migrate-nanoclaw.ts",
    "apps/web/src/app/(dashboard)/w/[workspaceId]/settings/install/_components/install-content.tsx",
  ]) {
    assert.match(
      read(path),
      /raw\.githubusercontent\.com\/misterbusiness1\/onecli\/main\/apps\/cli\/scripts\/install\.sh/,
    );
    assert.doesNotMatch(read(path), /onecli\.sh\/cli\/install/);
  }
});

function fixture(
  t,
  {
    binaryVersion = "2.11.1",
    corrupt = false,
    failDownload = false,
    symlink = false,
  } = {},
) {
  const dir = mkdtempSync(join(tmpdir(), "onecli-installer-test-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const bin = join(dir, "bin");
  const install = join(dir, "installed");
  const members = join(dir, "members");
  for (const p of [bin, install, members]) mkdirSync(p);
  writeFileSync(join(install, "onecli"), "existing installation\n");
  if (symlink) symlinkSync("LICENSE", join(members, "onecli"));
  else
    writeFileSync(
      join(members, "onecli"),
      `#!/bin/sh\nprintf '%s\\n' '{"name":"onecli","version":"${binaryVersion}"}'\n`,
      { mode: 0o755 },
    );
  writeFileSync(join(members, "LICENSE"), "Apache-2.0 fixture\n");
  const archive = join(dir, "archive.tar.gz");
  const tar = spawnSync("tar", [
    "-czf",
    archive,
    "-C",
    members,
    "onecli",
    "LICENSE",
  ]);
  assert.equal(tar.status, 0);
  const digest = corrupt
    ? "0".repeat(64)
    : createHash("sha256").update(readFileSync(archive)).digest("hex");
  const checksum = join(dir, "checksums.txt");
  writeFileSync(checksum, `${digest}  onecli_2.11.1_linux_amd64.tar.gz\n`);
  const log = join(dir, "urls.txt");
  writeFileSync(
    join(bin, "uname"),
    '#!/bin/sh\ncase "$1" in -s) echo Linux ;; -m) echo x86_64 ;; *) exit 1 ;; esac\n',
    { mode: 0o755 },
  );
  writeFileSync(
    join(bin, "curl"),
    `#!/bin/sh
set -eu
url=; output=
while [ "$#" -gt 0 ]; do
  case "$1" in https://*) url=$1 ;; -o) shift; output=$1 ;; esac
  shift
done
printf '%s\\n' "$url" >> "$TEST_CURL_LOG"
case "$url" in
  https://raw.githubusercontent.com/misterbusiness1/onecli/main/apps/cli/VERSION) printf '2.11.1\\n' > "$output" ;;
  https://github.com/misterbusiness1/onecli/releases/download/cli%2Fv2.11.1/checksums.txt) cp "$TEST_CHECKSUMS" "$output" ;;
  https://github.com/misterbusiness1/onecli/releases/download/cli%2Fv2.11.1/onecli_2.11.1_linux_amd64.tar.gz)
    [ "$TEST_FAIL_DOWNLOAD" != 1 ] || exit 22
    cp "$TEST_ARCHIVE" "$output" ;;
  *) echo "unexpected installer URL" >&2; exit 22 ;;
esac
`,
    { mode: 0o755 },
  );
  const env = {
    ...process.env,
    PATH: `${bin}:${process.env.PATH}`,
    ONECLI_INSTALL_DIR: install,
    ONECLI_CLI_VERSION: "",
    ONECLI_VERSION: "9.9.9",
    TEST_ARCHIVE: archive,
    TEST_CHECKSUMS: checksum,
    TEST_CURL_LOG: log,
    TEST_FAIL_DOWNLOAD: failDownload ? "1" : "0",
  };
  const result = spawnSync("sh", [installer], {
    env,
    encoding: "utf8",
    timeout: 15000,
  });
  return {
    result,
    installed: () => readFileSync(join(install, "onecli"), "utf8"),
    urls: () => readFileSync(log, "utf8"),
    dir,
  };
}

test("installer verifies the canonical asset and ignores a server version pin", (t) => {
  const x = fixture(t);
  assert.equal(x.result.status, 0, x.result.stderr);
  assert.match(x.installed(), /2\.11\.1/);
  assert.match(x.urls(), /cli%2Fv2\.11\.1/);
  assert.doesNotMatch(x.urls(), /9\.9\.9|onecli-cli/);
});
for (const [name, options, error] of [
  ["checksum mismatch", { corrupt: true }, /checksum mismatch/],
  ["download failure", { failDownload: true }, null],
  ["wrong binary version", { binaryVersion: "2.11.0" }, /does not match/],
  ["regex-like wrong version", { binaryVersion: "2a11b1" }, /does not match/],
  ["symlink binary", { symlink: true }, /non-regular/],
]) {
  test(`installer preserves the existing executable on ${name}`, (t) => {
    const x = fixture(t, options);
    assert.notEqual(x.result.status, 0);
    assert.equal(x.installed(), "existing installation\n");
    if (error) assert.match(x.result.stderr, error);
  });
}

test("CLI release builder rejects server tags before invoking a compiler", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "onecli-release-channel-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const output = join(dir, "release");
  const result = spawnSync(
    "python3",
    [
      join(root, "apps/cli/scripts/build-release.py"),
      "--tag",
      "v2.0.1",
      "--output",
      output,
      "--go",
      "compiler-must-not-run",
    ],
    { encoding: "utf8" },
  );
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Release tag must match/);
  assert.equal(existsSync(output), false);
});
