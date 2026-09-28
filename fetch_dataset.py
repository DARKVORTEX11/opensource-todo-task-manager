from pathlib import Path
from urllib.request import urlopen

URL = "https://raw.githubusercontent.com/microsoft/MS-LaTTE/main/MS-LaTTE.json"
DEST = Path(__file__).resolve().parent / "data" / "MS-LaTTE.json"

def main():
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print("Downloading official MS-LaTTE dataset...")
    with urlopen(URL, timeout=60) as response:
        content = response.read()
    DEST.write_bytes(content)
    print(f"Saved {len(content):,} bytes to {DEST}")

if __name__ == "__main__":
    main()
