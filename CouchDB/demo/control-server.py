#!/usr/bin/env python3
"""Sirve el monitor y ejecuta las acciones de Docker que pide la pagina.

Seguridad, aunque sea una demo local:
  - escucha solo en 127.0.0.1, no queda expuesto en la red
  - solo ejecuta comandos de una lista fija (ACCIONES). El navegador manda
    una clave, nunca un comando: no se arma ningun string con texto de
    afuera y no se usa shell=True
"""
import json
import os
import subprocess
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DEMO = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(DEMO, "ui", "monitor")
PUERTO = 8084

ACCIONES = {
    "encender-todo":  [["docker", "compose", "up", "-d"], ["./setup.sh"]],
    "apagar-todo":    [["docker", "compose", "stop"]],
    # destructivo: borra los volumenes. La pagina pide confirmacion.
    "reset-total":    [["docker", "compose", "down", "-v"],
                       ["docker", "compose", "up", "-d"],
                       ["./setup.sh"]],
    "up:central-a":   [["docker", "compose", "start", "couch-central"]],
    "down:central-a": [["docker", "compose", "stop", "couch-central"]],
    "up:central-b":   [["docker", "compose", "start", "couch-central-b"]],
    "down:central-b": [["docker", "compose", "stop", "couch-central-b"]],
    "up:tablet-a":    [["docker", "compose", "start", "couch-tablet"]],
    "down:tablet-a":  [["docker", "compose", "stop", "couch-tablet"]],
}


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/accion":
            self.send_error(404)
            return
        largo = int(self.headers.get("Content-Length", 0))
        try:
            datos = json.loads(self.rfile.read(largo) or b"{}")
        except ValueError:
            self._json(400, {"error": "json inválido"})
            return

        accion = datos.get("accion")
        if accion not in ACCIONES:
            self._json(400, {"error": "acción desconocida: %s" % accion})
            return

        pasos = []
        for cmd in ACCIONES[accion]:
            try:
                r = subprocess.run(cmd, cwd=DEMO, capture_output=True,
                                   text=True, timeout=240)
                pasos.append({"cmd": " ".join(cmd), "code": r.returncode,
                              "out": (r.stdout or "")[-500:],
                              "err": (r.stderr or "")[-500:]})
                if r.returncode != 0:
                    break
            except subprocess.TimeoutExpired:
                pasos.append({"cmd": " ".join(cmd), "code": -1,
                              "out": "", "err": "se pasó del tiempo límite"})
                break
            except OSError as e:
                pasos.append({"cmd": " ".join(cmd), "code": -1,
                              "out": "", "err": str(e)})
                break

        self._json(200, {"ok": all(p["code"] == 0 for p in pasos), "pasos": pasos})

    def _json(self, code, obj):
        cuerpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO),
                                   partial(Handler, directory=UI))
    servidor.serve_forever()
