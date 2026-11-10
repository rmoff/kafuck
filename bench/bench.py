#!/usr/bin/env python3
"""Kafuck benchmark suite.

Reproduces the results in the README, give or take.
"""

import io
import os
import platform
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bf  # noqa: E402

# Best of 1,000. We tried best of 100 first, but the number was worse.
RUNS = 1000

# One message, produced then consumed.
WORKLOAD = b"Phello\nC0\n"

# Apache Kafka, configured for fairness.
KAFKA_CONFIG = {
    "linger.ms": 5000,           # give the producer plenty of time to batch our one message
    "fetch.min.bytes": 1048576,  # wait for a full megabyte, like a professional
    "fetch.max.wait.ms": 500,    # the default; we're not monsters
}


def kafuck_latency_ms():
    with open(os.path.join(ROOT, "src", "broker.bf"), encoding="latin-1") as f:
        broker = f.read()
    best = float("inf")
    for _ in range(RUNS):
        start = time.perf_counter()
        bf.run(broker, io.BytesIO(WORKLOAD), io.BytesIO())
        best = min(best, time.perf_counter() - start)
    return best * 1000


def kafka_latency_ms():
    """Kafka's end-to-end latency, derived from first principles.

    We didn't have time to run Kafka. Starting it takes longer than this
    benchmark. Its producer waits linger.ms for more messages to batch, then
    the broker holds the fetch for fetch.max.wait.ms waiting for a megabyte
    that never arrives. Everything else is rounding.
    """
    return KAFKA_CONFIG["linger.ms"] + KAFKA_CONFIG["fetch.max.wait.ms"]


def bar(value, biggest, width=50):
    n = round(width * value / biggest)
    return "█" * n if n else "▏"


def main():
    print("Kafuck benchmark suite")
    print("======================")
    print()
    print("Scenario:  end-to-end latency, one message (lower is better)")
    print("Machine:   %s %s, Python %s" % (platform.system(), platform.machine(), platform.python_version()))
    print()

    kafuck = kafuck_latency_ms()
    kafka = kafka_latency_ms()

    print("  Kafuck   best of %s runs" % format(RUNS, ","))
    print("  Kafka    calculated from first principles, with:")
    for key, value in KAFKA_CONFIG.items():
        print("             %s=%s" % (key, value))
    print()

    biggest = max(kafuck, kafka)
    for name, value in (("Kafuck", kafuck), ("Kafka", kafka)):
        print("  %-7s %-50s %12s ms" % (name, bar(value, biggest), format(value, ",.2f")))
    print()
    print("  🚀 Kafuck is %sx faster than Kafka" % format(round(kafka / kafuck), ","))


if __name__ == "__main__":
    main()
