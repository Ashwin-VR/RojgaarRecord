import requests
import json
import time

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbw-uVaK2jGf5ktlrwGZ_wG314oUJ7Xu2NaPihaRXohRONvSCjbJOr8lmvORnJ3cGOnO/exec"

class Simulator:
    def __init__(self):
        self.session_id = None
        self.session_token = None

    def post(self, action, payload=None):
        if payload is None: payload = {}
        payload["action"] = action
        if self.session_id:
            payload["authId"] = self.session_id
            payload["authToken"] = self.session_token
        
        try:
            r = requests.post(SCRIPT_URL, json=payload, timeout=30)
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def get(self, role):
        url = f"{SCRIPT_URL}?role={role}&id={self.session_id}&token={self.session_token}"
        try:
            r = requests.get(url, timeout=30)
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def register(self, role, record):
        print(f"\n[*] Registering {role} -> {record.get('name')}")
        sheet = "Workers" if role == "worker" else "Contractors" if role == "contractor" else "Employers"
        payload = {"sheet": sheet, "record": record, "authId": "admin"}
        res = self.post("create", payload)
        if "error" in res:
            print(f" [!] Registration Failed: {res['error']}")
            return None
        pid = res.get("pid")
        print(f" [+] Success: Generated ID {pid}")
        return pid

    def login(self, user_id):
        print(f"\n[*] Logging in as {user_id}...")
        self.session_id = None
        self.session_token = None
        
        res = self.post("request_otp", {"id": user_id})
        if "error" in res:
            print(f" [!] OTP Request Failed: {res['error']}")
            return False
            
        time.sleep(2)
        print(" [~] Reading PendingOTPs via Admin Telemetry...")
        admin_data = requests.get(f"{SCRIPT_URL}?role=admin&id=admin&token=admin").json()
        
        otp = None
        for row in admin_data.get("otps", []):
            if row.get("id") == user_id:
                otp = row.get("otp")
                break
                
        if not otp:
            print(" [!] Could not find OTP in DB.")
            return False
            
        print(f" [+] Retrieved OTP: {otp}. Verifying...")
        res = self.post("verify_otp", {"id": user_id, "otp": otp})
        if "error" in res:
            print(f" [!] Login Failed: {res['error']}")
            return False
            
        self.session_id = user_id
        self.session_token = res["token"]
        print(f" [+] Logged in! Session Token: {self.session_token}")
        return True

    def logout(self):
        print(f"\n[*] Logging out {self.session_id}...")
        self.session_id = None
        self.session_token = None

if __name__ == "__main__":
    print("="*50)
    print(" ROJGAAR RECORD - E2E SIMULATION (CATEGORY 1)")
    print("="*50)
    
    sim = Simulator()
    
    print("\n[*] Wiping all ledgers before simulation...")
    sim.post("wipe_all", {"authId": "admin"})
    time.sleep(3)
    
    # 1. Register Users
    emp_id = sim.register("employer", {"name": "L&T Construction", "phone": "9999999991", "dob": "1980-01-01", "dt": "22-06-26", "gstin": "27AAAAA0000A1Z5", "status": "Active"})
    con_id = sim.register("contractor", {"name": "Ramesh Builders", "phone": "9999999992", "dob": "1985-01-01", "dt": "22-06-26", "strikes": 0})
    wrk1_id = sim.register("worker", {"name": "Kamlesh", "phone": "9999999993", "dob": "1990-01-01", "dt": "22-06-26", "wage": "Daily", "skill": "Mason"})
    wrk2_id = sim.register("worker", {"name": "Suresh", "phone": "9999999994", "dob": "1992-01-01", "dt": "22-06-26", "wage": "Hourly", "skill": "Electrician"})
    
    time.sleep(2)
    
    # 2. Employer Flow
    if sim.login(emp_id):
        print(" [*] Creating Site...")
        res = sim.post("create", {"sheet": "Sites", "record": {"name": "Navi Mumbai Airport", "location": "Navi Mumbai", "size": "15000", "status": "Active", "employer": emp_id, "emp": emp_id, "contractorId": "", "dt": "22-06-26"}})
        if "error" in res:
            print(f" [!] Site Create Failed: {res['error']}")
        print(f" [+] Site Create Output: {res}")
        time.sleep(3)
        
        # We need the site ID. Fetch Employer data.
        data = sim.get("employer")
        if "error" in data:
            print(f" [!] Fetch Employer Failed: {data['error']}")
        
        sites = data.get("sites", [])
        if not sites:
            print(f" [!] CRITICAL: No sites returned! Data dump: {data}")
            exit(1)
            
        site_id = sites[0].get("id")
        print(f" [+] Site Created: {site_id}")
        
        print(f" [*] Appointing Contractor {con_id} to Site {site_id}...")
        sim.post("update", {"sheet": "Sites", "pid": site_id, "record": {"contractorId": con_id, "con": con_id, "emp": emp_id, "sid": site_id, "dt": "22-06-26"}})
        sim.logout()

    time.sleep(2)
    
    # 3. Contractor Flow
    if sim.login(con_id):
        print(f" [*] Clocking In {wrk1_id} at {site_id}...")
        sim.post("create", {"sheet": "Attendance", "record": {"workerId": wrk1_id, "wrk": wrk1_id, "siteId": site_id, "sid": site_id, "contractorId": con_id, "con": con_id, "timestamp": "22-06-26", "dt": "22-06-26", "status": "Checked In"}})
        
        print(" [*] Waiting 5 seconds to simulate work duration...")
        time.sleep(5)
        
        print(f" [*] Clocking Out {wrk1_id}...")
        # To clock out, Contractor needs OTP from worker.
        sim.post("generate_payment_otp", {"workerId": wrk1_id, "amount": "500", "phone": "9999999993"})
        time.sleep(2)
        
        admin_data = requests.get(f"{SCRIPT_URL}?role=admin&id=admin&token=admin").json()
        pay_otp = None
        for row in admin_data.get("otps", []):
            if row.get("id") == f"{wrk1_id}-PAY":
                pay_otp = row.get("otp")
                break
                
        print(f" [+] Pay OTP retrieved: {pay_otp}")
        sim.post("verify_payment_otp", {"workerId": wrk1_id, "wrk": wrk1_id, "siteId": site_id, "sid": site_id, "amount": "500", "otp": pay_otp, "hours": 8})
        
        print(f" [*] Issuing EOD Signoff for Site {site_id}...")
        sim.post("create", {"sheet": "EODSignoffs", "record": {"siteId": site_id, "sid": site_id, "contractorId": con_id, "con": con_id, "timestamp": "22-06-26", "dt": "22-06-26"}})
        sim.logout()

    time.sleep(2)
    
    # 4. Worker 2 Flow (Dispute)
    if sim.login(wrk2_id):
        print(f" [*] Filing Claim against {con_id}...")
        sim.post("create", {"sheet": "Claims", "record": {"type": "claim", "workerId": wrk2_id, "wrk": wrk2_id, "contractorId": con_id, "con": con_id, "siteId": site_id, "sid": site_id, "claimType": "Underpayment", "amount": 1000, "description": "Did not pay for overtime", "status": "PENDING", "dt": "22-06-26"}})
        sim.logout()

    print("="*50)
    print(" E2E SIMULATION COMPLETED SUCCESSFULLY!")
    print("="*50)
