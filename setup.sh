#!/usr/bin/env bash
# Yap Editor setup (macOS). Safe to run again: it skips anything you already have.
# Free from @thoseaiguys
set -e
cd "$(dirname "$0")"

say() { printf "\n\033[1;33m==>\033[0m \033[1m%s\033[0m\n" "$1"; }

if [ "$(uname)" != "Darwin" ]; then
  echo "This setup script is for Mac. On Windows/Linux install ffmpeg, Node 18+, Python 3.10-3.12, then:"
  echo "  python3 -m venv .venv && .venv/bin/pip install whisperx==3.8.6"
  exit 1
fi

say "1/4  Homebrew (the Mac app store for developer tools)"
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)"; done
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew isn't installed. Paste this into Terminal, follow the prompts, then run  bash setup.sh  again:"
  echo
  echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 1
fi
echo "ok"

say "2/4  ffmpeg (cuts the video), Node (draws the captions), Python 3.12 (runs WhisperX)"
for pkg in ffmpeg node; do
  if command -v "$pkg" >/dev/null 2>&1; then echo "$pkg: already installed"; else brew install "$pkg"; fi
done
if brew list --versions python@3.12 >/dev/null 2>&1; then echo "python 3.12: already installed"; else brew install python@3.12; fi
PY="$(brew --prefix)/opt/python@3.12/bin/python3.12"

say "3/4  WhisperX (listens to every word, with exact timings). This one takes a few minutes."
if [ ! -x .venv/bin/whisperx ]; then
  "$PY" -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet "whisperx==3.8.6"
fi
.venv/bin/whisperx --help >/dev/null 2>&1 && echo "WhisperX is ready"

say "4/4  HyperFrames (the caption renderer)"
npx --yes hyperframes@0.8.140 --version >/dev/null 2>&1 || true
echo "ok"

printf "\n\033[1;32mAll set.\033[0m Try it:\n\n  python3 yap.py cut /path/to/your-video.mov\n\n"
echo "(The first video downloads the speech models, about 1 GB, one time only.)"
