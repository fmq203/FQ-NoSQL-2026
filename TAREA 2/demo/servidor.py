"""Servidor local de la demo: sirve index.html y deja subir/bajar los contenedores.

    python3 demo/servidor.py            # http://localhost:8080
    python3 demo/servidor.py --port 9000

Solo stdlib. La API de control corre `docker compose` sobre el docker-compose.yml
de TAREA 2, con una lista fija de servicios y acciones (sin shell), y "limpiar
datos" vacía MongoDB, Redis y el event_log de PostgreSQL con comandos fijos. Como cualquier
página abierta en el navegador puede pegarle a localhost, se defiende así:
- escucha solo en 127.0.0.1;
- exige el header X-Demo-Control (un fetch de otro origen con ese header necesita
  un preflight CORS que este servidor nunca aprueba);
- rechaza Host/Origin que no sean este mismo servidor (DNS rebinding).
"""
import argparse
import json
import subprocess
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

DEMO_DIR = Path(__file__).resolve().parent
COMPOSE_DIR = DEMO_DIR.parent

SERVICIOS = (
    "mongodb",
    "redis",
    "postgresql",
    "usuarios-service",
    "eventos-service",
    "reservas-service",
)
TIMEOUT_SEGUNDOS = 180


def docker_compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=COMPOSE_DIR,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SEGUNDOS,
    )


def estado_contenedores() -> dict:
    """{servicio: {"state": running|exited|..., "health": healthy|...}} desde `docker compose ps`."""
    proc = docker_compose("ps", "-a", "--format", "json")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "docker compose ps falló")
    salida = proc.stdout.strip()
    # Según la versión de compose sale un array JSON o un objeto por línea.
    filas = json.loads(salida) if salida.startswith("[") else [json.loads(l) for l in salida.splitlines() if l]
    estado = {s: {"state": "missing", "health": ""} for s in SERVICIOS}
    for fila in filas:
        if fila.get("Service") in estado:
            estado[fila["Service"]] = {"state": fila.get("State", ""), "health": fila.get("Health", "")}
    return estado


# Vacía los datos conservando la estructura (índices de Mongo, tabla y vistas de PostgreSQL).
_LIMPIAR_MONGO_JS = (
    'const e = db.getSiblingDB("eventflow");'
    'print(JSON.stringify(Object.fromEntries('
    '["usuarios", "eventos", "reservas"].map(c => [c, e[c].deleteMany({}).deletedCount]))));'
)
LIMPIEZA = (
    ("mongodb", ["mongosh", "--quiet", "--eval", _LIMPIAR_MONGO_JS]),
    ("redis", ["redis-cli", "FLUSHALL"]),  # DB 0 (pagos/inventario) y DB 1 (caché de lecturas)
    ("postgresql", ["sh", "-c", 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "TRUNCATE event_log RESTART IDENTITY"']),
)


def limpiar_datos() -> dict:
    resultados = {}
    for servicio, comando in LIMPIEZA:
        proc = docker_compose("exec", "-T", servicio, *comando)
        resultados[servicio] = {"ok": proc.returncode == 0, "salida": (proc.stdout + proc.stderr).strip()}
    return resultados


def accion_docker(accion: str, servicio: str) -> subprocess.CompletedProcess:
    objetivo = [] if servicio == "todos" else [servicio]
    if accion == "start":
        # `up -d` (sin build) también crea un contenedor que no exista; `start` no.
        return docker_compose("up", "-d", *objetivo)
    return docker_compose("stop", *objetivo)


class DemoHandler(SimpleHTTPRequestHandler):
    def _origen_permitido(self) -> bool:
        puerto = self.server.server_address[1]
        permitidos = {f"localhost:{puerto}", f"127.0.0.1:{puerto}"}
        if self.headers.get("Host") not in permitidos:
            return False
        origin = self.headers.get("Origin")
        return origin is None or urlparse(origin).netloc in permitidos

    def _json(self, status: int, cuerpo: dict) -> None:
        datos = json.dumps(cuerpo).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)

    def _control_autorizado(self) -> bool:
        if self._origen_permitido() and self.headers.get("X-Demo-Control") == "1":
            return True
        self._json(403, {"detail": "Solo se acepta desde la propia página de la demo"})
        return False

    def do_GET(self):
        if self.path != "/control/estado":
            return super().do_GET()
        if not self._control_autorizado():
            return
        try:
            self._json(200, {"servicios": estado_contenedores()})
        except (RuntimeError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            self._json(503, {"detail": f"No se pudo consultar Docker: {exc}"})

    def do_POST(self):
        if self.path == "/control/limpiar":
            if not self._control_autorizado():
                return
            try:
                resultados = limpiar_datos()
            except (OSError, subprocess.TimeoutExpired) as exc:
                return self._json(503, {"detail": f"No se pudo ejecutar docker compose: {exc}"})
            todo_ok = all(r["ok"] for r in resultados.values())
            return self._json(200 if todo_ok else 500, {"resultados": resultados})
        partes = self.path.strip("/").split("/")
        if len(partes) != 3 or partes[0] != "control":
            return self._json(404, {"detail": "Not Found"})
        if not self._control_autorizado():
            return
        _, accion, servicio = partes
        if accion not in ("start", "stop") or servicio not in (*SERVICIOS, "todos"):
            return self._json(400, {"detail": f"Acción o servicio inválido: {accion} {servicio}"})
        try:
            proc = accion_docker(accion, servicio)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return self._json(503, {"detail": f"No se pudo ejecutar docker compose: {exc}"})
        salida = (proc.stdout + proc.stderr).strip()
        self._json(200 if proc.returncode == 0 else 500,
                   {"accion": accion, "servicio": servicio, "returncode": proc.returncode, "salida": salida})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    servidor = ThreadingHTTPServer(("127.0.0.1", args.port), partial(DemoHandler, directory=str(DEMO_DIR)))
    print(f"Demo en http://localhost:{args.port}/index.html (Ctrl+C para cortar)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
