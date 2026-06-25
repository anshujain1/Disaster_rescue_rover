"""
Rover M — Dashboard Backend (polling version, no eventlet issues)
Run: python app.py
"""
import json, threading, time, serial
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

SERIAL_PORT = "COM6"
BAUD_RATE   = 115200
WEBCAM_URL  = ""

app = Flask(__name__)
CORS(app)

rover_state = {
    "us":999, "ir":[0,0,0], "pir":0,
    "x":0.0, "y":0.0, "heading":0.0,
    "mode":"auto", "connected":False,
}
victims  = []
ser      = None
ser_lock = threading.Lock()


def serial_thread():
    global ser
    while True:
        try:
            print(f"[SERIAL] Connecting {SERIAL_PORT}...")
            s = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            s.reset_input_buffer()
            with ser_lock: ser = s
            rover_state["connected"] = True
            print(f"[SERIAL] Connected on {SERIAL_PORT}")

            while True:
                raw = s.readline().decode("utf-8", errors="ignore").strip()
                if not raw: continue
                try: pkt = json.loads(raw)
                except: continue
                if pkt.get("t") != "s": continue

                prev_pir = rover_state["pir"]
                rover_state.update({
                    "us":      pkt.get("us", 999),
                    "ir":      pkt.get("ir", [0,0,0]),
                    "pir":     pkt.get("pir", 0),
                    "x":       round(float(pkt.get("x", 0)), 3),
                    "y":       round(float(pkt.get("y", 0)), 3),
                    "heading": round(float(pkt.get("heading", 0)), 1),
                    "mode":    pkt.get("mode", "auto"),
                    "connected": True,
                })
                if rover_state["pir"] == 1 and prev_pir == 0:
                    v = {"x":rover_state["x"],"y":rover_state["y"],
                         "t":int(time.time()),"id":len(victims)+1}
                    victims.append(v)
                    print(f"[VICTIM] #{v['id']} at {v['x']:.2f},{v['y']:.2f}")

        except Exception as e:
            print(f"[SERIAL] Error: {e}")
        finally:
            with ser_lock: ser = None
            rover_state["connected"] = False
            print("[SERIAL] Disconnected — retrying in 3s")
            time.sleep(3)

def send_cmd(cmd):
    with ser_lock: s = ser
    if not s or not s.is_open:
        print(f"[CMD] Not connected, dropped: {cmd}"); return
    try:
        s.write((json.dumps({"cmd":cmd})+"\n").encode())
        s.flush()
        print(f"[CMD] Sent: {cmd}")
    except Exception as e:
        print(f"[CMD] Error: {e}")

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/state")
def api_state():
    return jsonify({**rover_state, "victims": victims, "webcam_url": WEBCAM_URL})

@app.route("/api/cmd", methods=["POST"])
def api_cmd():
    cmd = request.json.get("cmd","").upper()
    if cmd in ("F","B","L","R","S","M"):
        send_cmd(cmd)
        return jsonify({"ok": True, "cmd": cmd})
    return jsonify({"ok": False}), 400

@app.route("/api/clear_victims", methods=["POST"])
def clear_victims():
    victims.clear(); return jsonify({"ok":True})

@app.route("/api/reset_odometry", methods=["POST"])
def reset_odo():
    rover_state.update({"x":0.0,"y":0.0,"heading":0.0})
    return jsonify({"ok":True})

@app.route("/api/set_webcam", methods=["POST"])
def set_webcam():
    global WEBCAM_URL
    WEBCAM_URL = request.json.get("url","").strip()
    return jsonify({"ok":True})

if __name__ == "__main__":
    t = threading.Thread(target=serial_thread, daemon=True)
    t.start()
    print("="*45)
    print(f"  Dashboard → http://localhost:5000")
    print("="*45)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
