#!/usr/bin/env python3
# gimp-shell bridge: lets gimp-shell run Python inside GIMP 3.
#
# It speaks agent-shell's host protocol (v1): a loopback TCP server that reads one JSON
# request line and writes one JSON response line per connection.
#
#   -> {"id":1,"method":"hello","token":"..."}
#   <- {"id":1,"name":"gimp","version":"3.2.4","commands":[{"name":"python",...}]}
#   -> {"id":2,"method":"invoke","token":"...","cmd":"python","args":[],"stdin":"<code>"}
#   <- {"id":2,"stdout":"...","stderr":"...","exit_code":0}
#
# Code runs on the plug-in's main thread, where libgimp may be called: the socket thread
# only hands it over and waits. Each run gets a fresh namespace, keeps what it printed
# when it fails, and has PDB errors returned to it instead of shown in GIMP's console.
#
# Port and token come from GIMP_SHELL_PORT / GIMP_SHELL_TOKEN, else from
# ~/.agent-shell/gimp/bridge.json ({"port": 9520, "token": "..."}); the default is port
# 9520 with no token. Start it from Tools > gimp-shell > Start Bridge.
import hmac
import io
import json
import os
import socket
import sys
import threading
import traceback

import gi

gi.require_version("Gimp", "3.0")
from gi.repository import GLib, GObject, Gimp  # noqa: E402

BRIDGE_VERSION = "dev"  # stamped by `gimp-shell plugin install`
PROC_START = "plug-in-gimp-shell-bridge"
DEFAULT_PORT = 9520
MAX_REQUEST = 64 << 20
RUN_TIMEOUT = 600  # seconds; agent-shell has its own, shorter timeout per run

PYTHON_HELP = """usage: python [ARGS...] < CODE
Run Python inside GIMP, with ARGS as a list of strings. Gimp, Gegl, Gio, GLib and GObject
are imported. What the code prints is the output; an exception exits 1 with its message,
after whatever was printed before it.
  python <<'EOF'
  for img in Gimp.get_images():
      print(img.get_id(), img.get_width(), img.get_height())
  EOF"""


def log(msg):
    # Never sys.stdout: while code runs, that is the command's output.
    print("[gimp-shell] " + msg, file=sys.__stderr__, flush=True)


def load_settings():
    port, token = DEFAULT_PORT, ""
    base = os.environ.get("AGENT_SHELL_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".agent-shell")
    path = os.path.join(base, "gimp", "bridge.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        port = int(data.get("port", port))
        token = str(data.get("token", token))
    except FileNotFoundError:
        pass
    except (ValueError, OSError) as e:
        log("ignoring %s: %s" % (path, e))
    if os.environ.get("GIMP_SHELL_PORT", "").isdigit():
        port = int(os.environ["GIMP_SHELL_PORT"])
    token = os.environ.get("GIMP_SHELL_TOKEN", token)
    return port, token


def error_text(exc):
    """An exception as the agent should see it: a Fail (gimp-shell's lib) as its message,
    anything else as its type and message, with the innermost line of the command."""
    if type(exc).__name__ == "Fail":
        return str(exc)
    text = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<command>"]
    if frames:
        f = frames[-1]
        where = "line %d" % f.lineno if f.name == "<module>" else "line %d, in %s" % (f.lineno, f.name)
        text += " (%s)" % where
    return text


def execute(code, args):
    """Run code; its output, error output and exit code."""
    out, err = io.StringIO(), io.StringIO()
    namespace = {"__name__": "__gimp_shell__", "ARGS": list(args)}
    exit_code = 0
    saved = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        exec("from gi.repository import Gegl, Gimp, Gio, GLib, GObject", namespace)
        exec(compile(code, "<command>", "exec"), namespace)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if e.code is not None and not isinstance(e.code, int):
            err.write(str(e.code) + "\n")
    except BaseException as e:  # noqa: BLE001 - every failure goes back to the caller
        exit_code = 1
        err.write(error_text(e) + "\n")
    finally:
        sys.stdout, sys.stderr = saved
    return {"stdout": out.getvalue(), "stderr": err.getvalue(), "exit_code": exit_code}


def on_main_thread(fn, timeout):
    """Run fn on the GLib main loop and wait for it."""
    done = threading.Event()
    box = {}

    def task():
        try:
            box["value"] = fn()
        except BaseException as e:  # noqa: BLE001
            box["error"] = e
        finally:
            done.set()
        return GLib.SOURCE_REMOVE

    GLib.idle_add(task)
    if not done.wait(timeout):
        raise TimeoutError("timed out after %ds; GIMP may still be running the command" % timeout)
    if "error" in box:
        raise box["error"]
    return box["value"]


class Bridge:
    def __init__(self, port, token):
        self.port, self.token = port, token
        self.sock = None

    def listen(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", self.port))
        self.sock.listen(8)
        threading.Thread(target=self.accept_loop, daemon=True).start()

    def accept_loop(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self.serve, args=(conn,), daemon=True).start()

    def serve(self, conn):
        with conn:
            try:
                line = read_line(conn)
                if not line:
                    return
                resp = self.handle(line)
            except Exception as e:  # noqa: BLE001
                resp = {"error": "bridge: %s" % e}
            conn.sendall(json.dumps(resp).encode("utf-8") + b"\n")

    def handle(self, line):
        try:
            req = json.loads(line)
        except ValueError as e:
            return {"error": "bad request: %s" % e}
        rid = req.get("id", 0)
        if self.token and not hmac.compare_digest(str(req.get("token", "")), self.token):
            return {"id": rid, "error": "Unauthorized"}
        method = req.get("method")
        if method == "hello":
            return {"id": rid, "name": "gimp", "version": "%s, bridge %s" % (Gimp.version(), BRIDGE_VERSION), "commands": [
                {"name": "python", "summary": "run Python inside GIMP: python [ARGS...] < CODE", "help": PYTHON_HELP},
            ]}
        if method == "help":
            if req.get("cmd") == "python":
                return {"id": rid, "stdout": PYTHON_HELP}
            return {"id": rid, "error": "unknown command %s" % req.get("cmd")}
        if method == "invoke":
            if req.get("cmd") != "python":
                return {"id": rid, "error": "unknown command %s" % req.get("cmd")}
            res = on_main_thread(lambda: execute(req.get("stdin") or "", req.get("args") or []), RUN_TIMEOUT)
            res["id"] = rid
            return res
        return {"id": rid, "error": "unknown method %s" % method}


def read_line(conn):
    buf = bytearray()
    while b"\n" not in buf:
        chunk = conn.recv(65536)
        if not chunk:
            break
        buf += chunk
        if len(buf) > MAX_REQUEST:
            raise ValueError("request too large")
    return bytes(buf).split(b"\n", 1)[0].decode("utf-8")


class GimpShellBridge(Gimp.PlugIn):
    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [PROC_START]

    def do_create_procedure(self, name):
        procedure = Gimp.Procedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        procedure.set_menu_label("Start Bridge")
        procedure.set_documentation(
            "Start the gimp-shell bridge",
            "Lets gimp-shell run Python in GIMP over a loopback socket, until GIMP quits.",
            name)
        procedure.set_attribution("gimp-shell", "gimp-shell", "2026")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
        procedure.add_enum_argument("run-mode", "Run mode", "The run mode", Gimp.RunMode,
                                    Gimp.RunMode.INTERACTIVE, GObject.ParamFlags.READWRITE)
        procedure.add_menu_path("<Image>/Tools/gimp-shell")
        return procedure

    def run(self, procedure, config, run_data):
        port, token = load_settings()
        bridge = Bridge(port, token)
        try:
            bridge.listen()
        except OSError as e:
            Gimp.message("gimp-shell bridge: port %d is in use (already running?): %s" % (port, e))
            return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())
        # PDB failures come back to the code that called them, not GIMP's error console.
        self.set_pdb_error_handler(Gimp.PDBErrorHandler.PLUGIN)
        log("listening on 127.0.0.1:%d%s" % (port, " (token required)" if token else ""))
        Gimp.message("gimp-shell bridge listening on 127.0.0.1:%d" % port)
        # This process now serves until GIMP quits; code runs here, on the main loop.
        GLib.MainLoop().run()
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


Gimp.main(GimpShellBridge.__gtype__, sys.argv)
