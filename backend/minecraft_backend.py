import threading
from flask import Flask, request, jsonify
from blockchain_ledger import MinecraftLedger
from database_ledger import DatabaseLedger
app = Flask(__name__)

# Threading lock to serialize RCON access and prevent write collisions
rcon_lock = threading.Lock()

# Initialize the ledger client (localhost, port 25575, password rojgaar_secret_2025)
ledger = MinecraftLedger()
db_ledger = DatabaseLedger()

@app.route('/api/blockchain/status', methods=['GET'])
def get_status():
    """Check if the API can connect to the Minecraft ledger server."""
    with rcon_lock:
        connected = ledger.connect()
        if connected:
            ledger.disconnect()
            return jsonify({"status": "ONLINE", "message": "Minecraft RCON ledger is reachable."}), 200
        else:
            return jsonify({"status": "OFFLINE", "message": "Cannot connect to Minecraft server."}), 503

@app.route('/api/blockchain/write', methods=['POST'])
def write_block():
    """Write a new record to a specific blockchain lane (zone)."""
    data = request.get_json()
    if not data or 'zone' not in data or 'record' not in data:
        return jsonify({"error": "Missing parameters. Required: zone (int), record (dict)"}), 400

    zone = int(data['zone'])
    if not (0 <= zone <= 7):
        return jsonify({"error": "Invalid zone. Must be between 0 and 7 inclusive."}), 400
    record = data['record']

    with rcon_lock:
        # Step 1: Validate PIDs in the Database Ledger
        pids_to_check = []
        for key, value in record.items():
            if key in ["wrk", "con", "emp", "sid"] and isinstance(value, str):
                pids_to_check.append(value)
        
        if pids_to_check:
            if not db_ledger.connect():
                return jsonify({"error": "Failed to connect to Database RCON for validation."}), 500
            
            for pid in pids_to_check:
                pid = pid.strip()
                db_zone = -1
                if pid.startswith("WRK"): db_zone = 0
                elif pid.startswith("CON"): db_zone = 1
                elif pid.startswith("EMP"): db_zone = 2
                elif pid.startswith("SID"): db_zone = 3
                
                if db_zone != -1:
                    print(f"[Validation Check] Reading block for pid='{pid}' in db_zone={db_zone}", flush=True)
                    if not db_ledger.read_block(db_zone, pid):
                        print(f"[Validation Check FAIL] pid='{pid}' NOT FOUND in db_zone={db_zone}", flush=True)
                        db_ledger.disconnect()
                        return jsonify({"error": f"Validation failed: {pid} does not exist in State Registry."}), 400
            db_ledger.disconnect()

        # Step 2: Write to Blockchain Ledger
        if not ledger.connect():
            return jsonify({"error": "Failed to connect to Minecraft RCON server."}), 500

        try:
            write_result = ledger.write_block(zone, record)
            ledger.disconnect()
            
            if write_result:
                return jsonify({
                    "status": "SUCCESS",
                    "block_id": write_result["block_id"],
                    "coords": f"{write_result['x']}, {write_result['y']}, {write_result['z']}",
                    "hash": write_result["hash"]
                }), 200
            else:
                return jsonify({"error": "Failed to write block to Minecraft."}), 500
        except Exception as e:
            ledger.disconnect()
            return jsonify({"error": f"Internal ledger error: {str(e)}"}), 500

@app.route('/api/blockchain/verify', methods=['GET'])
def verify_block():
    """Verify the integrity of a specific block on the ledger."""
    zone_val = request.args.get('zone')
    seq_val = request.args.get('seq')

    if zone_val is None or seq_val is None:
        return jsonify({"error": "Missing query parameters. Required: zone (int), seq (int)"}), 400

    zone = int(zone_val)
    if not (0 <= zone <= 7):
        return jsonify({"error": "Invalid zone. Must be between 0 and 7 inclusive."}), 400
    seq = int(seq_val)

    with rcon_lock:
        if not ledger.connect():
            return jsonify({"error": "Failed to connect to Minecraft RCON server."}), 500

        try:
            result = ledger.verify_block(zone, seq)
            ledger.disconnect()
            
            # Translate ledger status to HTTP responses
            if result["status"] == "VALID":
                return jsonify({
                    "status": "VERIFIED",
                    "tampered": False,
                    "coords": f"{result['x']}, {result['y']}, {result['z']}",
                    "hash": result["hash"],
                    "prev_hash": result["prev_hash"],
                    "data": result["data"]
                }), 200
            elif result["status"] == "TEMPERED":
                return jsonify({
                    "status": "TAMPERED",
                    "tampered": True,
                    "error": result["error"],
                    "stored_hash": result["stored_hash"],
                    "recomputed_hash": result["recomputed_hash"]
                }), 400
            else:
                return jsonify({
                    "status": "MISSING",
                    "tampered": False,
                    "error": result.get("error", "Block does not exist.")
                }), 404
        except Exception as e:
            ledger.disconnect()
            return jsonify({"error": f"Verification failed: {str(e)}"}), 500

@app.route('/api/blockchain/audit', methods=['GET'])
def audit_chain():
    """Audit an entire coordinate lane to check link integrity from latest to Genesis."""
    zone_val = request.args.get('zone')
    if zone_val is None:
        return jsonify({"error": "Missing query parameter. Required: zone (int)"}), 400

    zone = int(zone_val)
    if not (0 <= zone <= 7):
        return jsonify({"error": "Invalid zone. Must be between 0 and 7 inclusive."}), 400

    with rcon_lock:
        if not ledger.connect():
            return jsonify({"error": "Failed to connect to Minecraft RCON server."}), 500

        try:
            success, blocks_checked = ledger.verify_chain(zone)
            ledger.disconnect()
            
            if success:
                return jsonify({
                    "status": "SECURE",
                    "blocks_audited": blocks_checked,
                    "message": f"Successfully validated all {blocks_checked} blocks on the chain."
                }), 200
            else:
                return jsonify({
                    "status": "COMPROMISED",
                    "failed_at_seq": blocks_checked,
                    "message": f"Chain validation failed at sequence index {blocks_checked}."
                }), 400
        except Exception as e:
            ledger.disconnect()
            return jsonify({"error": f"Audit failed: {str(e)}"}), 500
@app.route('/api/blockchain/wipe', methods=['POST'])
def wipe_blockchain():
    """Wipe all transaction blocks (shulkers/signs) from all lanes, reverting back to chains."""
    with rcon_lock:
        if not ledger.connect():
            return jsonify({"error": "Failed to connect to Minecraft RCON server."}), 500

        try:
            wiped = ledger.wipe_state()
            ledger.disconnect()
            if wiped:
                return jsonify({
                    "status": "SUCCESS",
                    "message": "Blockchain state wiped successfully."
                }), 200
            else:
                return jsonify({"error": "Failed to wipe blockchain state."}), 500
        except Exception as e:
            ledger.disconnect()
            return jsonify({"error": f"Wipe state failed: {str(e)}"}), 500

@app.route('/api/db/write', methods=['POST'])
def db_write():
    data = request.get_json()
    if not data or 'zone' not in data or 'record_id' not in data or 'record' not in data:
        return jsonify({"error": "Missing parameters."}), 400

    zone = int(data['zone'])
    record_id = data['record_id']
    record = data['record']

    with rcon_lock:
        if not db_ledger.connect():
            return jsonify({"error": "Connection failed"}), 500
        try:
            res = db_ledger.write_block(zone, record_id, record)
            db_ledger.disconnect()
            if res:
                return jsonify({"status": "SUCCESS", "details": res}), 200
            return jsonify({"error": "Write failed"}), 500
        except Exception as e:
            db_ledger.disconnect()
            return jsonify({"error": f"Write failed: {str(e)}"}), 500

@app.route('/api/db/read/<int:zone>/<record_id>', methods=['GET'])
def db_read(zone, record_id):
    with rcon_lock:
        if not db_ledger.connect():
            return jsonify({"error": "Connection failed"}), 500
        try:
            res = db_ledger.read_block(zone, record_id)
            db_ledger.disconnect()
            if res:
                return jsonify({"status": "SUCCESS", "data": res}), 200
            return jsonify({"error": "Record not found"}), 404
        except Exception as e:
            db_ledger.disconnect()
            return jsonify({"error": f"Read failed: {str(e)}"}), 500

@app.route('/api/db/delete', methods=['POST'])
def db_delete():
    data = request.get_json()
    if not data or 'zone' not in data or 'record_id' not in data:
        return jsonify({"error": "Missing parameters."}), 400

    zone = int(data['zone'])
    record_id = data['record_id']

    with rcon_lock:
        if not db_ledger.connect():
            return jsonify({"error": "Connection failed"}), 500
        try:
            res = db_ledger.delete_block(zone, record_id)
            db_ledger.disconnect()
            if res:
                return jsonify({"status": "SUCCESS", "message": f"{record_id} deleted."}), 200
            return jsonify({"error": "Delete failed or record not found"}), 404
        except Exception as e:
            db_ledger.disconnect()
            return jsonify({"error": f"Delete failed: {str(e)}"}), 500

@app.route('/api/db/wipe', methods=['POST'])
def db_wipe():
    with rcon_lock:
        if not db_ledger.connect():
            return jsonify({"error": "Connection failed"}), 500
        try:
            wiped = db_ledger.wipe_state()
            db_ledger.disconnect()
            if wiped:
                return jsonify({"status": "SUCCESS"}), 200
            return jsonify({"error": "Wipe failed"}), 500
        except Exception as e:
            db_ledger.disconnect()
            return jsonify({"error": str(e)}), 500

import time
import sys

def run_sim_thread():
    try:
        import scripts.onboard as onboard
        import importlib
        importlib.reload(onboard)
        onboard.run_simulation()
    except Exception as e:
        print(f"[Daemon Error] Failed to run simulation: {e}")

def run_web_sim_thread():
    try:
        import scripts.sheets_sim as sheets_sim
        import importlib
        importlib.reload(sheets_sim)
        sheets_sim.onboard()
    except Exception as e:
        print(f"[Daemon Error] Failed to run web simulation: {e}")

def run_web_wipe_thread():
    try:
        import scripts.sheets_wipe as sw
        sw.wipe()
    except Exception as e:
        print(f"[Daemon Error] Failed to run web wipe: {e}")

def run_db_sim_thread():
    try:
        import scripts.simulate_db as sim_db
        import importlib
        importlib.reload(sim_db)
        sim_db.simulate()
    except Exception as e:
        print(f"[Daemon Error] Failed to run db simulation: {e}")

def run_db_wipe_thread():
    try:
        import requests
        requests.post('http://127.0.0.1:5000/api/db/wipe')
    except Exception as e:
        print(f"[Daemon Error] Failed to wipe db: {e}")

def trigger_daemon():
    print("[Daemon] Trigger polling started.")
    # Attempt to initialize scoreboards
    with rcon_lock:
        if ledger.connect():
            ledger.send_cmd("scoreboard objectives remove onboard")
            ledger.send_cmd("scoreboard objectives remove wipe")
            ledger.send_cmd("scoreboard objectives remove blockchain")
            ledger.send_cmd("scoreboard objectives remove db")
            
            ledger.send_cmd("scoreboard objectives add onboard_blockchain trigger")
            ledger.send_cmd("scoreboard objectives add wipe_blockchain trigger")
            ledger.send_cmd("scoreboard objectives add web_onboard trigger")
            ledger.send_cmd("scoreboard objectives add web_wipe trigger")
            ledger.send_cmd("scoreboard objectives add tp_blockchain trigger")
            ledger.send_cmd("scoreboard objectives add tp_db trigger")
            ledger.send_cmd("scoreboard objectives add onboard_db trigger")
            ledger.send_cmd("scoreboard objectives add wipe_db trigger")
            ledger.disconnect()
            
    while True:
        time.sleep(2)
        with rcon_lock:
            if not ledger.connect():
                continue
            
            try:
                # Enable triggers for everyone
                for t in ["onboard_blockchain", "wipe_blockchain", "web_onboard", "web_wipe", "tp_blockchain", "tp_db", "onboard_db", "wipe_db"]:
                    ledger.send_cmd(f"scoreboard players enable @a {t}")
                    ledger.send_cmd(f"tag @a[scores={{{t}=1..}}] add do_{t}")
                    ledger.send_cmd(f"scoreboard players set @a[scores={{{t}=1..}}] {t} 0")
                
                # Check tags
                res_tags = ledger.send_cmd("tag @a list")
                
                if "do_tp_blockchain" in res_tags:
                    ledger.send_cmd("tag @a remove do_tp_blockchain")
                    ledger.send_cmd("tp @a 0 -58 0")
                    ledger.send_cmd("title @a actionbar {\"text\":\"Teleported to Blockchain Ledger\",\"color\":\"aqua\"}")
                    
                if "do_tp_db" in res_tags:
                    ledger.send_cmd("tag @a remove do_tp_db")
                    ledger.send_cmd("tp @a -50 -58 -50")
                    ledger.send_cmd("title @a actionbar {\"text\":\"Teleported to Database\",\"color\":\"gold\"}")

                if "do_onboard_blockchain" in res_tags:
                    ledger.send_cmd("tag @a remove do_onboard_blockchain")
                    ledger.send_cmd("title @a actionbar {\"text\":\"Running Onboard Simulation...\",\"color\":\"yellow\"}")
                    threading.Thread(target=run_sim_thread).start()
                    
                if "do_wipe_blockchain" in res_tags:
                    ledger.send_cmd("tag @a remove do_wipe_blockchain")
                    ledger.send_cmd("title @a actionbar {\"text\":\"Wiping Blockchain...\",\"color\":\"red\"}")
                    ledger.wipe_state()
                    
                if "do_web_onboard" in res_tags:
                    ledger.send_cmd("tag @a remove do_web_onboard")
                    ledger.send_cmd("title @a actionbar {\"text\":\"Running Webhook Simulation...\",\"color\":\"green\"}")
                    threading.Thread(target=run_web_sim_thread).start()
                    
                if "do_web_wipe" in res_tags:
                    ledger.send_cmd("tag @a remove do_web_wipe")
                    ledger.send_cmd("title @a actionbar {\"text\":\"Wiping Discord & Blockchain...\",\"color\":\"dark_red\"}")
                    threading.Thread(target=run_web_wipe_thread).start()
                    
                if "do_onboard_db" in res_tags:
                    ledger.send_cmd("tag @a remove do_onboard_db")
                    ledger.send_cmd("title @a actionbar {\"text\":\"Running DB Onboard Simulation...\",\"color\":\"yellow\"}")
                    threading.Thread(target=run_db_sim_thread).start()
                    
                if "do_wipe_db" in res_tags:
                    ledger.send_cmd("tag @a remove do_wipe_db")
                    ledger.send_cmd("tp @a -50 -58 -50")
                    ledger.send_cmd("title @a actionbar {\"text\":\"Wiping Database Registry...\",\"color\":\"red\"}")
                    threading.Thread(target=run_db_wipe_thread).start()

            except Exception as e:
                print(f"[Daemon Error] {e}")
            finally:
                ledger.disconnect()

if __name__ == '__main__':
    # Start the daemon
    daemon_thread = threading.Thread(target=trigger_daemon, daemon=True)
    daemon_thread.start()
    
    print("[API Server] Starting local Blockchain Web API on port 5000...")
    app.run(host='127.0.0.1', port=5000, debug=False)
