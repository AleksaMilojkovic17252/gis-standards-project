import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

frost_url = os.environ.get("FROST_URL", "http://frost:8080/FROST-Server/v1.1").rstrip("/")
source_start = datetime.fromisoformat(os.environ.get("SOURCE_START", "2026-11-12T00:00:00+00:00"))
target_start = datetime.fromisoformat(os.environ.get("TARGET_START", "2026-11-14T00:00:00+00:00"))
seconds_per_step = float(os.environ.get("SECONDS_PER_STEP", "5"))
steps = int(os.environ.get("STEPS", "144"))
step = timedelta(minutes=10)


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def get_json(path, query):
    with urllib.request.urlopen(f"{frost_url}/{path}?{urllib.parse.urlencode(query)}") as response:
        return json.load(response)


def post_json(path, body):
    request = urllib.request.Request(f"{frost_url}/{path}", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(request).close()


datastream_ids = [item["@iot.id"] for item in get_json("Datastreams", {"$select": "id", "$top": "1000"})["value"]]
source_end = source_start + step * steps
series = {}
for datastream_id in datastream_ids:
    observations = get_json(f"Datastreams({datastream_id})/Observations", {
        "$filter": f"phenomenonTime ge {iso(source_start)} and phenomenonTime lt {iso(source_end)}",
        "$select": "phenomenonTime,result",
        "$top": "2000",
    })["value"]
    series[datastream_id] = {observation["phenomenonTime"]: observation["result"] for observation in observations}
print(f"{len(datastream_ids)} datastreams, replaying {iso(source_start)} as {iso(target_start)}, "
      f"{steps} steps of 10 min, one step every {seconds_per_step} s", flush=True)

for index in range(steps):
    started = time.monotonic()
    source_time = iso(source_start + step * index)
    target_time = iso(target_start + step * index)
    posted = 0
    for datastream_id, values in series.items():
        if source_time in values:
            post_json("Observations", {
                "phenomenonTime": target_time,
                "result": values[source_time],
                "parameters": {"replay": True, "replayed_from": source_time},
                "Datastream": {"@iot.id": datastream_id},
            })
            posted += 1
    print(f"{target_time}  {posted} observations", flush=True)
    time.sleep(max(0.0, seconds_per_step - (time.monotonic() - started)))
