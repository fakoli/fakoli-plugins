import json
request = json.load(open("request.json", encoding="utf-8"))
assert request == {"operation": "deploy", "dry_run": True}
