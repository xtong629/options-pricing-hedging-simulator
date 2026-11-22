import json
import sys
from pathlib import Path

from optionlab.risk_study import run

if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(run(), indent=2) + "\n")
