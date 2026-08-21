#!/usr/bin/env python3
"""Pre-download a Whisper model so the API does not hang on first transcription."""
import argparse
import os
import socket
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

SOCKET_TIMEOUT_SECONDS = 30


def main():
    parser = argparse.ArgumentParser(description="Download and cache a Whisper model")
    parser.add_argument("--model", default="base", help="Model name (default: base)")
    args = parser.parse_args()

    socket.setdefaulttimeout(SOCKET_TIMEOUT_SECONDS)

    cache_dir = Path.home() / ".cache" / "whisper"
    cache_path = cache_dir / f"{args.model}.pt"
    if cache_path.is_file() and cache_path.stat().st_size > 0:
        size_mb = cache_path.stat().st_size / (1024 * 1024)
        print(f"Model '{args.model}' already cached at {cache_path} ({size_mb:.1f} MB)")
        return

    print(f"Downloading Whisper model '{args.model}' (timeout {SOCKET_TIMEOUT_SECONDS}s per network op)...")
    import whisper

    whisper.load_model(args.model)
    print(f"Done. Model cached in {cache_dir}")


if __name__ == "__main__":
    main()
