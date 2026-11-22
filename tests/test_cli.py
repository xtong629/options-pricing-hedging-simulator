import json

import pytest

from optionlab.cli import main


def test_installed_workflow_and_output_protection(tmp_path):
    out = tmp_path / "result"
    args = ["price", "--output", str(out)]
    main(args)
    first = (out / "analytical.json").read_bytes()
    call = json.loads(first)["call"]
    assert call["price"] == pytest.approx(call["integrated"], abs=1e-10)
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code != 0
    assert first == (out / "analytical.json").read_bytes()


def test_invalid_config_leaves_no_output(tmp_path):
    cfg = tmp_path / "invalid.json"
    cfg.write_text('{"paths": -1}')
    out = tmp_path / "run"
    with pytest.raises(SystemExit):
        main(["all", "--config", str(cfg), "--output", str(out)])
    assert not out.exists()
