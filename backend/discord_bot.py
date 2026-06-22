import discord
from discord.ext import commands
import requests
import json
import re
import datetime
import threading

TOKEN = ""
BLOCKCHAIN_API_URL = "http://127.0.0.1:5000/api/blockchain/write"
DB_API_URL = "http://127.0.0.1:5000/api/db"
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbw-uVaK2jGf5ktlrwGZ_wG314oUJ7Xu2NaPihaRXohRONvSCjbJOr8lmvORnJ3cGOnO/exec"

def clean_blockchain_record(zone, record):
    if zone == 0: # ATTENDANCE_IN: wrk, con, sid, dt
        return {
            "wrk": (record.get("wrk") or record.get("workerId") or "").strip(),
            "con": (record.get("con") or record.get("contractorId") or "").strip(),
            "sid": (record.get("sid") or record.get("siteId") or "").strip(),
            "dt": (record.get("dt") or "").strip()
        }
    elif zone == 1: # ATTENDANCE_OUT: wrk, sid, hours, dt
        hours_val = record.get("hours")
        try:
            hours = int(hours_val)
        except:
            hours = 8
        return {
            "wrk": (record.get("wrk") or record.get("workerId") or "").strip(),
            "sid": (record.get("sid") or record.get("siteId") or "").strip(),
            "hours": hours,
            "dt": (record.get("dt") or "").strip()
        }
    elif zone == 2: # SITE_REGISTRATION: emp, sid, dt
        return {
            "emp": (record.get("emp") or record.get("employer") or "").strip(),
            "sid": (record.get("sid") or record.get("id") or "").strip(),
            "dt": (record.get("dt") or "").strip()
        }
    elif zone == 3: # CONTRACT_AWARD: emp, con, sid, dt
        return {
            "emp": (record.get("emp") or record.get("employer") or "").strip(),
            "con": (record.get("con") or record.get("contractorId") or "").strip(),
            "sid": (record.get("sid") or record.get("id") or "").strip(),
            "dt": (record.get("dt") or "").strip()
        }
    elif zone == 4: # CLAIM_SUBMISSION: type, wrk, con, status, dt
        return {
            "type": "claim",
            "wrk": (record.get("wrk") or record.get("workerId") or "").strip(),
            "con": (record.get("con") or record.get("contractorId") or "").strip(),
            "status": (record.get("status") or "PENDING").strip(),
            "dt": (record.get("dt") or "").strip()
        }
    elif zone == 5: # CLAIM_RESOLUTION: claim_id, action, resp_by, dt
        return {
            "claim_id": (record.get("claim_id") or record.get("id") or "").strip(),
            "action": (record.get("action") or "RESOLVED").strip(),
            "resp_by": (record.get("resp_by") or record.get("con") or "").strip(),
            "dt": (record.get("dt") or "").strip()
        }
    elif zone == 6: # PAYMENT_TRANSACTION: type, wrk, sid, amount, dt
        amount_val = record.get("amount")
        try:
            amount = int(amount_val)
        except:
            amount = 0
        return {
            "type": "payment",
            "wrk": (record.get("wrk") or record.get("workerId") or "").strip(),
            "sid": (record.get("sid") or record.get("siteId") or "").strip(),
            "amount": amount,
            "dt": (record.get("dt") or "").strip()
        }
    elif zone == 7: # EOD_SIGNOFF: con, sid, dt
        return {
            "con": (record.get("con") or record.get("contractorId") or "").strip(),
            "sid": (record.get("sid") or record.get("siteId") or "").strip(),
            "dt": (record.get("dt") or "").strip()
        }
    return record

def reconcile_db():
    print("[Sync] Starting database reconciliation with Google Sheets...", flush=True)
    try:
        res = requests.get(f"{SCRIPT_URL}?role=admin", timeout=15)
        if res.status_code != 200:
            print(f"[Sync] Failed to fetch Google Sheet registry: {res.text}", flush=True)
            return
        
        data = res.json()
        registries = {
            0: data.get("workers", []),
            1: data.get("contractors", []),
            2: data.get("employers", []),
            3: data.get("sites", [])
        }
        
        for zone, records in registries.items():
            for record in records:
                pid = record.get("id")
                if not pid:
                    continue
                
                # Check if it exists in Minecraft DB
                read_res = requests.get(f"{DB_API_URL}/read/{zone}/{pid}", timeout=5)
                if read_res.status_code == 404:
                    print(f"[Sync] {pid} is missing from Minecraft DB. Writing...", flush=True)
                    # Write it!
                    write_payload = {"zone": zone, "record_id": pid, "record": record}
                    write_res = requests.post(f"{DB_API_URL}/write", json=write_payload, timeout=5)
                    if write_res.status_code == 200:
                        print(f"[Sync] Successfully wrote {pid} to Minecraft DB.", flush=True)
                    else:
                        print(f"[Sync] Failed to write {pid} to Minecraft DB: {write_res.text}", flush=True)
                elif read_res.status_code == 200:
                    print(f"[Sync] {pid} exists in Minecraft DB.", flush=True)
        print("[Sync] Reconciliation completed.", flush=True)
    except Exception as e:
        print(f"[Sync Error] Reconciliation failed: {e}", flush=True)

class RojgaarBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.blockchain_zone_map = {
            'tx-attendance-in': 0,
            'tx-attendance-out': 1,
            'tx-site-registrations': 2,
            'tx-contract-awards': 3,
            'tx-claims': 4,
            'tx-claim-resolutions': 5,
            'tx-payments': 6,
            'tx-eod-signoffs': 7
        }

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        print("Ready to process DB Slash Commands & Blockchain JSONs...")
        threading.Thread(target=reconcile_db, daemon=True).start()

    async def on_message(self, message):
        print(f"[DEBUG] Received message in #{message.channel}: {message.content} | Embeds: {len(message.embeds)}", flush=True)
        if message.author == self.user:
            return

        # Passive JSON listener for Blockchain
        if message.channel.name in self.blockchain_zone_map:
            zone = self.blockchain_zone_map[message.channel.name]
            content = message.content
            json_str = None
            if content:
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if match:
                    json_str = match.group(1)
                else:
                    match = re.search(r'(\{.*\})', content, re.DOTALL)
                    if match:
                        json_str = match.group(1)
            
            if not json_str and message.embeds:
                embed_desc = message.embeds[0].description
                if embed_desc:
                    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', embed_desc, re.DOTALL)
                    if match:
                        json_str = match.group(1)
                        print(f"[DEBUG Blockchain] Found JSON in embed: {json_str}", flush=True)
            
            if not json_str:
                return

            try:
                payload = json.loads(json_str)
            except json.JSONDecodeError:
                return

            record = payload.get("record", {})

            # Special hook for Site Registrations:
            # We must write to DB Zone 3 first!
            if message.channel.name == 'tx-site-registrations':
                site_id = (record.get("sid") or record.get("id") or payload.get("pid") or "").strip()
                emp_id = (record.get("emp") or record.get("employer") or "").strip()
                if site_id:
                    db_record = {
                        "id": site_id,
                        "name": record.get("name") or record.get("siteName") or "Unnamed Site",
                        "location": record.get("location", "N/A"),
                        "size": record.get("size", "N/A"),
                        "status": record.get("status", "ACTIVE"),
                        "employer": emp_id or "N/A",
                        "dt": record.get("dt") or datetime.datetime.now().strftime("%d-%m-%y")
                    }
                    db_payload = {
                        "zone": 3,
                        "record_id": site_id,
                        "record": db_record
                    }
                    print(f"[Bot] Pre-writing site {site_id} to Database Ledger (Zone 3)...", flush=True)
                    try:
                        db_res = requests.post(f"{DB_API_URL}/write", json=db_payload, timeout=5)
                        if db_res.status_code == 200:
                            print(f"[Bot] Successfully pre-wrote site {site_id} to Database Ledger.", flush=True)
                        else:
                            print(f"[Bot] Failed to pre-write site {site_id} to Database Ledger: {db_res.text}", flush=True)
                    except Exception as e:
                        print(f"[Bot Error] Failed to pre-write site to DB: {e}", flush=True)

            # Clean/strip record to conform to exact blockchain ledger schema
            record = clean_blockchain_record(zone, record)
            data = {"zone": zone, "record": record}
            try:
                res = requests.post(BLOCKCHAIN_API_URL, json=data, timeout=5)
                if res.status_code == 200:
                    await message.add_reaction('✅')
                else:
                    await message.add_reaction('❌')
            except Exception as e:
                await message.add_reaction('❌')

        # Passive JSON listener for DB CRUD Webhooks
        elif message.channel.name == 'db-crud':
            content = message.content
            json_str = None
            
            # 1. Try to parse from message content
            if content:
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if match:
                    json_str = match.group(1)
                else:
                    match = re.search(r'(\{.*\})', content, re.DOTALL)
                    if match:
                        json_str = match.group(1)
            
            # 2. Try to parse from Embeds
            if not json_str and message.embeds:
                embed_desc = message.embeds[0].description
                print(f"[DEBUG db-crud] Embed description: {embed_desc}", flush=True)
                if embed_desc:
                    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', embed_desc, re.DOTALL)
                    if match:
                        json_str = match.group(1)
                        print(f"[DEBUG db-crud] Matched json_str: {json_str}", flush=True)
            
            if not json_str:
                print("[DEBUG db-crud] No json_str found.", flush=True)
                return
            
            try:
                payload = json.loads(json_str)
                print(f"[DEBUG db-crud] Payload loaded: {payload}", flush=True)
            except json.JSONDecodeError:
                print("Failed to decode JSON from db-crud.", flush=True)
                return
            
            action = payload.get("action")
            pid = payload.get("pid")
            record = payload.get("record", {})

            # End-to-End Wipe Listener
            if action == "wipe_all":
                print("[Bot] Executing WIPE_ALL from web.", flush=True)
                try:
                    res_db = requests.post(f"{DB_API_URL}/wipe", timeout=5)
                    res_bc = requests.post("http://127.0.0.1:5000/api/blockchain/wipe", timeout=30)
                    if res_db.status_code == 200 and res_bc.status_code == 200:
                        await message.add_reaction('✅')
                    else:
                        await message.add_reaction('❌')
                except Exception as e:
                    print(f"[Bot] WIPE_ALL failed: {e}", flush=True)
                    await message.add_reaction('❌')
                return

            # Ignore non-DB operations like session management
            if not action or not pid: return

            zone = -1
            if pid.startswith("WRK"): zone = 0
            elif pid.startswith("CON"): zone = 1
            elif pid.startswith("EMP"): zone = 2
            elif pid.startswith("SID"): zone = 3
            
            if zone == -1: return

            try:
                if action in ["create", "update"]:
                    data = {"zone": zone, "record_id": pid, "record": record}
                    res = requests.post(f"{DB_API_URL}/write", json=data, timeout=5)
                elif action == "delete":
                    data = {"zone": zone, "record_id": pid}
                    res = requests.post(f"{DB_API_URL}/delete", json=data, timeout=5)
                else:
                    return

                if res.status_code == 200:
                    print(f"[Bot] DB write SUCCESS for {pid} (zone={zone}).", flush=True)
                    await message.add_reaction('✅')
                else:
                    print(f"[Bot] DB write FAILED for {pid}: HTTP {res.status_code} — {res.text}", flush=True)
                    await message.add_reaction('❌')
            except Exception as e:
                print(f"[Bot] DB write EXCEPTION for {pid}: {e}", flush=True)
                await message.add_reaction('❌')

bot = RojgaarBot()

@bot.tree.command(name="onboard", description="Onboard a new worker, contractor, employer, or site.")
async def onboard(interaction: discord.Interaction, table: str, name: str, phone_or_location: str, dob_or_size: str, wage_or_status: str, extra: str):
    await interaction.response.defer()
    table = table.lower()
    dt = datetime.datetime.now().strftime("%d-%m-%y")
    seq = str(int(datetime.datetime.now().timestamp()))[-4:]
    
    if table == "worker":
        zone = 0
        pid = f"WRK-{seq}"
        payload = {"id": pid, "name": name, "phone": phone_or_location, "dob": dob_or_size, "wage": wage_or_status, "skill": extra, "dt": dt}
    elif table == "contractor":
        zone = 1
        pid = f"CON-{seq}"
        payload = {"id": pid, "name": name, "phone": phone_or_location, "dob": dob_or_size, "strikes": wage_or_status, "dt": dt}
    elif table == "employer":
        zone = 2
        pid = f"EMP-{seq}"
        payload = {"id": pid, "name": name, "phone": phone_or_location, "dob": dob_or_size, "gstin": wage_or_status, "dt": dt}
    elif table == "site":
        zone = 3
        pid = f"SID-{seq}"
        payload = {"id": pid, "name": name, "location": phone_or_location, "size": dob_or_size, "status": wage_or_status, "employer": extra, "dt": dt}
    else:
        await interaction.followup.send("Invalid table. Choose worker, contractor, employer, or site.")
        return

    data = {"zone": zone, "record_id": pid, "record": payload}
    try:
        res = requests.post(f"{DB_API_URL}/write", json=data)
        if res.status_code == 200:
            await interaction.followup.send(f"✅ Created {table.title()} with PID: **{pid}**\nPayload: {payload}")
        else:
            await interaction.followup.send(f"❌ Failed to write to DB: {res.text}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="update", description="Update an existing record (by PID). Provide raw JSON dict.")
async def update_record(interaction: discord.Interaction, pid: str, json_payload: str):
    await interaction.response.defer()
    zone = -1
    if pid.startswith("WRK"): zone = 0
    elif pid.startswith("CON"): zone = 1
    elif pid.startswith("EMP"): zone = 2
    elif pid.startswith("SID"): zone = 3
    
    if zone == -1:
        await interaction.followup.send("❌ Invalid PID prefix.")
        return

    try:
        payload = json.loads(json_payload)
        payload['id'] = pid
    except:
        await interaction.followup.send("❌ Invalid JSON format.")
        return

    data = {"zone": zone, "record_id": pid, "record": payload}
    res = requests.post(f"{DB_API_URL}/write", json=data)
    if res.status_code == 200:
        await interaction.followup.send(f"✅ Updated PID: **{pid}**")
    else:
        await interaction.followup.send(f"❌ Failed to update: {res.text}")

@bot.tree.command(name="lookup", description="Read a record from the Database by PID.")
async def lookup(interaction: discord.Interaction, pid: str):
    await interaction.response.defer()
    zone = -1
    if pid.startswith("WRK"): zone = 0
    elif pid.startswith("CON"): zone = 1
    elif pid.startswith("EMP"): zone = 2
    elif pid.startswith("SID"): zone = 3

    if zone == -1:
        await interaction.followup.send("❌ Invalid PID prefix.")
        return

    res = requests.get(f"{DB_API_URL}/read/{zone}/{pid}")
    if res.status_code == 200:
        data = res.json().get("data", {})
        await interaction.followup.send(f"🔍 **Lookup Results for {pid}**\n```json\n{json.dumps(data, indent=2)}\n```")
    else:
        await interaction.followup.send(f"❌ Record not found or error: {res.text}")

@bot.tree.command(name="delete", description="Delete a record from the Database by PID.")
async def delete_record(interaction: discord.Interaction, pid: str):
    await interaction.response.defer()
    zone = -1
    if pid.startswith("WRK"): zone = 0
    elif pid.startswith("CON"): zone = 1
    elif pid.startswith("EMP"): zone = 2
    elif pid.startswith("SID"): zone = 3

    if zone == -1:
        await interaction.followup.send("❌ Invalid PID prefix.")
        return

    data = {"zone": zone, "record_id": pid}
    res = requests.post(f"{DB_API_URL}/delete", json=data)
    if res.status_code == 200:
        await interaction.followup.send(f"🗑️ Deleted PID: **{pid}**")
    else:
        await interaction.followup.send(f"❌ Failed to delete: {res.text}")

@bot.tree.command(name="sessions", description="List all active sessions.")
async def sessions(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        res = requests.get(f"{SCRIPT_URL}?role=admin", timeout=10)
        if res.status_code == 200:
            data = res.json()
            active_sessions = data.get("sessions", [])
            if not active_sessions:
                await interaction.followup.send("No active sessions currently.")
                return
            msg = "👁️ **Active Sessions**\n"
            for s in active_sessions:
                msg += f"- ID: **{s.get('id')}** | Token: `{s.get('session_token')}` | Last Active: *{s.get('last_active_time')}*\n"
            await interaction.followup.send(msg)
        else:
            await interaction.followup.send(f"❌ Failed to fetch sessions: {res.text}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="killsession", description="Force terminate a session by User ID.")
async def killsession(interaction: discord.Interaction, id: str):
    await interaction.response.defer()
    payload = {
        "action": "logout",
        "id": id,
        "token": "FORCE"
    }
    try:
        res = requests.post(SCRIPT_URL, json=payload, timeout=10)
        if res.status_code == 200 and res.json().get("ok"):
            await interaction.followup.send(f"🗑️ Session for **{id}** terminated successfully.")
        else:
            await interaction.followup.send(f"❌ Failed to terminate session: {res.text}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="sync", description="Sync and reconcile Google Sheet registries with Minecraft DB.")
async def sync_registry(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        t = threading.Thread(target=reconcile_db)
        t.start()
        t.join(5)
        if t.is_alive():
            await interaction.followup.send("⏳ Database reconciliation started in background. Please check bot logs / Minecraft DB shortly.")
        else:
            await interaction.followup.send("✅ Database reconciliation complete! Check Minecraft Lecterns/signs to verify.")
    except Exception as e:
        await interaction.followup.send(f"❌ Synchronization failed: {str(e)}")

if __name__ == '__main__':
    bot.run(TOKEN)
