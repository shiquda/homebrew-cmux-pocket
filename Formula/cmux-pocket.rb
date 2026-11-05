class CmuxPocket < Formula
  desc "Rust Gateway and macOS service manager for cmux Pocket"
  homepage "https://github.com/shiquda/cmux-pocket"
  version "0.4.0"
  license "AGPL-3.0-or-later"

  # Mach-O minos is 11.0, so older than Big Sur cannot load the binary.
  # That floor is not a tested support matrix; release builds run on the
  # current macOS runners. The archive is a single cmux-pocket file.
  on_macos do
    on_arm do
      url "https://github.com/shiquda/cmux-pocket/releases/download/v0.4.0/cmux-pocket-v0.4.0-aarch64-apple-darwin.tar.gz"
      sha256 "d244c8bb3fc62929f3578c9e4089374a17e3feeff3a9dd5150b4e9d1bc04e8e4"
    end
    on_intel do
      url "https://github.com/shiquda/cmux-pocket/releases/download/v0.4.0/cmux-pocket-v0.4.0-x86_64-apple-darwin.tar.gz"
      sha256 "3d3eea50567401638fe690403b97fa2f37083e2249704611de8be09cf7cc981c"
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
    assert_match "cmux-pocket 0.4.0", shell_output("#{bin}/cmux-pocket --version")
    output = shell_output("#{bin}/cmux-pocket doctor --offline --json")
    assert_match '"ok": true', output
    assert_match '"code": 0', output
  end
end
