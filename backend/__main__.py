"""Package entry point for `python -m backend`."""

import sys

from backend.main import main

if __name__ == "__main__":
    main(sys.argv[1:])
