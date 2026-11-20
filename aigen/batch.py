"""Batch mode: every request (*.json) of a folder, with the model loaded only once.

    bin/aigen_batch.sh requests_folder output_folder

Each request x.json becomes output_folder/x.png (or x_001.png ... with "count"). A wrong or failed request does not
stop the others; the summary goes to output_folder/batch.aigen.json. Exit code: 0 all ok; 1 some failed; 2 the batch
itself is wrong (a folder that does not exist, no requests, a summary that already exists).
"""
import json
import os
import sys
import time

from aigen import VERSION, config, contract, generate, model

SUMMARY = "batch.aigen.json"


def parse_args(argv):
    p = generate._Options(prog=contract.command("aigen_batch"),
                          description="Generates the images of every request (*.json) of a folder.")
    p.add_argument("requests", help="the folder with the requests (*.json, docs/contract.md)")
    p.add_argument("output", help="the folder where the PNGs and the batch.aigen.json summary are written")
    p.add_argument("--version", action="version", version="AIGenerator " + VERSION)
    return p.parse_args(argv)


def list_requests(folder):
    if not os.path.isdir(folder):
        raise contract.RequestError("requests folder not found: " + folder)
    names = sorted(n for n in os.listdir(folder) if n.endswith(".json") and not n.endswith(".aigen.json"))
    if not names:
        raise contract.RequestError("the folder %s has no requests (*.json)" % folder)
    return [os.path.join(folder, n) for n in names]


def _one(path, destination, session, cfg):
    name = os.path.splitext(os.path.basename(path))[0]
    item = {"request": os.path.basename(path)}
    start = time.time()
    try:
        request = contract.normalize(contract.read_request(path), "the request " + os.path.basename(path))
        done = generate.run(request, os.path.join(destination, name + ".png"), session, cfg)
        item.update(ok=True, png=[os.path.basename(png) for png, _ in done])
    except contract.RequestError as e:
        item.update(ok=False, error="ERROR: %s" % e)
    except Exception as e:  # the batch goes on: the next request may work
        item.update(ok=False, error="ERROR: the generation failed: %s: %s" % (type(e).__name__, e))
    item["seconds"] = round(time.time() - start, 2)
    print(("ok     " if item["ok"] else "failed ") + item["request"] + ("" if item["ok"] else ": " + item["error"]))
    return item


def main(argv=None):
    a = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        cfg = config.read()
        requests = list_requests(a.requests)
        summary = os.path.join(a.output, SUMMARY)
        if os.path.exists(summary):
            raise contract.RequestError("the summary already exists (nothing is overwritten): " + summary)
    except contract.RequestError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return contract.BAD_REQUEST
    os.makedirs(a.output, exist_ok=True)
    session = model.Session(cfg)
    items = [_one(c, a.output, session, cfg) for c in requests]
    failures = sum(1 for i in items if not i["ok"])
    with open(summary, "x", encoding="utf-8") as f:
        json.dump({"format_version": contract.FORMAT_VERSION, "aigen": VERSION, "requests": items,
                   "failures": failures}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("%d request(s), %d failure(s); summary in %s" % (len(items), failures, summary))
    return contract.GENERATION_FAILED if failures else contract.OK


if __name__ == "__main__":
    sys.exit(main())
