class CodexCliLinker < Formula
  include Language::Python::Virtualenv

  desc "Generate Codex CLI profiles for local LLM servers"
  homepage "https://github.com/supermarsx/codex-cli-linker"
  url "https://github.com/supermarsx/codex-cli-linker/archive/refs/tags/v0.1.2.tar.gz"
  sha256 "609b9ecb07d3626e66b7b811c159fdbc66dde07f52ef32b322a3864df0615098"
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
