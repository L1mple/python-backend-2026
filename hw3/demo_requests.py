import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(
        "http://127.0.0.1:8000" + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=5) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code != 404:
            raise
        error.close()


if __name__ == "__main__":
    item = request("/item", "POST", {"name": "Notebook", "price": 100})
    cart = request("/cart", "POST")
    request(f"/cart/{cart['id']}/add/{item['id']}", "POST")
    print("Sending requests to the local shop for 2 minutes...")
    for i in range(240):
        request("/item")
        request(f"/item/{item['id']}")
        request(f"/cart/{cart['id']}")
        if i % 5 == 0:
            request("/item/999999")
        time.sleep(0.5)
    print("Done. Open Grafana to see the graphs.")
