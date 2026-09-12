from pathlib import Path
assert Path("status.txt").read_text(encoding="utf-8") == "verified\n"
