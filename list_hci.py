from pathlib import Path
import subprocess


found = False

for hci in sorted(Path("/sys/class/bluetooth").glob("hci*")):
    address_path = hci / "address"
    if address_path.exists():
        found = True
        print(f"{hci.name}: {address_path.read_text().strip()}")

if found:
    raise SystemExit

for command in (["hciconfig"], ["bluetoothctl", "list"]):
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        continue

    if result.stdout.strip():
        print(f"$ {' '.join(command)}")
        print(result.stdout.rstrip())
