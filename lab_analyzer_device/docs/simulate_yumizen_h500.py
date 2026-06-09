#!/usr/bin/env python3
"""
Yumizen H500 / H500E lab analyzer simulator.

Simulates the Horiba Yumizen H500's HL7 v2.5 MLLP behaviour:
  - Connects to the gateway's ORU port (results, default 2575)
  - Connects to the gateway's ORM port (orders, default 2576)
  - Waits for OML^O33 orders on the ORM socket
  - Replies with ORL^O34 acknowledgment
  - Sends OUL^R22 sample results on the ORU socket
  - Reads ACK^R22 from the gateway

Usage:
    python scripts/simulate_yumizen_h500.py [--host 127.0.0.1] [--oru-port 2575] [--orm-port 2576]

Requires: pip install hl7
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
logger = logging.getLogger("yumizen-sim")

# MLLP framing constants
SB = b"\x0b"  # Start Block (VT)
EB = b"\x1c"  # End Block (FS)
CR = b"\x0d"  # Carriage Return

SERIAL_NUMBER = "SIM00001"
SW_VERSION = "4.0.0.0"
SENDING_APP = f"H500/H500E^{SERIAL_NUMBER}^{SW_VERSION}"
SENDING_FACILITY = "HORIBA_MEDICAL"

# ──────────────────────────────────────────────────
#  Sample result data per panel
# ──────────────────────────────────────────────────

# Each entry: (LOINC, name, value, unit, ref_range, flag)
CBC_RESULTS = [
    ("789-8",  "RBC",    "4.85",  "1E06/mm3", "4.20 - 6.00",  "N"),
    ("718-7",  "HGB",    "14.2",  "g/dL",     "12.0 - 17.5",  "N"),
    ("4544-3", "HCT",    "42.1",  "%",        "36.0 - 50.0",  "N"),
    ("787-2",  "MCV",    "86.8",  "fL",       "80.0 - 100.0", "N"),
    ("785-6",  "MCH",    "29.3",  "pg",       "26.0 - 34.0",  "N"),
    ("786-4",  "MCHC",   "33.7",  "g/dL",     "32.0 - 36.0",  "N"),
    ("21000-5","RDW-SD", "42.5",  "fL",       "35.0 - 56.0",  "N"),
    ("788-0",  "RDW-CV", "13.1",  "%",        "11.0 - 16.0",  "N"),
    ("777-3",  "PLT",    "245",   "1E03/mm3", "150 - 400",     "N"),
    ("51637-7","PCT",    "0.22",  "%",        "0.15 - 0.40",  "N"),
    ("51631-0","PDW",    "12.3",  "fL",       "9.0 - 17.0",   "N"),
    ("32623-1","MPV",    "9.8",   "fL",       "7.4 - 10.4",   "N"),
    ("96354-6","P-LCC",  "62",    "1E03/mm3", "30 - 90",       "N"),
    ("48386-7","P-LCR",  "25.3",  "%",        "15.0 - 35.0",  "N"),
    ("6690-2", "WBC",    "7.2",   "1E03/mm3", "4.0 - 10.0",   "N"),
]

DIF_RESULTS = [
    ("731-0",  "LYM#",  "2.1",  "1E03/mm3", "1.0 - 3.5",  "N"),
    ("736-9",  "LYM%",  "29.2", "%",        "20.0 - 40.0", "N"),
    ("742-7",  "MON#",  "0.5",  "1E03/mm3", "0.2 - 1.0",  "N"),
    ("5905-5", "MON%",  "6.9",  "%",        "2.0 - 10.0",  "N"),
    ("751-8",  "NEU#",  "4.1",  "1E03/mm3", "1.5 - 7.0",  "N"),
    ("770-8",  "NEU%",  "56.9", "%",        "40.0 - 70.0", "N"),
    ("711-2",  "EOS#",  "0.3",  "1E03/mm3", "0.0 - 0.5",  "N"),
    ("713-8",  "EOS%",  "4.2",  "%",        "1.0 - 6.0",   "N"),
    ("704-7",  "BAS#",  "0.05", "1E03/mm3", "0.0 - 0.1",  "N"),
    ("706-2",  "BAS%",  "0.7",  "%",        "0.0 - 2.0",   "N"),
    ("53115-2","IMG#",  "0.02", "1E03/mm3", "0.0 - 0.1",  "N"),
    ("71695-1","IMG%",  "0.3",  "%",        "0.0 - 2.0",   "N"),
    ("43743-4","ALY#",  "0.1",  "1E03/mm3", "0.0 - 0.2",  "N"),
    ("42250-1","ALY%",  "1.4",  "%",        "0.0 - 2.0",   "N"),
    ("55432-9","LIC#",  "0.03", "1E03/mm3", "0.0 - 0.2",  "N"),
    ("55433-7","LIC%",  "0.4",  "%",        "0.0 - 2.0",   "N"),
]

ESR_RESULTS = [
    ("82477-1", "ESR", "8", "mm/h", "0 - 20", "N"),
]

PANEL_MAP = {
    "CBC": CBC_RESULTS,
    "DIF": DIF_RESULTS,
    "ESR": ESR_RESULTS,
}


def _now() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _control_id() -> str:
    now = _now()
    counter = f"{random.randint(1, 99999):05d}"
    return f"{now[2:]}{counter}"  # YYMMDDhhmmss + 5-digit counter (17 chars)


# ──────────────────────────────────────────────────
#  MLLP low-level helpers
# ──────────────────────────────────────────────────

async def mllp_connect(host: str, port: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Open a raw TCP connection (we do MLLP framing manually)."""
    reader, writer = await asyncio.open_connection(host, port)
    return reader, writer


def mllp_encode(hl7_message: str) -> bytes:
    """Wrap an HL7 message in MLLP framing: <VT> message <FS><CR>"""
    return SB + hl7_message.encode("utf-8") + EB + CR


async def mllp_send(writer: asyncio.StreamWriter, hl7_message: str):
    """Send an MLLP-framed HL7 message."""
    writer.write(mllp_encode(hl7_message))
    await writer.drain()


async def mllp_receive(reader: asyncio.StreamReader) -> str:
    """Read one MLLP-framed HL7 message. Returns the raw HL7 string."""
    # Read until we see the SB byte
    while True:
        byte = await reader.readexactly(1)
        if byte == SB:
            break

    # Read until EB + CR
    buf = bytearray()
    while True:
        byte = await reader.readexactly(1)
        if byte == EB:
            # Read the trailing CR
            await reader.readexactly(1)
            break
        buf.extend(byte)

    return buf.decode("utf-8")


# ──────────────────────────────────────────────────
#  HL7 Message Builders
# ──────────────────────────────────────────────────

def build_orl_o34(incoming_msh_control_id: str) -> str:
    """
    Build an ORL^O34 acknowledgment for an OML^O33 order.
    Structure: MSH | MSA
    """
    now = _now()
    ctrl = _control_id()
    segments = [
        (
            f"MSH|^~\\&|{SENDING_APP}|{SENDING_FACILITY}"
            f"|||{now}||ORL^O34^ORL_O34|{ctrl}|P|2.5||||||UNICODE UTF-8"
        ),
        f"MSA|AA|{incoming_msh_control_id}",
    ]
    return "\r".join(segments)


def build_oul_r22(
    patient_id: str,
    patient_name: str,
    specimen_id: str,
    panel: str,
    results: list[tuple[str, str, str, str, str, str]],
) -> str:
    """
    Build an OUL^R22 result message for one panel.

    Structure per RAA085BEN §4.1.2.3:
        MSH | PID | SPM | [OBX age] | [OBX dosage] | OBR | [ORC] | {OBX results}
    """
    now = _now()
    ctrl = _control_id()

    segments = []

    # MSH
    segments.append(
        f"MSH|^~\\&|{SENDING_APP}|{SENDING_FACILITY}"
        f"|||{now}||OUL^R22^OUL_R22|{ctrl}|P|2.5||||||UNICODE UTF-8"
    )

    # PID
    name_parts = patient_name.split(" ", 1) if patient_name else ["", ""]
    last = name_parts[1] if len(name_parts) > 1 else ""
    first = name_parts[0]
    segments.append(f"PID|1||{patient_id}^^^^PI||{last}^{first}||19800926000000|U")

    # SPM
    segments.append(f"SPM|1|{specimen_id}||WB||||||P||||||{now}|{now}")

    # OBX linked to SPM — patient age
    segments.append("OBX|1|NM|35659-2^Age at specimen collection^LN||36|a|||||F")

    # OBX linked to SPM — dosage category
    segments.append("OBX|1|ST|^Dosage category||CHILD8_MAN||||||F")

    # OBR — panel header
    segments.append(
        f"OBR|1|||{panel}|||||||||||789456^SIMULATOR PHYSICIAN||||||{now}|||F|||||||||SimUser"
    )

    # ORC
    segments.append("ORC|SC")

    # OBX — one per result parameter
    for idx, (loinc, name, value, unit, ref_range, flag) in enumerate(results, start=1):
        ref_field = f"{ref_range}^REFERENCE_RANGE" if ref_range else ""
        flag_field = f"{flag}~" if flag else ""
        segments.append(
            f"OBX|{idx}|NM|{loinc}^{name}^LN||{value}|{unit}|{ref_field}|{flag_field}||F|||||SimUser|||{now}"
        )

    return "\r".join(segments)


def parse_order_panels(hl7_msg: str) -> tuple[str | None, str | None, str | None, list[str]]:
    """
    Parse an OML^O33 message and extract patient_id, patient_name, specimen_id,
    and the list of requested panel codes.
    """
    patient_id = None
    patient_name = None
    specimen_id = None
    panels: list[str] = []

    for line in hl7_msg.split("\r"):
        if not line.strip():
            continue
        fields = line.split("|")
        seg_type = fields[0]

        if seg_type == "PID":
            # PID-3: patient_id^^^^PI
            if len(fields) > 3:
                pid3 = fields[3]
                patient_id = pid3.split("^")[0] if pid3 else None
            # PID-5: last^first
            if len(fields) > 5:
                patient_name = fields[5].replace("^", " ").strip() if fields[5] else None

        elif seg_type == "SPM":
            # SPM-2: specimen ID
            if len(fields) > 2:
                specimen_id = fields[2] if fields[2] else None

        elif seg_type == "OBR":
            # OBR-4: universal service identifier (panel code)
            if len(fields) > 4:
                panel_code = fields[4].split("^")[0].strip()
                if panel_code:
                    panels.append(panel_code)

    return patient_id, patient_name, specimen_id, panels


def extract_msh_control_id(hl7_msg: str) -> str:
    """Extract MSH-10 (Message Control ID) from an HL7 message."""
    for line in hl7_msg.split("\r"):
        fields = line.split("|")
        if fields[0] == "MSH":
            # MSH fields are offset by 1 because MSH-1 is the field separator itself
            if len(fields) > 9:
                return fields[9]
    return "UNKNOWN"


# ──────────────────────────────────────────────────
#  Main simulator logic
# ──────────────────────────────────────────────────

async def run_simulator(host: str, oru_port: int, orm_port: int):
    """
    Run the Yumizen H500 simulator.

    1. Connect to the ORU (results) port
    2. Connect to the ORM (orders) port
    3. Wait for orders on ORM, send ACK, then push results on ORU
    """
    logger.info(f"Connecting to ORU server at {host}:{oru_port} ...")
    oru_reader, oru_writer = await mllp_connect(host, oru_port)
    logger.info(f"Connected to ORU (results) port {oru_port}")

    logger.info(f"Connecting to ORM server at {host}:{orm_port} ...")
    orm_reader, orm_writer = await mllp_connect(host, orm_port)
    logger.info(f"Connected to ORM (orders) port {orm_port}")

    logger.info("Simulator ready — waiting for orders on ORM socket ...")
    logger.info("(Send an OML^O33 order from CARE to trigger a response)\n")

    try:
        while True:
            # Wait for an OML^O33 order on the ORM socket
            try:
                order_msg = await mllp_receive(orm_reader)
            except asyncio.IncompleteReadError:
                logger.warning("ORM connection closed by server")
                break

            logger.info(f"Received order message ({len(order_msg)} bytes)")
            for line in order_msg.split("\r"):
                if line.strip():
                    logger.info(f"  <- {line}")

            msh_ctrl = extract_msh_control_id(order_msg)

            # Parse the order
            patient_id, patient_name, specimen_id, panels = parse_order_panels(order_msg)
            logger.info(
                f"Order details: patient={patient_id}, specimen={specimen_id}, panels={panels}"
            )

            # Send ORL^O34 acknowledgment on the ORM socket
            orl = build_orl_o34(msh_ctrl)
            logger.info("Sending ORL^O34 acknowledgment ...")
            for line in orl.split("\r"):
                if line.strip():
                    logger.info(f"  -> {line}")
            await mllp_send(orm_writer, orl)

            # Small delay to simulate analysis time
            delay = random.uniform(1.0, 3.0)
            logger.info(f"Simulating analysis ({delay:.1f}s) ...")
            await asyncio.sleep(delay)

            # Default values for missing fields
            patient_id = patient_id or "SIMPAT001"
            patient_name = patient_name or "Simulator Patient"
            specimen_id = specimen_id or f"SPEC{random.randint(1000, 9999)}"

            # If no panels specified, default to CBC
            if not panels:
                panels = ["CBC"]

            # Send OUL^R22 results for each requested panel on the ORU socket
            for panel in panels:
                panel_upper = panel.upper()
                results = PANEL_MAP.get(panel_upper)
                if not results:
                    logger.warning(f"Unknown panel '{panel}', skipping")
                    continue

                # Add slight random variation to make results look realistic
                varied = _vary_results(results)

                oul = build_oul_r22(patient_id, patient_name, specimen_id, panel_upper, varied)
                logger.info(f"Sending OUL^R22 results for panel {panel_upper} ...")
                for line in oul.split("\r"):
                    if line.strip():
                        logger.info(f"  -> {line}")

                await mllp_send(oru_writer, oul)

                # Wait for ACK^R22 from the server
                try:
                    ack_msg = await asyncio.wait_for(mllp_receive(oru_reader), timeout=10.0)
                    logger.info(f"Received ACK for {panel_upper}:")
                    for line in ack_msg.split("\r"):
                        if line.strip():
                            logger.info(f"  <- {line}")
                except asyncio.TimeoutError:
                    logger.warning(f"No ACK received for {panel_upper} within timeout")

            logger.info("Order processing complete. Waiting for next order ...\n")

    except KeyboardInterrupt:
        logger.info("Shutting down simulator ...")
    except Exception as e:
        logger.error(f"Simulator error: {e}", exc_info=True)
    finally:
        oru_writer.close()
        orm_writer.close()
        try:
            await oru_writer.wait_closed()
            await orm_writer.wait_closed()
        except Exception:
            pass
        logger.info("Simulator disconnected.")


def _vary_results(
    results: list[tuple[str, str, str, str, str, str]],
) -> list[tuple[str, str, str, str, str, str]]:
    """Add small random variation to numeric values for realism."""
    varied = []
    for loinc, name, value, unit, ref_range, flag in results:
        try:
            v = float(value)
            # ±5% variation
            v *= random.uniform(0.95, 1.05)
            # Maintain same decimal precision
            if "." in value:
                decimals = len(value.split(".")[1])
                value_str = f"{v:.{decimals}f}"
            else:
                value_str = str(int(round(v)))

            # Recompute flag based on reference range
            new_flag = _compute_flag(v, ref_range)
            varied.append((loinc, name, value_str, unit, ref_range, new_flag))
        except (ValueError, TypeError):
            varied.append((loinc, name, value, unit, ref_range, flag))
    return varied


def _compute_flag(value: float, ref_range: str) -> str:
    """Compute abnormal flag based on reference range string like '4.20 - 6.00'."""
    if not ref_range or " - " not in ref_range:
        return "N"
    try:
        parts = ref_range.split(" - ")
        low = float(parts[0].strip())
        high = float(parts[1].strip())
        if value < low:
            return "L"
        elif value > high:
            return "H"
        return "N"
    except (ValueError, IndexError):
        return "N"


def main():
    parser = argparse.ArgumentParser(
        description="Yumizen H500 lab analyzer simulator (HL7 v2.5 / MLLP)"
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Gateway host to connect to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--oru-port", type=int, default=2575,
        help="ORU (results) MLLP port (default: 2575)"
    )
    parser.add_argument(
        "--orm-port", type=int, default=2576,
        help="ORM (orders) MLLP port (default: 2576)"
    )
    args = parser.parse_args()

    asyncio.run(run_simulator(args.host, args.oru_port, args.orm_port))


if __name__ == "__main__":
    main()
