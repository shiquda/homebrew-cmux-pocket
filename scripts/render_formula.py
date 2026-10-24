#!/usr/bin/env python3
"""Render Formula/cmux-pocket.rb for a released cmux-pocket tag.

The tap is the only source of truth for the formula. The scheduled workflow
calls ``binary`` only when the latest published release is newer than the
formula and both macOS archives are present. An equal version is left alone,
so a manual same-version rollback is not overwritten on the next poll.

``source`` reprints the previous git/cargo formula for that manual rollback.
The scheduled workflow never calls it. Reverting this script is still required
if the next newer release should go back to a source build; otherwise that
release renders binary archives again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

ARM_TARGET = "aarch64-apple-darwin"
INTEL_TARGET = "x86_64-apple-darwin"
MISSING_ARCHIVES = 2

SOURCE_TEMPLATE = """\
class CmuxPocket < Formula
  desc "Rust Gateway and macOS service manager for cmux Pocket"
  homepage "https://github.com/shiquda/cmux-pocket"
  url "https://github.com/shiquda/cmux-pocket.git",
      tag:      "{tag}",
      revision: "{revision}"
  version "{version}"
  license "AGPL-3.0-or-later"

  depends_on "rust" => :build

  def install
    system "cargo", "install", *std_cargo_args(path: "crates/cmux-pocket-cli")
  end

  # Upgrading replaces the binary on disk while launchd keeps the previous
  # Gateway process. Restart the registered agent so the new build serves the
  # phone immediately instead of at the next login.
  post_install_steps do
    run "/bin/sh",
        args:         ["-c", "launchctl kickstart -k gui/$(id -u)/com.cmuxpocket.gateway"],
        must_succeed: false
  end

  test do
    assert_match "cmux-pocket {version}", shell_output("#{{bin}}/cmux-pocket --version")
    output = shell_output("#{{bin}}/cmux-pocket doctor --offline --json")
    assert_match '"ok": true', output
    assert_match '"code": 0', output
  end
end
"""

BINARY_TEMPLATE = """\
class CmuxPocket < Formula
  desc "Rust Gateway and macOS service manager for cmux Pocket"
  homepage "https://github.com/shiquda/cmux-pocket"
  version "{version}"
  license "AGPL-3.0-or-later"

  # Mach-O minos is 11.0, so older than Big Sur cannot load the binary.
  # That floor is not a tested support matrix; release builds run on the
  # current macOS runners. The archive is a single cmux-pocket file.
  on_macos do
    on_arm do
      url "https://github.com/shiquda/cmux-pocket/releases/download/v{version}/cmux-pocket-v{version}-aarch64-apple-darwin.tar.gz"
      sha256 "{arm_sha256}"
    end
    on_intel do
      url "https://github.com/shiquda/cmux-pocket/releases/download/v{version}/cmux-pocket-v{version}-x86_64-apple-darwin.tar.gz"
      sha256 "{intel_sha256}"
    end
  end

  depends_on macos: :big_sur

  def install
    bin.install "cmux-pocket"
  end

  # Upgrading replaces the binary on disk while launchd keeps the previous
  # Gateway process. Restart the registered agent so the new build serves the
  # phone immediately instead of at the next login.
  post_install_steps do
    run "/bin/sh",
        args:         ["-c", "launchctl kickstart -k gui/$(id -u)/com.cmuxpocket.gateway"],
        must_succeed: false
  end

  test do
    assert_match "cmux-pocket {version}", shell_output("#{{bin}}/cmux-pocket --version")
    output = shell_output("#{{bin}}/cmux-pocket doctor --offline --json")
    assert_match '"ok": true', output
    assert_match '"code": 0', output
  end
end
"""

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def archive_name(tag: str, target: str) -> str:
    return f"cmux-pocket-{tag}-{target}.tar.gz"


def required_archives(tag: str) -> tuple[str, str]:
    _validate_tag(tag)
    return archive_name(tag, ARM_TARGET), archive_name(tag, INTEL_TARGET)


def missing_archives(tag: str, asset_names: list[str]) -> list[str]:
    present = set(asset_names)
    return [name for name in required_archives(tag) if name not in present]


def render_binary(version: str, tag: str, arm_sha256: str, intel_sha256: str) -> str:
    _validate_version_tag(version, tag)
    arm_sha256 = _validate_sha256(arm_sha256, "arm64")
    intel_sha256 = _validate_sha256(intel_sha256, "intel")
    return BINARY_TEMPLATE.format(
        version=version,
        arm_sha256=arm_sha256,
        intel_sha256=intel_sha256,
    )


def render_source(version: str, tag: str, revision: str) -> str:
    _validate_version_tag(version, tag)
    if not REVISION_PATTERN.match(revision):
        raise SystemExit(f"revision '{revision}' is not a 40-character commit sha")
    return SOURCE_TEMPLATE.format(version=version, tag=tag, revision=revision)


def checksums(tag: str, assets_json: pathlib.Path, archive_dir: pathlib.Path) -> dict[str, str]:
    """Hash the downloaded archives and require a matching GitHub digest when present."""
    arm_name, intel_name = required_archives(tag)
    assets = _load_assets(assets_json)
    names = [asset.get("name", "") for asset in assets]
    missing = missing_archives(tag, names)
    if missing:
        raise SystemExit(f"missing release archives: {', '.join(missing)}")
    by_name = {asset.get("name", ""): asset for asset in assets}
    hashed = {
        "arm_sha256": _hash_asset(archive_dir / arm_name, by_name[arm_name]),
        "intel_sha256": _hash_asset(archive_dir / intel_name, by_name[intel_name]),
    }
    return hashed


def _validate_tag(tag: str) -> str:
    if not tag.startswith("v") or not VERSION_PATTERN.match(tag[1:]):
        raise SystemExit(f"tag '{tag}' does not look like vMAJOR.MINOR.PATCH")
    return tag


def _validate_version_tag(version: str, tag: str) -> None:
    if not VERSION_PATTERN.match(version):
        raise SystemExit(f"unsupported version '{version}': expected MAJOR.MINOR.PATCH")
    if tag != f"v{version}":
        raise SystemExit(f"tag '{tag}' does not match version '{version}'")


def _validate_sha256(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if normalized.startswith("sha256:"):
        normalized = normalized[len("sha256:") :]
    if not SHA256_PATTERN.match(normalized):
        raise SystemExit(f"{label} sha256 '{value}' is not 64 hex characters")
    return normalized


def _load_assets(path: pathlib.Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"could not read release assets: {error}") from error
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list):
        raise SystemExit("release assets JSON has no assets array")
    return assets


def _hash_asset(path: pathlib.Path, asset: dict[str, object]) -> str:
    if not path.is_file():
        raise SystemExit(f"archive was not downloaded: {path.name}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    declared = asset.get("digest")
    if isinstance(declared, str) and declared.startswith("sha256:"):
        expected = _validate_sha256(declared, path.name)
        if digest != expected:
            raise SystemExit(
                f"{path.name} sha256 {digest} does not match GitHub digest {expected}"
            )
    return digest


def _write(path: pathlib.Path, formula: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(formula, encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    binary = subparsers.add_parser("binary", help="render a prebuilt macOS formula")
    binary.add_argument("version")
    binary.add_argument("tag")
    binary.add_argument("arm_sha256")
    binary.add_argument("intel_sha256")
    binary.add_argument("--output", type=pathlib.Path, default=pathlib.Path("Formula/cmux-pocket.rb"))

    source = subparsers.add_parser("source", help="render the git/cargo formula for a manual rollback")
    source.add_argument("version")
    source.add_argument("tag")
    source.add_argument("revision")
    source.add_argument("--output", type=pathlib.Path, default=pathlib.Path("Formula/cmux-pocket.rb"))

    check = subparsers.add_parser("check-archives", help="exit 2 when either macOS archive is absent")
    check.add_argument("tag")
    check.add_argument("assets_json", type=pathlib.Path)

    hashed = subparsers.add_parser("checksums", help="print arm_sha256 and intel_sha256")
    hashed.add_argument("tag")
    hashed.add_argument("assets_json", type=pathlib.Path)
    hashed.add_argument("archive_dir", type=pathlib.Path)

    args = parser.parse_args(argv)
    if args.command == "binary":
        _write(args.output, render_binary(args.version, args.tag, args.arm_sha256, args.intel_sha256))
        return 0
    if args.command == "source":
        _write(args.output, render_source(args.version, args.tag, args.revision))
        return 0
    if args.command == "check-archives":
        assets = _load_assets(args.assets_json)
        missing = missing_archives(args.tag, [str(asset.get("name", "")) for asset in assets])
        if missing:
            print("missing " + ", ".join(missing), file=sys.stderr)
            return MISSING_ARCHIVES
        return 0
    digests = checksums(args.tag, args.assets_json, args.archive_dir)
    print(f"arm_sha256={digests['arm_sha256']}")
    print(f"intel_sha256={digests['intel_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
