import json, datetime, os
LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_log.jsonl")


def log(rec):
    rec = dict(rec); rec.setdefault("date", datetime.date.today().isoformat())
    with open(LOG, "a") as f: f.write(json.dumps(rec, default=float, ensure_ascii=False) + "\n")
