import sys
from pathlib import Path

# Make `shop_api` importable regardless of where pytest is invoked from.
# Needed because `hw/__init__.py` makes pytest add the parent `hw2/` directory
# to sys.path instead of this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
