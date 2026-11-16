#!/usr/bin/env python3
"""
Build measured data into Analog Atlas.

Takes the app (analog-atlas.html) and the pipeline output (earth_sites_measured.json)
and writes a new HTML file with the data built in, so every visitor sees the
measured values without clicking "Load measured data".

    python bake_data.py
    python bake_data.py --app analog-atlas.html --data earth_sites_measured.json --out analog-atlas-measured.html
"""
import argparse, json, re, sys

ap = argparse.ArgumentParser()
ap.add_argument("--app", default="analog-atlas.html")
ap.add_argument("--data", default="earth_sites_measured.json")
ap.add_argument("--out", default="analog-atlas-measured.html")
a = ap.parse_args()

html = open(a.app, encoding="utf-8").read()
data = json.load(open(a.data, encoding="utf-8"))
if "sites" not in data:
    sys.exit("That JSON has no 'sites' section. Use the file written by earth_pipeline.py.")

pattern = re.compile(r"const BAKED_DATA = .*?;\n")
if not pattern.search(html):
    sys.exit("Couldn't find 'const BAKED_DATA' in the app. Use the latest analog-atlas.html.")

# '</' is escaped so the JSON can never close the <script> tag early.
payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
html = pattern.sub(lambda m: f"const BAKED_DATA = {payload};\n", html, count=1)
open(a.out, "w", encoding="utf-8").write(html)

n = len(data["sites"])
vals = sum(len(s.get("values", {})) for s in data["sites"].values())
errs = sum(len(s.get("errors", [])) for s in data["sites"].values())
print(f"Built {vals} measured values for {n} sites into {a.out}"
      + (f" ({errs} lookups failed and stay as estimates)" if errs else ""))
