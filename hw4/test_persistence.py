import json
import os
from pathlib import Path
import subprocess
import sys


def run_api(code, database):
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "hw2" / "hw")
    result = subprocess.run(
        [sys.executable, "-c", "from fastapi.testclient import TestClient\n"
         "from shop_api.main import app\nclient = TestClient(app)\n" + code],
        env=env, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def test_cart_survives_process_restart(tmp_path):
    database = tmp_path / "shop.db"
    cart_id = run_api(
        "item = client.post('/item', json={'name': 'Book', 'price': 10}).json()\n"
        "cart = client.post('/cart').json()\n"
        "client.post(f\"/cart/{cart['id']}/add/{item['id']}\")\n"
        "print(cart['id'])", database,
    )
    cart = run_api(f"import json\nprint(json.dumps(client.get('/cart/{cart_id}').json()))", database)
    assert cart["price"] == 10
    assert cart["items"][0] == {"id": 1, "name": "Book", "quantity": 1, "available": True}
