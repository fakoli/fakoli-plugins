from pathlib import Path
assert Path("answer.txt").read_text(encoding="utf-8") == "fixed\n"
