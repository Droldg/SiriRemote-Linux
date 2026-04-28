from pathlib import Path


for hci in sorted(Path("/sys/class/bluetooth").glob("hci*")):
    address_path = hci / "address"
    if address_path.exists():
        print(f"{hci.name}: {address_path.read_text().strip()}")
