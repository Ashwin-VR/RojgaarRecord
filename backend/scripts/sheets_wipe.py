import requests
import json

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbw-uVaK2jGf5ktlrwGZ_wG314oUJ7Xu2NaPihaRXohRONvSCjbJOr8lmvORnJ3cGOnO/exec"

def wipe():
    print("[Sheets Wipe] Triggering end-to-end wipe via Apps Script...")
    payload = {"action": "wipe_all"}
    try:
        res = requests.post(SCRIPT_URL, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
        if res.status_code == 200:
            print("[Sheets Wipe] Successfully instructed Apps Script to wipe all tabs.")
            print("[Sheets Wipe] Wipe webhook pushed to Discord -> DB -> Blockchain.")
        else:
            print(f"[Sheets Wipe Error] {res.text}")
    except Exception as e:
        print(f"[Sheets Wipe Exception] {e}")

if __name__ == "__main__":
    wipe()
