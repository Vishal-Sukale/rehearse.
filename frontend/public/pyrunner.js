// Runs the candidate's Python inside the browser (Pyodide, WebAssembly) in a Web Worker.
// Their code never reaches the server, and the page can stop it at any time by terminating this worker.
// Programs read standard input and print to standard output, like in a real coding interview.
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";

const HARNESS = `
import sys, io, json, contextlib

def run_many(code, inputs_json):
    inputs = json.loads(inputs_json)
    try:
        program = compile(code, "<main>", "exec")
    except BaseException as e:
        return json.dumps({"fatal": type(e).__name__ + ": " + str(e)[:300]})
    results = []
    for text in inputs:
        out = io.StringIO()
        old_in = sys.stdin
        sys.stdin = io.StringIO(text)
        try:
            with contextlib.redirect_stdout(out):
                exec(program, {"__name__": "__main__"})
            results.append({"ok": True, "stdout": out.getvalue()[:5000]})
        except SystemExit:
            results.append({"ok": True, "stdout": out.getvalue()[:5000]})
        except BaseException as e:
            results.append({"ok": False, "stdout": out.getvalue()[:5000], "error": type(e).__name__ + ": " + str(e)[:200]})
        finally:
            sys.stdin = old_in
    return json.dumps({"results": results})
`;

let pyodide = null;
const ready = (async () => {
  importScripts(PYODIDE + "pyodide.js");
  pyodide = await loadPyodide({ indexURL: PYODIDE });
  pyodide.runPython(HARNESS);
})();
ready.then(() => self.postMessage({ type: "ready" }), () => self.postMessage({ type: "error" }));

self.onmessage = async (event) => {
  const { id, code, inputs } = event.data;
  try {
    await ready;
    const runMany = pyodide.globals.get("run_many");
    self.postMessage({ id, ...JSON.parse(runMany(code, JSON.stringify(inputs))) });
  } catch (e) {
    self.postMessage({ id, fatal: String((e && e.message) || e).split("\n").filter(Boolean).slice(-1)[0] });
  }
};