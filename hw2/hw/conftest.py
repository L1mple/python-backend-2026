import sys
from pathlib import Path

# shop_api лежит рядом с тестами, а pytest часто запускают из корня репозитория
sys.path.insert(0, str(Path(__file__).resolve().parent))
