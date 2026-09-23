"""Small deterministic load generator: python scripts/load_test.py --trips 10000."""
import argparse
import urllib.request
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trips", type=int, default=1000)
    parser.add_argument("--token", required=True)
    args = parser.parse_args()
    for number in range(args.trips):
        request = urllib.request.Request("http://localhost:8000/api/trips", method="POST", data=json.dumps({"distance_km": 10, "trip_type": "NORMAL", "idempotency_key": f"load-{number}"}).encode(), headers={"Content-Type": "application/json", "Authorization": f"Bearer {args.token}"})
        with urllib.request.urlopen(request) as response:
            response.read()
    print(f"Submitted {args.trips} deterministic trips")


if __name__ == "__main__":
    main()
