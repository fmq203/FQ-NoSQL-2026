#!/usr/bin/env python3
"""Resumen del archivo .jtl de JMeter (CSV) sin dependencias externas.

Uso: python3 jmeter/resumen.py jmeter/results/resultados.jtl [stock]

Imprime por etiqueta: muestras, errores, codigos HTTP, latencia (promedio, p95,
p99) y rendimiento; y verifica la prueba de doble venta: cuantas compras (201)
hubo contra el stock configurado. Termina con codigo 1 si hubo errores de
aserciones o si se vendio mas que el stock.
"""
import csv
import sys
from collections import Counter, defaultdict

DOBLE_VENTA = "POST /api/reservar (mismo evento)"


def percentil(valores, p):
    valores = sorted(valores)
    return valores[min(len(valores) - 1, int(p / 100 * len(valores)))] if valores else 0


def main(ruta, stock):
    por_etiqueta = defaultdict(list)
    with open(ruta, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            por_etiqueta[fila["label"]].append(fila)

    hay_fallos = False
    print(f"{'etiqueta':<46}{'n':>7}{'err':>6}{'avg ms':>8}{'p95':>7}{'p99':>7}{'req/s':>8}  codigos")
    for etiqueta, filas in por_etiqueta.items():
        lat = [int(x["elapsed"]) for x in filas]
        errores = sum(1 for x in filas if x["success"] != "true")
        t0 = min(int(x["timeStamp"]) for x in filas)
        t1 = max(int(x["timeStamp"]) + int(x["elapsed"]) for x in filas)
        tasa = len(filas) / max((t1 - t0) / 1000, 0.001)
        codigos = dict(Counter(x["responseCode"] for x in filas))
        print(f"{etiqueta:<46}{len(filas):>7}{errores:>6}{sum(lat) / len(lat):>8.0f}{percentil(lat, 95):>7}{percentil(lat, 99):>7}{tasa:>8.1f}  {codigos}")
        hay_fallos = hay_fallos or errores > 0

    dv = por_etiqueta.get(DOBLE_VENTA)
    if dv:
        codigos = Counter(x["responseCode"] for x in dv)
        compras, rechazos = codigos.get("201", 0), codigos.get("409", 0)
        print(f"\nDoble venta: {len(dv)} intentos -> {compras} compras (201) y {rechazos} rechazos (409)", end="")
        if stock is not None:
            ok = compras == stock
            print(f"; stock = {stock} -> {'OK: se vendio exactamente el stock' if ok else 'FALLO: compras != stock'}")
            hay_fallos = hay_fallos or not ok
        else:
            print()
    return 1 if hay_fallos else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None))
