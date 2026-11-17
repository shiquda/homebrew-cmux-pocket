class CmuxPocket < Formula
  desc "Rust Gateway and macOS service manager for cmux Pocket"
  homepage "https://github.com/shiquda/cmux-pocket"
  version "0.4.2"
  license "AGPL-3.0-or-later"

  # Mach-O minos is 11.0, so older than Big Sur cannot load the binary.
  # That floor is not a tested support matrix; release builds run on the
  # current macOS runners. The archive is a single cmux-pocket file.
  on_macos do
    on_arm do
      url "https://github.com/shiquda/cmux-pocket/releases/download/v0.4.2/cmux-pocket-v0.4.2-aarch64-apple-darwin.tar.gz"
      sha256 "c70cc58e3bb0dd7fbbe21542e36607d4f463f6261038d42030c4ecda4585fa89"
    end
    on_intel do
      url "https://github.com/shiquda/cmux-pocket/releases/download/v0.4.2/cmux-pocket-v0.4.2-x86_64-apple-darwin.tar.gz"
      sha256 "fcff6f36b42e13a739dcc9b8fd385898e1986ccc92b99e4cc060bb221cc2354f"
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
    assert_match "cmux-pocket 0.4.2", shell_output("#{bin}/cmux-pocket --version")
    output = shell_output("#{bin}/cmux-pocket doctor --offline --json")
    assert_match '"ok": true', output
    assert_match '"code": 0', output
  end
end
