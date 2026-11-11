class CmuxPocket < Formula
  desc "Rust Gateway and macOS service manager for cmux Pocket"
  homepage "https://github.com/shiquda/cmux-pocket"
  version "0.4.1"
  license "AGPL-3.0-or-later"

  # Mach-O minos is 11.0, so older than Big Sur cannot load the binary.
  # That floor is not a tested support matrix; release builds run on the
  # current macOS runners. The archive is a single cmux-pocket file.
  on_macos do
    on_arm do
      url "https://github.com/shiquda/cmux-pocket/releases/download/v0.4.1/cmux-pocket-v0.4.1-aarch64-apple-darwin.tar.gz"
      sha256 "5a78731bea45a82b5c50ad6f9920f45e5fc5af347fb4765d9b5478170003065c"
    end
    on_intel do
      url "https://github.com/shiquda/cmux-pocket/releases/download/v0.4.1/cmux-pocket-v0.4.1-x86_64-apple-darwin.tar.gz"
      sha256 "3f38c1e4727e3e99939ce3a247e696ba752c316a8c4b8322d0c07a9adaf76775"
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
    assert_match "cmux-pocket 0.4.1", shell_output("#{bin}/cmux-pocket --version")
    output = shell_output("#{bin}/cmux-pocket doctor --offline --json")
    assert_match '"ok": true', output
    assert_match '"code": 0', output
  end
end
