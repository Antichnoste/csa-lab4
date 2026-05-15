import os
import tempfile
import contextlib
import io
import pytest
import sys

from translator import main as translator_main
from machine import run_simulation

@pytest.mark.golden_test("test/*.yml")
def test_pipeline(golden, monkeypatch):
    algo_name = os.path.splitext(os.path.basename(golden.path))[0]
    source_path = os.path.join("lisp", algo_name, f"{algo_name}.lisp")
    
    if not os.path.exists(source_path):
        pytest.fail(f"Исходный файл не найден по пути: {source_path}")

    with open(source_path, "r", encoding="utf-8") as f:
        source_code = f.read()

    in_stdin = golden.get("in_stdin", "")

    with tempfile.TemporaryDirectory() as tmpdirname:
        target_bin = os.path.join(tmpdirname, "target.bin")
        target_asm = os.path.join(tmpdirname, "target.asm")
        input_txt = os.path.join(tmpdirname, "input.txt")
        
        with open(input_txt, "w", encoding="utf-8") as f:
            f.write(in_stdin)

        with contextlib.redirect_stdout(io.StringIO()):
            monkeypatch.setattr(sys, "argv", ["translator.py", source_path, target_bin, target_asm])
            translator_main()
            
        with open(target_asm, "r", encoding="utf-8") as f:
            asm_code = f.read()

        machine_stdout = io.StringIO()
        with contextlib.redirect_stdout(machine_stdout):
            run_simulation(target_bin, input_txt, trace=True, micro_trace=False)

        raw_log = machine_stdout.getvalue()
        lines = raw_log.splitlines()
        
        if len(lines) > 200:
            truncated_log = "\n".join(
                lines[:100] + 
                ["", f"... [ Скрыто {len(lines) - 200} строк лога ] ...", ""] + 
                lines[-100:]
            ) + "\n"
        else:
            truncated_log = raw_log

    assert source_code == golden.out["source_code"]
    assert asm_code == golden.out["out_code"]
    assert truncated_log == golden.out["out_log"]