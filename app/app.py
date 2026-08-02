import os, socket
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

PAGE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>AI-with-GitOps</title>
<style>
  body { margin:0; font-family: -apple-system, Segoe UI, Roboto, sans-serif;
         background:#f4f5f7; display:flex; align-items:center; justify-content:center; height:100vh; }
  .card { background:#ffffff; border-radius:16px; padding:32px 36px; width:340px;
          border-top:6px solid {{ accent }}; box-shadow:0 4px 18px rgba(0,0,0,0.08); }
  .header { display:flex; align-items:center; justify-content:space-between; margin-bottom:20px; }
  .title { font-size:18px; font-weight:600; color:#1a1a1a; }
  .badge { background:{{ accent }}; color:#fff; font-size:12px; font-weight:700;
           padding:4px 12px; border-radius:20px; letter-spacing:0.5px; }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  td { padding:8px 0; border-top:1px solid #eee; }
  td.label { color:#888; }
  td.value { text-align:right; font-weight:600; color:#222; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:{{ accent }}; margin-right:6px; }
</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <span class="title">AI-with-GitOps</span>
      <span class="badge">{{ environment|upper }}</span>
    </div>
    <table>
      <tr><td class="label"><span class="dot"></span>Version</td><td class="value">{{ version }}</td></tr>
      <tr><td class="label">Environment</td><td class="value">{{ environment }}</td></tr>
      <tr><td class="label">Node</td><td class="value">{{ node_name }}</td></tr>
      <tr><td class="label">Pod IP</td><td class="value">{{ pod_ip }}</td></tr>
      <tr><td class="label">Hostname</td><td class="value">{{ hostname }}</td></tr>
    </table>
  </div>
</body>
</html>
"""

def collect_info():
    return {
        "application": "AI-with-GitOps",
        "version": os.environ.get("APP_VERSION", "unknown"),
        "environment": os.environ.get("ENVIRONMENT", "unknown"),
        "node_name": os.environ.get("NODE_NAME", "unknown"),
        "pod_ip": os.environ.get("POD_IP", "unknown"),
        "hostname": socket.gethostname(),
    }

@app.route("/")
@app.route("/info")
def info():
    data = collect_info()

    # JSON for scripts/curl -H "Accept: application/json", HTML for browsers
    if request.args.get("format") == "json" or request.headers.get("Accept") == "application/json":
        return jsonify(data)

    env = data["environment"].lower()
    accent = "#2f6feb" if env == "dev" else "#e0393e" if env == "prod" else "#6b7280"
    return render_template_string(PAGE, accent=accent, **data)

@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
