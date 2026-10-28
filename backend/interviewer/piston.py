"""Client for a Piston-compatible code-execution service (https://github.com/engineer-man/piston).
The candidate's code runs inside that service's sandbox, never on this server. Standard library only."""
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


class RunnerError(RuntimeError):
    """The execution service could not be reached or refused the request."""


def installed_languages(base_url: str, timeout: float = 3.0) -> set[str] | None:
    """Names and aliases of the languages installed in the runner, or None if it can't be reached."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/v2/runtimes", timeout=timeout) as response:
            runtimes = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    names: set[str] = set()
    for runtime in runtimes if isinstance(runtimes, list) else []:
        names.add(runtime.get("language", ""))
        names.update(runtime.get("aliases", []))
    return names


def build_payload(piston_language: str, filename: str | None, code: str, stdin: str) -> dict:
    file = {"content": code}
    if filename:
        file["name"] = filename
    return {
        "language": piston_language, "version": "*", "files": [file], "stdin": stdin,
        "compile_timeout": 10000, "run_timeout": 3000,
    }


def parse_result(data: dict) -> dict:
    compiled = data.get("compile") or {}
    run = data.get("run") or {}
    compile_failed = bool(compiled) and compiled.get("code") not in (0, None)
    return {
        "compile_error": (compiled.get("stderr") or compiled.get("output") or "Compilation failed")[:2000] if compile_failed else None,
        "stdout": (run.get("stdout") or "")[:5000],
        "stderr": (run.get("stderr") or "")[:1000],
        "exit_code": run.get("code"),
        "timed_out": run.get("status") == "TO" or run.get("signal") == "SIGKILL",
    }


def execute(base_url: str, payload: dict, timeout: float = 20.0) -> dict:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/v2/execute", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return parse_result(json.loads(response.read().decode()))
    except urllib.error.HTTPError as err:
        try:
            detail = json.loads(err.read().decode()).get("message", "")
        except ValueError:
            detail = ""
        raise RunnerError(f"The code runner refused the request. {detail}".strip()) from err
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        raise RunnerError(f"The code runner at {base_url} could not be reached. Is it running?") from err


def run_many(base_url: str, piston_language: str, filename: str | None, code: str, inputs: list[str], max_workers: int = 4) -> dict:
    """Run one program on several stdin inputs. The first run doubles as the compile check: if it fails, stop."""
    first = execute(base_url, build_payload(piston_language, filename, code, inputs[0]))
    if first["compile_error"]:
        return {"compile_error": first["compile_error"], "results": []}
    rest = []
    if len(inputs) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            rest = list(pool.map(lambda text: execute(base_url, build_payload(piston_language, filename, code, text)), inputs[1:]))
    return {"compile_error": None, "results": [first, *rest]}