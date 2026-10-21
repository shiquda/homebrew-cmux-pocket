class CmuxPocket < Formula
  desc "Rust Gateway and macOS service manager for cmux Pocket"
  homepage "https://github.com/shiquda/cmux-pocket"
  url "https://github.com/shiquda/cmux-pocket.git",
      tag:      "v0.2.0",
      revision: "97226dd2c7a2f9fb9ac1792c758798c3dcf8ed60"
  version "0.2.0"
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
    assert_match "cmux-pocket 0.2.0", shell_output("#{bin}/cmux-pocket --version")
    output = shell_output("#{bin}/cmux-pocket doctor --offline --json")
    assert_match '"ok": true', output
    assert_match '"code": 0', output
  end
end
