import json
import os
import urllib.parse
import urllib.request

frost_url = os.environ.get("FROST_URL", "http://frost:8080/FROST-Server/v1.1").rstrip("/")
period_end = os.environ.get("PERIOD_END", "2026-11-13T23:50:00Z")

query = urllib.parse.urlencode({"$filter": f"phenomenonTime gt {period_end}", "$select": "id", "$top": "1000"})
deleted = 0
while True:
    with urllib.request.urlopen(f"{frost_url}/Observations?{query}") as response:
        ids = [item["@iot.id"] for item in json.load(response)["value"]]
    if not ids:
        break
    for observation_id in ids:
        urllib.request.urlopen(urllib.request.Request(f"{frost_url}/Observations({observation_id})",
                                                      method="DELETE")).close()
    deleted += len(ids)
    print(f"{deleted} deleted", flush=True)
print(f"done: {deleted} observations after {period_end} deleted")
