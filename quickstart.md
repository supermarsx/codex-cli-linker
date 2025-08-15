# Interactive

python codex-lmstudio-linker.py

# Auto-detect + launch Codex when done

python codex-lmstudio-linker.py --auto --launch

# Fully non-interactive example

python codex-lmstudio-linker.py \
  --base-url <http://localhost:1234/v1> \
  --model llama-3.1-8b \
  --provider lmstudio \
  --profile lmstudio \
  --api-key sk-local \
  --launch
