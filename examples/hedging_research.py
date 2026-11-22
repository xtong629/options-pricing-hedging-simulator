import json
from pathlib import Path

from optionlab.hedging_study import run

if __name__ == "__main__":
    output = Path("/tmp")
    (output / "phase3_hedging_summary.json").write_text(
        json.dumps(run(output), indent=2) + "\n"
    )
