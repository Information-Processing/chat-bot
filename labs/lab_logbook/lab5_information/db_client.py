import requests
IP = "13.60.40.103"

# Testing Task i: Get 3 artists
print("--- Task i: Artists (Limit 3) ---")
r1 = requests.get(f"http://{IP}:5000/artists", params={"limit": 3})
print(r1.json())

# Testing Task ii: Get albums for AC/DC
print("\n--- Task ii: Albums for AC/DC ---")
r2 = requests.get(f"http://{IP}:5000/albums", params={"artist": "AC/DC"})
print(r2.json())
