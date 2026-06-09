#!/usr/bin/env python3
"""
Local HTTP server for the annotation tool.

Usage:
    cd annotation_tool
    python server.py          # default port 8080
    python server.py --port 9090
"""

import argparse
import json
import os
import pathlib
import socketserver
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_DIR = pathlib.Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
ANNOTATION_DATA_FILE = DATA_DIR / "annotation_data.json"
ANNOTATIONS_FILE = DATA_DIR / "annotations.json"

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".ico":  "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):

  def log_message(self, fmt, *args):  # suppress default access log spam
    pass

  # ------------------------------------------------------------------ helpers

  def _send_json(self, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _send_file(self, path: pathlib.Path):
    ext = path.suffix.lower()
    mime = MIME.get(ext, "application/octet-stream")
    try:
      content = path.read_bytes()
    except FileNotFoundError:
      self.send_error(404, f"Not found: {path.name}")
      return
    self.send_response(200)
    self.send_header("Content-Type", mime)
    self.send_header("Content-Length", str(len(content)))
    self.end_headers()
    self.wfile.write(content)

  def _read_annotations(self) -> dict:
    if ANNOTATIONS_FILE.exists():
      return json.loads(ANNOTATIONS_FILE.read_text(encoding="utf-8"))
    return {}

  def _write_annotations(self, data: dict):
    tmp = ANNOTATIONS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ANNOTATIONS_FILE)  # atomic on all platforms

  # ------------------------------------------------------------------ GET

  def do_GET(self):
    path = urllib.parse.urlparse(self.path).path

    if path in ("/", "/index.html"):
      self._send_file(STATIC_DIR / "index.html")

    elif path.startswith("/static/"):
      rel = path[len("/static/"):]
      self._send_file(STATIC_DIR / rel)

    elif path == "/api/data":
      if not ANNOTATION_DATA_FILE.exists():
        self._send_json(
            {"error": "annotation_data.json not found — run prepare_data.py first."},
            status=500,
        )
        return
      self._send_json(json.loads(ANNOTATION_DATA_FILE.read_text(encoding="utf-8")))

    elif path == "/api/annotations":
      self._send_json(self._read_annotations())

    elif path == "/api/progress":
      self._handle_progress()

    elif path == "/favicon.ico":
      self.send_response(204)
      self.end_headers()

    else:
      self.send_error(404)

  # ------------------------------------------------------------------ POST

  def do_POST(self):
    path = urllib.parse.urlparse(self.path).path

    if path == "/api/annotate":
      length = int(self.headers.get("Content-Length", 0))
      body = self.rfile.read(length)
      try:
        payload = json.loads(body)
      except json.JSONDecodeError:
        self._send_json({"error": "invalid JSON"}, status=400)
        return
      self._handle_annotate(payload)
    else:
      self.send_error(404)

  # ------------------------------------------------------------------ handlers

  def _handle_annotate(self, payload: dict):
    required = {"run_id", "qid", "page_rank", "sid", "label"}
    missing = required - set(payload)
    if missing:
      self._send_json({"error": f"missing fields: {missing}"}, status=400)
      return

    run_id = str(payload["run_id"])
    qid = str(payload["qid"])
    page_rank = str(payload["page_rank"])
    sid = str(payload["sid"])
    label = bool(payload["label"])

    ann = self._read_annotations()
    ann.setdefault(run_id, {}).setdefault(qid, {}).setdefault(page_rank, {})[sid] = label
    self._write_annotations(ann)

    self._send_json({"ok": True})

  def _handle_progress(self):
    if not ANNOTATION_DATA_FILE.exists():
      self._send_json({})
      return

    data = json.loads(ANNOTATION_DATA_FILE.read_text(encoding="utf-8"))
    ann = self._read_annotations()

    progress: dict[str, dict] = {}
    for group in data["groups"]:
      rid = group["run_id"]
      qid = group["qid"]
      pr = str(group["page_rank"])
      sids = [s["sid"] for s in group["sentences"]]
      done = ann.get(rid, {}).get(qid, {}).get(pr, {})
      n_done = sum(1 for sid in sids if sid in done)

      p = progress.setdefault(rid, {
          "total_groups": 0, "complete_groups": 0,
          "total_sentences": 0, "done_sentences": 0,
      })
      p["total_groups"] += 1
      p["total_sentences"] += len(sids)
      p["done_sentences"] += n_done
      if n_done == len(sids):
        p["complete_groups"] += 1

    self._send_json(progress)


# --------------------------------------------------------------------------- main

def main():
  parser = argparse.ArgumentParser(description="Annotation tool server")
  parser.add_argument("--port", type=int, default=8080)
  args = parser.parse_args()

  DATA_DIR.mkdir(exist_ok=True)

  if not ANNOTATION_DATA_FILE.exists():
    print(f"WARNING: {ANNOTATION_DATA_FILE} not found.")
    print("Run  python prepare_data.py  before annotating.\n")

  print(f"Annotation server ->  http://localhost:{args.port}")
  print("Press Ctrl+C to stop.\n")

  # Allow immediate port reuse after restart
  socketserver.TCPServer.allow_reuse_address = True
  with HTTPServer(("localhost", args.port), Handler) as httpd:
    httpd.serve_forever()


if __name__ == "__main__":
  main()
