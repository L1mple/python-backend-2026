import os
import tempfile

if "DATABASE_URL" not in os.environ:
    _db_dir = tempfile.mkdtemp(prefix="hw2-tests-")
    _db_path = os.path.join(_db_dir, "shop.db")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_path}"
