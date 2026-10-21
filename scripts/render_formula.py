#!/usr/bin/env python3
"""Render Formula/cmux-pocket.rb for a released cmux-pocket tag.

The tap is the only source of truth for the formula: the release pipeline in
shiquda/cmux-pocket only tags commits, and this repository's workflow resolves
the tag, verifies the tagged source declares the same version, and rewrites the
formula from this template. Nothing else edits Formula/cmux-pocket.rb.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

TEMPLATE = """\
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

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def render(version: str, tag: str, revision: str) -> str:
    if not VERSION_PATTERN.match(version):
        raise SystemExit(f"unsupported version '{version}': expected MAJOR.MINOR.PATCH")
    if tag != f"v{version}":
        raise SystemExit(f"tag '{tag}' does not match version '{version}'")
    if not REVISION_PATTERN.match(revision):
        raise SystemExit(f"revision '{revision}' is not a 40-character commit sha")
    return TEMPLATE.format(version=version, tag=tag, revision=revision)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="release version without the leading v")
    parser.add_argument("tag", help="release tag, e.g. v0.3.0")
    parser.add_argument("revision", help="commit sha the tag resolves to")
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("Formula/cmux-pocket.rb"),
        help="formula path to write (default: Formula/cmux-pocket.rb)",
    )
    args = parser.parse_args(argv)

    formula = render(args.version, args.tag, args.revision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(formula, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
