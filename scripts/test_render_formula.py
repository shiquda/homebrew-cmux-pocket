#!/usr/bin/env python3
"""Renderer checks. Run from anywhere: python3 scripts/test_render_formula.py"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import render_formula  # noqa: E402


ARM = "a" * 64
INTEL = "b" * 64
REVISION = "dba5140cb71b45ac14e8c01d3e26b6a35401a1c3"


class RenderFormulaTest(unittest.TestCase):
    def test_source_render_matches_the_published_formula(self) -> None:
        rendered = render_formula.render_source("0.3.1", "v0.3.1", REVISION)
        current = (ROOT / "Formula" / "cmux-pocket.rb").read_text(encoding="utf-8")
        self.assertEqual(rendered, current)

    def test_binary_render_drops_rust_and_keeps_the_install_hooks(self) -> None:
        rendered = render_formula.render_binary("0.4.0", "v0.4.0", ARM, INTEL)
        self.assertNotIn('depends_on "rust"', rendered)
        self.assertNotIn("cargo", rendered)
        self.assertIn("depends_on macos: :big_sur", rendered)
        self.assertIn('bin.install "cmux-pocket"', rendered)
        self.assertIn("cmux-pocket-v0.4.0-aarch64-apple-darwin.tar.gz", rendered)
        self.assertIn("cmux-pocket-v0.4.0-x86_64-apple-darwin.tar.gz", rendered)
        self.assertIn(f'sha256 "{ARM}"', rendered)
        self.assertIn(f'sha256 "{INTEL}"', rendered)
        self.assertIn("launchctl kickstart -k gui/$(id -u)/com.cmuxpocket.gateway", rendered)
        self.assertIn("must_succeed: false", rendered)
        self.assertIn('assert_match "cmux-pocket 0.4.0"', rendered)
        self.assertIn('assert_match \'"ok": true\'', rendered)
        self.assertIn('assert_match \'"code": 0\'', rendered)
        self.assertNotIn("{version}", rendered)
        self.assertNotIn("{arm_sha256}", rendered)

    def test_binary_render_rejects_bad_inputs(self) -> None:
        with self.assertRaises(SystemExit):
            render_formula.render_binary("0.4", "v0.4.0", ARM, INTEL)
        with self.assertRaises(SystemExit):
            render_formula.render_binary("0.4.0", "v0.4.1", ARM, INTEL)
        with self.assertRaises(SystemExit):
            render_formula.render_binary("0.4.0", "v0.4.0", "sha256:" + ARM, "not-a-hash")
        with self.assertRaises(SystemExit):
            render_formula.render_source("0.3.1", "v0.3.1", "abc")

    def test_sha256_prefix_is_stripped(self) -> None:
        rendered = render_formula.render_binary("0.4.0", "v0.4.0", "sha256:" + ARM, INTEL.upper())
        self.assertIn(f'sha256 "{ARM}"', rendered)
        self.assertIn(f'sha256 "{INTEL}"', rendered)

    def test_current_release_assets_are_incomplete(self) -> None:
        names = ["app-release.apk", "release-metadata.txt"]
        missing = render_formula.missing_archives("v0.3.1", names)
        self.assertEqual(
            missing,
            [
                "cmux-pocket-v0.3.1-aarch64-apple-darwin.tar.gz",
                "cmux-pocket-v0.3.1-x86_64-apple-darwin.tar.gz",
            ],
        )

    def test_checksums_match_github_digest_and_reject_a_mismatch(self) -> None:
        arm_name, intel_name = render_formula.required_archives("v0.4.0")
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            arm = root / arm_name
            intel = root / intel_name
            arm.write_bytes(b"arm-bytes")
            intel.write_bytes(b"intel-bytes")
            arm_sha = render_formula.hashlib.sha256(b"arm-bytes").hexdigest()
            intel_sha = render_formula.hashlib.sha256(b"intel-bytes").hexdigest()
            payload = {
                "assets": [
                    {"name": arm_name, "digest": f"sha256:{arm_sha}"},
                    {"name": intel_name, "digest": f"sha256:{intel_sha}"},
                    {"name": "cmux-pocket-v0.4.0.apk"},
                ]
            }
            assets = root / "assets.json"
            assets.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(
                render_formula.checksums("v0.4.0", assets, root),
                {"arm_sha256": arm_sha, "intel_sha256": intel_sha},
            )
            payload["assets"][0]["digest"] = "sha256:" + ("c" * 64)
            assets.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(SystemExit):
                render_formula.checksums("v0.4.0", assets, root)

    def test_cli_check_archives_exits_2_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assets = pathlib.Path(tmp) / "assets.json"
            assets.write_text(json.dumps({"assets": [{"name": "app-release.apk"}]}), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render_formula.py"),
                    "check-archives",
                    "v0.3.1",
                    str(assets),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("cmux-pocket-v0.3.1-aarch64-apple-darwin.tar.gz", completed.stderr)


if __name__ == "__main__":
    unittest.main()
