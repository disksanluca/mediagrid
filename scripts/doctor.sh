#!/usr/bin/env bash
set -uo pipefail
check() { if command -v "$1" >/dev/null 2>&1; then printf 'OK  %-12s %s\n' "$1" "$($1 "$2" 2>/dev/null | head -n 1)"; else printf 'MISS %-12s\n' "$1"; fi; }
check node --version
check npm --version
check python3 --version
check uv --version
check ffmpeg -version
if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then echo "OK  Ollama"; else echo "INFO Ollama not running (local fallback active)"; fi
