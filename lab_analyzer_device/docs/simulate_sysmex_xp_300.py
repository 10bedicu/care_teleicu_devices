#!/usr/bin/env python3
"""
Sysmex XP-300 Automated Hematology Analyzer simulator.

Simulates unidirectional ASTM E1381/E1394 over TCP (analyzer as client):
  - Connects to the gateway inbound ASTM listener (default port 5006)
  - Sends ENQ, waits for ACK
  - Sends each H/P/O/R/L record as an individually ACKed frame
  - Sends EOT

Usage:
    python simulate_sysmex_xp_300.py [--host 127.0.0.1] [--port 5006]

Commands at the prompt:
    <sample_id>              — Send CBC results for sample (optional name/gender flags)
    send <id> [name] [M|F] — Shorthand to send results
    qc                       — Send validation run with sample ID "0"
    quit                     — Exit

Requires: no external dependencies (stdlib only)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("xp-300-sim")

ENQ = b"\x05"
ACK = b"\x06"
EOT = b"\x04"
STX = b"\x02"
ETX = b"\x03"
CR = b"\x0d"
LF = b"\x0a"
CRLF = CR + LF
FRAME_NUMBER_MODULO = 8

# XP-300 R-record parameters (order matches instrument capture).
# Each: (code, base_value, unit, ref_low, ref_high, decimals, width)
CBC_PARAMETERS = [
    ("WBC", 8.5, "10*3/uL", 4.0, 10.0, 1, 5),
    ("RBC", 3.52, "10*6/uL", 3.5, 5.5, 2, 5),
    ("HGB", 13.5, "g/dL", 11.0, 16.0, 1, 5),
    ("HCT", 42.0, "%", 37.0, 54.0, 1, 5),
    ("MCV", 88.0, "fL", 80.0, 100.0, 1, 5),
    ("MCH", 29.0, "pg", 27.0, 34.0, 1, 5),
    ("MCHC", 33.5, "g/dL", 32.0, 36.0, 1, 5),
    ("PLT", 284, "10*3/uL", 150, 450, 0, 5),
    ("LYM%", 21.4, "%", 20.0, 40.0, 1, 5),
    ("MXD%", 6.1, "%", 3.0, 15.0, 1, 5),
    ("NEUT%", 72.5, "%", 50.0, 70.0, 1, 5),
    ("LYM#", 1.8, "10*3/uL", 0.8, 4.0, 1, 5),
    ("MXD#", 0.5, "10*3/uL", 0.1, 1.5, 1, 5),
    ("NEUT#", 6.2, "10*3/uL", 2.0, 7.0, 1, 5),
    ("RDW-SD", 39.2, "fL", 35.0, 56.0, 1, 5),
    ("RDW-CV", 17.2, "%", 11.0, 16.0, 1, 5),
    ("PDW", 11.0, "fL", 9.0, 17.0, 1, 5),
    ("MPV", 8.4, "fL", 6.5, 12.0, 1, 5),
    ("P-LCR", 16.5, "%", 11.0, 45.0, 1, 5),
    ("PCT", 0.24, "%", 0.108, 0.282, 2, 5),
]

ORDER_TEST_LIST = "\\".join(f"^^^^{code}" for code, *_ in CBC_PARAMETERS)


def _now() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def make_checksum(payload: bytes) -> bytes:
    total = sum(payload) % 256
    return f"{total:02X}".encode("ascii")


def build_frame(record_text: str, frame_number: int) -> bytes:
    fn = str(frame_number % FRAME_NUMBER_MODULO).encode("ascii")
    body = fn + record_text.encode("ascii") + ETX
    return STX + body + make_checksum(body) + CRLF


def _vary_value(base: float, decimals: int) -> float:
    return round(base * random.uniform(0.90, 1.10), decimals)


def _compute_flag(value: float, ref_low: float, ref_high: float) -> str:
    if ref_high > 0 and value > ref_high:
        return "H"
    if ref_low > 0 and value < ref_low:
        return "L"
    return "N"


def _format_value(value: float, decimals: int, width: int) -> str:
    if decimals == 0:
        text = str(int(round(value)))
    else:
        text = f"{value:.{decimals}f}"
    return text.rjust(width)


def build_records(
    sample_id: str = "",
    patient_name: str = "SIM PATIENT",
    gender: str = "M",
) -> list[str]:
    """Build ASTM E1394 record lines for one CBC result message.

    XP-300 has one on-screen Sample ID field. It maps to O-3 component 2
    (``^^     <sample_id>^``); O-2 is always empty. *patient_name* and
    *gender* are ignored — kept only for CLI backward compatibility.
    """
    timestamp = _now()
    del patient_name, gender  # not transmitted by XP-300

    # O-2 empty; sample ID in O-3 component 2 (padded like instrument output).
    o_specimen = ""
    o_instrument = f"^^     {sample_id.strip()}^" if sample_id else "^^^"

    records = [
        r"H|\^&|||XP-300^00-16^^^^SIM001^SIMULATOR||||||||E1394-97",
        "P|1",
        (
            f"O|1|{o_specimen}|{o_instrument}|{ORDER_TEST_LIST}"
            "|||||||N||||||||||||||F"
        ),
    ]

    for seq, (code, base, unit, ref_low, ref_high, decimals, width) in enumerate(
        CBC_PARAMETERS, start=1
    ):
        value = _vary_value(base, decimals)
        flag = _compute_flag(value, ref_low, ref_high)
        value_str = _format_value(value, decimals, width)
        records.append(
            f"R|{seq}|^^^^{code}^1|{value_str}|{unit}||{flag}||||               ||{timestamp}"
        )

    records.append("L|1|N")
    return records


async def _read_ack(reader: asyncio.StreamReader, timeout: float = 10.0) -> bool:
    try:
        data = await asyncio.wait_for(reader.read(1), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("Timeout waiting for ACK")
        return False
    if not data:
        logger.error("Connection closed while waiting for ACK")
        return False
    if data == ACK:
        return True
    logger.warning("Expected ACK, got %r", data)
    return False


async def send_astm_message(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    records: list[str],
) -> bool:
    """Send a complete ASTM message with E1381 handshake."""
    writer.write(ENQ)
    await writer.drain()
    logger.info("[OUT] ENQ")
    if not await _read_ack(reader):
        return False

    frame_number = 1
    for record in records:
        frame = build_frame(record, frame_number)
        writer.write(frame)
        await writer.drain()
        logger.info("[OUT] %s", record)
        if not await _read_ack(reader):
            return False
        frame_number += 1

    writer.write(EOT)
    await writer.drain()
    logger.info("[OUT] EOT")
    return True


async def send_results(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    sample_id: str,
    patient_name: str = "SIM PATIENT",
    gender: str = "M",
) -> None:
    records = build_records(sample_id, patient_name, gender)
    logger.info("Sending CBC results for sample '%s' ...", sample_id or "(no accession)")
    ok = await send_astm_message(reader, writer, records)
    if ok:
        logger.info("Transmission complete.\n")
    else:
        logger.error("Transmission failed.\n")


async def session(host: str, port: int) -> None:
    logger.info("Connecting to %s:%d ...", host, port)
    reader, writer = await asyncio.open_connection(host, port)
    peer = writer.get_extra_info("sockname")
    logger.info("Connected from %s", peer)
    logger.info("")
    logger.info("Commands:")
    logger.info("  <sample_id>                    — Send CBC results")
    logger.info("  send <id> [name] [M|F]         — Send with optional patient info")
    logger.info("  qc                             — Send QC/validation (sample ID 0)")
    logger.info("  quit                           — Exit")
    logger.info("")

    loop = asyncio.get_event_loop()
    try:
        while True:
            try:
                user_input = await loop.run_in_executor(
                    None, lambda: input("XP-300> ")
                )
            except EOFError:
                break
            user_input = user_input.strip()
            if not user_input:
                continue
            if user_input.lower() == "quit":
                break
            if user_input.lower() == "qc":
                await send_results(reader, writer, "0", "QC SAMPLE", "U")
                continue

            parts = user_input.split()
            if parts[0].lower() == "send":
                if len(parts) < 2:
                    logger.error("Usage: send <sample_id> [name] [M|F]")
                    continue
                sample_id = parts[1]
                name = parts[2] if len(parts) > 2 else "SIM PATIENT"
                gender = parts[3].upper()[:1] if len(parts) > 3 else "M"
                await send_results(reader, writer, sample_id, name, gender)
                continue

            sample_id = user_input
            await send_results(reader, writer, sample_id)
    except KeyboardInterrupt:
        logger.info("Interrupted.")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        logger.info("Disconnected.")


async def run_once(
    host: str,
    port: int,
    sample_id: str,
    patient_name: str,
    gender: str,
) -> None:
    """Non-interactive single transmission (for scripting)."""
    reader, writer = await asyncio.open_connection(host, port)
    try:
        await send_results(reader, writer, sample_id, patient_name, gender)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sysmex XP-300 hematology analyzer simulator "
            "(ASTM E1381/E1394, unidirectional, inbound TCP)"
        )
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Gateway host address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5006,
        help="Gateway inbound ASTM port (default: 5006)",
    )
    parser.add_argument(
        "--sample-id",
        default="",
        help="If set, send one result message and exit (non-interactive)",
    )
    parser.add_argument("--name", default="SIM PATIENT", help="Patient name")
    parser.add_argument("--gender", default="M", help="Patient gender (M/F)")
    args = parser.parse_args()

    try:
        if args.sample_id:
            asyncio.run(
                run_once(args.host, args.port, args.sample_id, args.name, args.gender)
            )
        else:
            asyncio.run(session(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("Simulator stopped.")
        sys.exit(0)
    except ConnectionRefusedError:
        logger.error(
            "Connection refused — is the MLLP gateway listening on %s:%d?",
            args.host,
            args.port,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
