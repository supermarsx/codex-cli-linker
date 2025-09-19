class CodexCliLinker < Formula
  include Language::Python::Virtualenv

  desc "Generate Codex CLI profiles for local LLM servers"
  homepage "https://github.com/supermarsx/codex-cli-linker"
  url "https://github.com/supermarsx/codex-cli-linker/archive/refs/tags/v0.1.3.tar.gz"
  sha256 "8777e3a88c53eb72d6a4db5a150ef1ac88aaa7e747b412a23ee5f644686bfd3a"
  license "MIT"
  head "https://github.com/supermarsx/codex-cli-linker.git", branch: "main"

  depends_on "python@3.11"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/codex-cli-linker --version")
  end
end
