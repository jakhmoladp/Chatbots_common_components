"""Run module 3 standalone:  python -m modules.language_detection "your text" """

import argparse
import sys

from .detector import detect_language
from .languages import SUPPORTED_LANGUAGES


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect the language of a piece of text.")
    parser.add_argument("text", nargs="?", help="Text to inspect. Omit to read stdin.")
    parser.add_argument("--list", action="store_true", help="Print supported codes and exit.")
    args = parser.parse_args()

    if args.list:
        for code, name in sorted(SUPPORTED_LANGUAGES.items()):
            print(f"{code}\t{name}")
        return 0

    text = args.text if args.text is not None else sys.stdin.read()
    result = detect_language(text)
    print(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
