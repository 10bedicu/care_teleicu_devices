#!/usr/bin/env python3
"""
Mindray BC-5150 Auto Hematology Analyzer simulator.

Simulates host-query HL7 v2.3.1 MLLP communication with outbound connection:
  - Listens on the analyzer MLLP port (default 5100) for gateway connections
  - Sends ORM^O01 worklist query for a sample/barcode
  - Receives ORR^O02 worklist response
  - Sends ORU^R01 with randomized 5-part differential CBC results
  - Waits for ACK^R01

Usage:
    python simulate_bc_5150.py [--host 0.0.0.0] [--port 5100]

Requires: no external dependencies (stdlib only)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("bc-5150-sim")

SB = b"\x0b"
EB = b"\x1c"
CR = b"\x0d"

# Clinical NM parameters sent in ORU^R01 (matches BC-5150 LOINC/99MRC OBX-3 format).
# Each entry: (code, name, system, base_value, unit, ref_low, ref_high, decimals)
CBC_5DIFF_PARAMETERS = [
    ("6690-2", "WBC", "LN", 7.5, "10*9/L", 4.00, 10.00, 2),
    ("704-7", "BAS#", "LN", 0.05, "10*9/L", 0.00, 0.10, 2),
    ("706-2", "BAS%", "LN", 0.8, "%", 0.0, 1.0, 1),
    ("751-8", "NEU#", "LN", 4.8, "10*9/L", 2.00, 7.00, 2),
    ("770-8", "NEU%", "LN", 64.0, "%", 50.0, 70.0, 1),
    ("711-2", "EOS#", "LN", 0.25, "10*9/L", 0.02, 0.50, 2),
    ("713-8", "EOS%", "LN", 3.2, "%", 0.5, 5.0, 1),
    ("731-0", "LYM#", "LN", 2.0, "10*9/L", 0.80, 4.00, 2),
    ("736-9", "LYM%", "LN", 28.0, "%", 20.0, 40.0, 1),
    ("742-7", "MON#", "LN", 0.55, "10*9/L", 0.12, 1.20, 2),
    ("5905-5", "MON%", "LN", 7.5, "%", 3.0, 12.0, 1),
    ("26477-0", "*ALY#", "LN", 0.02, "10*9/L", 0.00, 0.00, 2),
    ("13046-8", "*ALY%", "LN", 0.2, "%", 0.0, 0.0, 1),
    ("10000", "*LIC#", "99MRC", 0.02, "10*9/L", 0.00, 0.00, 2),
    ("10001", "*LIC%", "99MRC", 0.1, "%", 0.0, 0.0, 1),
    ("30376-8", "Blast#", "LN", 0.01, "10*9/L", 0.00, 0.00, 2),
    ("10049", "Blast%", "99MRC", 0.1, "%", 0.0, 0.0, 1),
    ("789-8", "RBC", "LN", 4.6, "10*12/L", 3.50, 5.50, 2),
    ("718-7", "HGB", "LN", 13.5, "g/dL", 11.0, 16.0, 1),
    ("4544-3", "HCT", "LN", 42.0, "%", 37.0, 47.0, 1),
    ("787-2", "MCV", "LN", 88.0, "fL", 80.0, 100.0, 1),
    ("785-6", "MCH", "LN", 30.0, "pg", 27.0, 34.0, 1),
    ("786-4", "MCHC", "LN", 34.0, "g/dL", 32.0, 36.0, 1),
    ("788-0", "RDW-CV", "LN", 13.2, "%", 11.0, 16.0, 1),
    ("21000-5", "RDW-SD", "LN", 44.0, "fL", 35.0, 56.0, 1),
    ("777-3", "PLT", "LN", 240, "10*9/L", 150, 450, 0),
    ("32623-1", "MPV", "LN", 10.0, "fL", 6.5, 12.0, 1),
    ("32207-3", "PDW", "LN", 15.5, "", 9.0, 17.0, 1),
    ("10002", "PCT", "99MRC", 0.24, "%", 0.108, 0.282, 3),
    ("30392-5", "NRBC#", "LN", 0.00, "10*9/L", 0.00, 0.00, 2),
    ("26461-4", "NRBC%", "LN", 0.0, "%", 0.0, 0.0, 1),
    ("10013", "PLCC", "99MRC", 60, "10*9/L", 30, 90, 0),
    ("10014", "PLCR", "99MRC", 28.0, "%", 11.0, 45.0, 1),
]

_message_counter = 0


def _now() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _next_message_id() -> int:
    global _message_counter
    _message_counter += 1
    return _message_counter


def mllp_encode(hl7_message: str) -> bytes:
    return SB + hl7_message.encode("utf-8") + EB + CR


async def mllp_send(writer: asyncio.StreamWriter, hl7_message: str) -> None:
    writer.write(mllp_encode(hl7_message))
    await writer.drain()


async def mllp_receive(reader: asyncio.StreamReader) -> str:
    while True:
        byte = await reader.readexactly(1)
        if byte == SB:
            break

    buf = bytearray()
    while True:
        byte = await reader.readexactly(1)
        if byte == EB:
            await reader.readexactly(1)
            break
        buf.extend(byte)

    return buf.decode("utf-8")


def _vary_value(base: float, decimals: int) -> float:
    return round(base * random.uniform(0.90, 1.10), decimals)


def _compute_flag(value: float, ref_low: float, ref_high: float) -> str:
    if ref_high > 0 and value > ref_high:
        suffix = "H" if (value - ref_high) / ref_high <= 0.15 else "H~N"
        return suffix
    if ref_low > 0 and value < ref_low:
        suffix = "L" if (ref_low - value) / ref_low <= 0.15 else "L~N"
        return suffix
    return "N"


def build_orm_o01(sample_id: str) -> str:
    """Build ORM^O01 worklist query (ORC|RF||<sample_id>||IP)."""
    now = _now()
    msg_id = _next_message_id()
    return "\r".join(
        [
            f"MSH|^~\\&|||||{now}||ORM^O01|{msg_id}|P|2.3.1||||||UNICODE",
            f"ORC|RF||{sample_id}||IP",
        ]
    )


def build_oru_r01(
    sample_id: str,
    patient_id: str = "",
    patient_name: str = "",
    gender: str = "",
    ref_group: str = "Common",
    operator: str = "Administrator",
) -> str:
    """Build ORU^R01 with 5-part differential CBC results."""
    now = _now()
    msg_id = _next_message_id()
    collect_time = now

    segments = [
        f"MSH|^~\\&|||||{now}||ORU^R01|{msg_id}|P|2.3.1||||||UNICODE",
        f"PID|1||{patient_id}^^^^MR||{patient_name}|||{gender}",
        "PV1|1",
        (
            f"OBR|1||{sample_id}|00001^Automated Count^99MRC|||{collect_time}"
            f"|||||||||||||||||HM||||||||{operator}"
        ),
        "OBX|1|IS|08001^Take Mode^99MRC||O||||||F",
        "OBX|2|IS|08002^Blood Mode^99MRC||W||||||F",
        "OBX|3|IS|08003^Test Mode^99MRC||CBC+DIFF||||||F",
        f"OBX|4|IS|01002^Ref Group^99MRC||{ref_group}||||||F",
    ]

    obx_idx = 5
    for code, name, system, base_val, unit, ref_low, ref_high, decimals in CBC_5DIFF_PARAMETERS:
        value = _vary_value(base_val, decimals)
        flag = _compute_flag(value, ref_low, ref_high)

        if decimals == 0:
            value_str = str(int(round(value)))
        else:
            value_str = f"{value:.{decimals}f}"

        if ref_low == int(ref_low) and ref_high == int(ref_high):
            ref_range = f"{int(ref_low)}-{int(ref_high)}"
        else:
            ref_range = f"{ref_low:.2f}-{ref_high:.2f}"

        segments.append(
            f"OBX|{obx_idx}|NM|{code}^{name}^{system}||{value_str}|{unit}|{ref_range}|{flag}|||F"
        )
        obx_idx += 1

    return "\r".join(segments)


def parse_orr_patient_id(orr_message: str) -> str:
    for line in orr_message.split("\r"):
        if line.startswith("PID|"):
            parts = line.split("|")
            if len(parts) > 3:
                return parts[3].split("^")[0] or parts[3]
    return ""


def parse_orr_patient_name(orr_message: str) -> str:
    for line in orr_message.split("\r"):
        if line.startswith("PID|"):
            parts = line.split("|")
            if len(parts) > 5:
                return parts[5]
    return ""


def parse_orr_gender(orr_message: str) -> str:
    for line in orr_message.split("\r"):
        if line.startswith("PID|"):
            parts = line.split("|")
            if len(parts) > 8:
                return parts[8]
    return ""


def _log_message(direction: str, message: str) -> None:
    for line in message.split("\r"):
        if line.strip():
            logger.info(f"  {direction} {line}")


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    peer = writer.get_extra_info("peername")
    logger.info("Gateway connected from %s", peer)
    logger.info("")
    logger.info("Commands:")
    logger.info("  <sample_id>  — Query worklist (ORM^O01), then send results (ORU^R01)")
    logger.info("  send <id>   — Send ORU^R01 results directly without worklist query")
    logger.info("  quit        — Close connection")
    logger.info("")

    loop = asyncio.get_event_loop()

    try:
        while True:
            user_input = await loop.run_in_executor(
                None, lambda: input("BC-5150> ")
            )
            user_input = user_input.strip()

            if not user_input:
                continue
            if user_input.lower() == "quit":
                break

            if user_input.lower().startswith("send "):
                parts = user_input.split()
                if len(parts) < 2:
                    logger.error("Usage: send <sample_id>")
                    continue
                sample_id = parts[1]
                await _send_results(reader, writer, sample_id)
                continue

            await _query_and_send(reader, writer, user_input)

    except (KeyboardInterrupt, EOFError):
        logger.info("Closing connection ...")
    except Exception as e:
        logger.error("Session error: %s", e, exc_info=True)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        logger.info("Gateway disconnected.")


async def _query_and_send(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    sample_id: str,
) -> None:
    orm_msg = build_orm_o01(sample_id)
    logger.info("Sending ORM^O01 for sample '%s' ...", sample_id)
    _log_message("->", orm_msg)
    await mllp_send(writer, orm_msg)

    try:
        orr_msg = await asyncio.wait_for(mllp_receive(reader), timeout=15.0)
    except asyncio.TimeoutError:
        logger.warning("No ORR^O02 received within 15s.\n")
        return
    except asyncio.IncompleteReadError:
        logger.error("Connection closed while waiting for ORR^O02.")
        return

    logger.info("Received ORR^O02:")
    _log_message("<-", orr_msg)

    if "MSA|AE" in orr_msg or "MSA|AR" in orr_msg:
        logger.warning("Worklist query rejected by LIS.\n")
        return
    if "MSA|AA" not in orr_msg:
        logger.warning("Unexpected worklist response.\n")
        return

    patient_id = parse_orr_patient_id(orr_msg) or f"PAT-{sample_id}"
    patient_name = parse_orr_patient_name(orr_msg) or f"^Sim Patient {sample_id}"
    gender = parse_orr_gender(orr_msg) or "Unknown"

    await _send_results(
        reader,
        writer,
        sample_id,
        patient_id=patient_id,
        patient_name=patient_name,
        gender=gender,
    )


async def _send_results(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    sample_id: str,
    patient_id: str = "",
    patient_name: str = "",
    gender: str = "",
) -> None:
    oru_msg = build_oru_r01(
        sample_id=sample_id,
        patient_id=patient_id or f"PAT-{sample_id}",
        patient_name=patient_name or f"^Sim Patient {sample_id}",
        gender=gender or "Unknown",
    )

    logger.info("Sending ORU^R01 for sample '%s' ...", sample_id)
    _log_message("->", oru_msg)
    await mllp_send(writer, oru_msg)

    try:
        ack_msg = await asyncio.wait_for(mllp_receive(reader), timeout=15.0)
        logger.info("Received ACK:")
        _log_message("<-", ack_msg)
        if "MSA|AA" in ack_msg:
            logger.info("Results accepted.\n")
        else:
            logger.warning("Unexpected or negative ACK.\n")
    except asyncio.TimeoutError:
        logger.warning("No ACK received within 15s.\n")
    except asyncio.IncompleteReadError:
        logger.error("Connection closed while waiting for ACK.\n")


async def run_simulator(host: str, port: int) -> None:
    server = await asyncio.start_server(handle_client, host, port)
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    logger.info("Mindray BC-5150 simulator listening on %s", addrs)
    logger.info("Waiting for gateway outbound connection on port %d ...", port)

    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Mindray BC-5150 hematology analyzer simulator "
            "(HL7 v2.3.1 / MLLP, host-query, outbound connection)"
        )
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Listen address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5100,
        help="Analyzer MLLP listen port (default: 5100)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_simulator(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("Simulator stopped.")


if __name__ == "__main__":
    main()
