import requests
import time

DB_API_URL = "http://127.0.0.1:5000/api/db/write"

def simulate():
    print("Starting DB Onboarding (Source of Truth)...")
    dt = "21-06-26"
    
    def post(zone, pid, record):
        data = {"zone": zone, "record_id": pid, "record": record}
        try:
            res = requests.post(DB_API_URL, json=data, timeout=5)
            if res.status_code != 200:
                print(f"Error {pid}: {res.text}")
        except Exception as e:
            print(f"Exception {pid}: {e}")
        time.sleep(0.5)

    print("1. Registering Workers (Zone 0)...")
    post(0, "WRK-001", {"id": "WRK-001", "name": "Kamlesh", "phone": "7777777777", "dob": "10-10-95", "dt": dt, "skill": "Mason", "wage": "Daily"})
    post(0, "WRK-002", {"id": "WRK-002", "name": "Raju", "phone": "6666666666", "dob": "11-11-98", "dt": dt, "skill": "Helper", "wage": "Weekly"})
    post(0, "WRK-003", {"id": "WRK-003", "name": "Babu", "phone": "5555555555", "dob": "12-12-92", "dt": dt, "skill": "Carpenter", "wage": "Daily"})

    print("2. Registering Contractors (Zone 1)...")
    post(1, "CON-001", {"id": "CON-001", "name": "Ramesh Building Co", "phone": "8888888888", "dob": "12-05-85", "dt": dt, "strikes": 0})
    post(1, "CON-002", {"id": "CON-002", "name": "Suresh Infra", "phone": "8888888887", "dob": "22-08-88", "dt": dt, "strikes": 0})
    
    print("3. Registering Employers (Zone 2)...")
    post(2, "EMP-001", {"id": "EMP-001", "name": "RojgaarRecord Corp", "phone": "9999999999", "dob": "01-01-90", "dt": dt, "gstin": "27AAAAA0000A1Z5"})
    post(2, "EMP-002", {"id": "EMP-002", "name": "Builder Group LLC", "phone": "9999999998", "dob": "01-01-91", "dt": dt, "gstin": "27BBBBB0000A1Z5"})
    
    print("4. Registering Sites (Zone 3)...")
    post(3, "SID-001", {"id": "SID-001", "name": "Phase 1 Housing", "location": "Mumbai", "size": "1000", "status": "Active", "employer": "EMP-001", "dt": dt})
    post(3, "SID-002", {"id": "SID-002", "name": "Phase 2 Commercial", "location": "Pune", "size": "5000", "status": "Active", "employer": "EMP-002", "dt": dt})

    print("\nDB Onboarding Done!")

if __name__ == '__main__':
    simulate()
