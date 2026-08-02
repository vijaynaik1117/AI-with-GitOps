import os, socket
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
@app.route("/info")
def info():
    return jsonify({
        "application": "AI-with-GitOps",
        "version": os.environ.get("APP_VERSION", "unknown"),
        "environment": os.environ.get("ENVIRONMENT", "unknown"),
        "node_name": os.environ.get("NODE_NAME", "unknown"),
        "pod_ip": os.environ.get("POD_IP", "unknown"),
        "hostname": socket.gethostname()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
