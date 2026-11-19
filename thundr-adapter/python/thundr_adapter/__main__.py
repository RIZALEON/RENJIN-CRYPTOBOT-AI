"""`python3 -m thundr_adapter ...` — same as the `thundr-adapter` CLI."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
