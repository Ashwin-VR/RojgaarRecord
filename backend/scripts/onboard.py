import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from blockchain_ledger import MinecraftLedger

def run_simulation():
    ledger = MinecraftLedger()
    if not ledger.connect():
        print("Failed to connect.")
        return

    def write(zone, payload):
        ledger.write_block(zone, payload)
        time.sleep(1) # delay for animation

    print("Starting Holistic Blockchain Transactions...")

    print("1. Site Registrations (Zone 2)...")
    write(2, {
        "emp": "EMP-001",
        "sid": "SID-001",
        "dt": "21-06-26"
    })
    write(2, {
        "emp": "EMP-002",
        "sid": "SID-002",
        "dt": "21-06-26"
    })

    print("2. Contract Awards (Zone 3)...")
    write(3, {
        "emp": "EMP-001",
        "con": "CON-001",
        "sid": "SID-001",
        "dt": "21-06-26"
    })
    write(3, {
        "emp": "EMP-002",
        "con": "CON-002",
        "sid": "SID-002",
        "dt": "21-06-26"
    })

    print("3. Attendance In (Zone 0)...")
    write(0, {
        "wrk": "WRK-001",
        "con": "CON-001",
        "sid": "SID-001",
        "dt": "22-06-26"
    })
    write(0, {
        "wrk": "WRK-002",
        "con": "CON-001",
        "sid": "SID-001",
        "dt": "22-06-26"
    })
    write(0, {
        "wrk": "WRK-003",
        "con": "CON-002",
        "sid": "SID-002",
        "dt": "22-06-26"
    })

    print("4. Attendance Out (Zone 1)...")
    write(1, {
        "wrk": "WRK-001",
        "sid": "SID-001",
        "hours": 8,
        "dt": "22-06-26"
    })
    write(1, {
        "wrk": "WRK-003",
        "sid": "SID-002",
        "hours": 9,
        "dt": "22-06-26"
    })

    print("5. EOD Sign-offs (Zone 7)...")
    write(7, {
        "con": "CON-001",
        "sid": "SID-001",
        "dt": "22-06-26"
    })
    write(7, {
        "con": "CON-002",
        "sid": "SID-002",
        "dt": "22-06-26"
    })

    print("6. Payment Transactions (Zone 6)...")
    write(6, {
        "type": "payment",
        "wrk": "WRK-001",
        "sid": "SID-001",
        "amount": 500,
        "dt": "26-06-26"
    })
    write(6, {
        "type": "payment",
        "wrk": "WRK-003",
        "sid": "SID-002",
        "amount": 600,
        "dt": "26-06-26"
    })

    print("7. Claim Submissions (Zone 4)...")
    write(4, {
        "type": "claim",
        "wrk": "WRK-002",
        "con": "CON-001",
        "status": "PENDING",
        "dt": "27-06-26"
    })

    print("8. Claim Resolutions (Zone 5)...")
    write(5, {
        "claim_id": "CLAIM_SUB-0",
        "action": "RESOLVED",
        "resp_by": "CON-001",
        "dt": "28-06-26"
    })

    ledger.disconnect()
    print("\nBlockchain Transaction Simulation Done!")

if __name__ == '__main__':
    run_simulation()
