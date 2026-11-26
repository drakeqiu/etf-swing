"""Format JSON files passed on the command line."""

import json
import sys
from pathlib import Path

for filename in sys.argv[1:]:
    path = Path(filename)
    content = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(
        json.dumps(content, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
