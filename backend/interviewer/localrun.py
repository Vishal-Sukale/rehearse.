"""LOCAL PRACTICE ONLY: compile and run C, C++ and Java with compilers installed on THIS computer.
There is no sandbox, so this is for running your own practice code on your own machine. The server refuses to use
it when APP_ENV=production. For anything shared, use a sandboxed runner (see piston.py)."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

COMPILE_TIMEOUT = 30
RUN_TIMEOUT = 3
TOOLS = {"c": ("gcc",), "cpp": ("g++",), "java": ("javac", "java")}
SOURCE = {"c": "main.c", "cpp": "main.cpp", "java": "Main.java"}


def available(language: str) -> bool:
    return all(shutil.which(tool) for tool in TOOLS[language])


def _clip(text: str | None, size: int) -> str:
    return (text or "")[:size]


def run_many(language: str, code: str, inputs: list[str]) -> dict:
    """Same result shape as the sandboxed runner: {"compile_error": str | None, "results": [...]}."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / SOURCE[language]).write_text(code, encoding="utf-8")
        exe = str(folder / ("main.exe" if os.name == "nt" else "main"))
        if language == "c":
            compile_cmd, run_cmd = ["gcc", SOURCE[language], "-O2", "-o", exe, "-lm"], [exe]
        elif language == "cpp":
            compile_cmd, run_cmd = ["g++", "-std=c++17", SOURCE[language], "-O2", "-o", exe], [exe]
        else:
            compile_cmd, run_cmd = ["javac", SOURCE[language]], ["java", "-Xmx256m", "-cp", str(folder), "Main"]
        try:
            built = subprocess.run(compile_cmd, cwd=folder, capture_output=True, text=True, timeout=COMPILE_TIMEOUT)
        except subprocess.TimeoutExpired:
            return {"compile_error": "Compilation took too long.", "results": []}
        if built.returncode != 0:
            return {"compile_error": _clip(built.stderr or built.stdout, 2000) or "Compilation failed", "results": []}

        results = []
        for text in inputs:
            try:
                done = subprocess.run(run_cmd, cwd=folder, input=text, capture_output=True, text=True, timeout=RUN_TIMEOUT)
                results.append({"stdout": _clip(done.stdout, 5000), "stderr": _clip(done.stderr, 1000),
                                "exit_code": done.returncode, "timed_out": False})
            except subprocess.TimeoutExpired:
                results.append({"stdout": "", "stderr": "", "exit_code": None, "timed_out": True})
        return {"compile_error": None, "results": results}