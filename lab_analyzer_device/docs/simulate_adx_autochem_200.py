#!/usr/bin/env python3
"""
ADX AutoChem 200 Biochemistry Analyzer simulator.

Simulates host-query HL7 v2.3.1 MLLP communication:
  - Listens on an ORU port (default 2575) for gateway connections
  - Sends QRY^Q02 to query worklist for a barcode
  - Receives QCK^Q02 + DSR^Q03 worklist response
  - Sends ACK^Q03 acknowledgment
  - Generates randomized biochemistry results
  - Sends ORU^R01 and waits for ACK^R01

Usage:
    python simulate_adx_autochem_200.py [--host 127.0.0.1] [--port 2575]

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
logger = logging.getLogger("adx-chem-200-sim")

# MLLP framing constants
SB = b"\x0b"  # Start Block (VT) 0x0B
EB = b"\x1c"  # End Block (FS) 0x1C
CR = b"\x0d"  # Carriage Return 0x0D

# ──────────────────────────────────────────────────
#  Biochemistry test parameters
#  Each entry: (test_id, name, base_value, unit, ref_low, ref_high, decimals)
# ──────────────────────────────────────────────────

# LFT Panel tests
LFT_PARAMETERS = [
    (7,  "BIL T",    0.8,   "mg/dL",   0.1,   1.2,   2),
    (6,  "BIL D",    0.2,   "mg/dL",   0.0,   0.4,   2),
    (3,  "ALT",      28.0,  "U/L",     0,     40,    1),
    (5,  "AST",      24.0,  "U/L",     0,     40,    1),
    (2,  "ALP",      72.0,  "U/L",     30,    120,   1),
    (25, "GGT",      32.0,  "U/L",     8,     61,    1),
    (12, "TP",       7.0,   "g/dL",    6.0,   8.3,   1),
    (1,  "ALB",      4.2,   "g/dL",    3.5,   5.0,   1),
]

# KFT Panel tests
KFT_PARAMETERS = [
    (14, "BUN",      15.0,  "mg/dL",   7,     20,    1),
    (22, "CREA",     0.9,   "mg/dL",   0.6,   1.2,   2),
    (15, "K",        4.2,   "mEq/L",   3.5,   5.0,   1),
    (16, "Na",       140.0, "mEq/L",   136,   145,   0),
    (17, "Ca",       9.5,   "mg/dL",   8.5,   10.5,  1),
    (28, "PO4",      3.5,   "mg/dL",   2.5,   4.5,   1),
    (13, "UA",       5.5,   "mg/dL",   3.4,   7.0,   1),
]

# Lipid Panel tests
LIPID_PARAMETERS = [
    (9,  "CHOL",     190.0, "mg/dL",   0,     200,   0),
    (11, "TG",       130.0, "mg/dL",   0,     150,   0),
    (26, "HDL",      55.0,  "mg/dL",   40,    60,    0),
]

# Other common tests
OTHER_PARAMETERS = [
    (10, "GLU",      95.0,  "mg/dL",   70,    110,   1),
    (18, "CRP",      2.5,   "mg/L",    0,     5,     1),
    (4,  "AMY",      70.0,  "U/L",     25,    125,   0),
    (23, "LIP",      35.0,  "U/L",     0,     60,    0),
    (27, "HbA1c",    5.5,   "%",       4.0,   5.6,   1),
]

# Full panel (all tests)
ALL_PARAMETERS = LFT_PARAMETERS + KFT_PARAMETERS + LIPID_PARAMETERS + OTHER_PARAMETERS

# Panel definitions: panel_name → list of test parameters
PANELS = {
    "LFT": LFT_PARAMETERS,
    "KFT": KFT_PARAMETERS,
    "LIPID": LIPID_PARAMETERS,
    "ALL": ALL_PARAMETERS,
}


def _now() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


# Global message counter
_message_counter = 0


def _next_message_id() -> int:
    global _message_counter
    _message_counter += 1
    return _message_counter


# ──────────────────────────────────────────────────
#  MLLP low-level helpers
# ──────────────────────────────────────────────────

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

def _compute_flag(value: float, ref_low: float, ref_high: float) -> str:
    """Compute abnormal flag: N = normal, H = high, L = low."""
    if ref_high > 0 and value > ref_high:
        return "H"
    elif ref_low > 0 and value < ref_low:
        return "L"
    return "N"


def _vary_value(base: float, decimals: int) -> float:
    """Add ±10% random variation to a base value."""
    return round(base * random.uniform(0.90, 1.10), decimals)


def build_qry_q02(barcode: str) -> str:
    """
    Build a QRY^Q02 query message per ADX AutoChem 200 protocol.

    The analyzer sends this to request worklist info for a given barcode.

    Format:
        MSH
        QRD (query definition — barcode in field 8)
        QRF (query filter — device identifier)
    """
    now = _now()
    msg_id = _next_message_id()

    segments = [
        f"MSH|^~\\&|ADX-CHEM-200|ES-200|||{now}||QRY^Q02|{msg_id}|P|2.3.1||||||UNICODE||",
        f"QRD|{now}|R|D|{msg_id}|||900^CH|{barcode}|OTH|\"\"||T",
        f"QRF|ES-200|{now}|{now}|||RCT|COR|ALL|",
    ]

    return "\r".join(segments)


def build_ack_q03(control_id: str) -> str:
    """
    Build an ACK^Q03 response to acknowledge receipt of DSR^Q03.
    """
    now = _now()
    msg_id = _next_message_id()

    segments = [
        f"MSH|^~\\&|ADX-CHEM-200|ES-200|||{now}||ACK^Q03|{msg_id}|P|2.3.1||||||UNICODE||",
        f"MSA|AA|{control_id}|Message accepted|||0",
        "ERR|0",
    ]

    return "\r".join(segments)


def build_oru_r01(
    sample_id: str,
    barcode: str,
    tests: list[tuple[int, str, float, str, float, float, int]],
    patient_name: str = "",
    gender: str = "",
    date_of_birth: str = "",
) -> str:
    """
    Build an ORU^R01 result message per ADX AutoChem 200 protocol.

    Format:
        MSH
        PID
        OBR
        {OBX}  (one per test result)
    """
    now = _now()
    msg_id = _next_message_id()

    segments = []

    # MSH — Message Header (MSH-16 = 0 for patient samples)
    segments.append(
        f"MSH|^~\\&|ADX-CHEM-200|ES-200|||{now}||ORU^R01|{msg_id}|P|2.3.1||||0||UNICODE||"
    )

    # PID — Patient Identification
    segments.append(
        f"PID|1||\"\"||{patient_name}||{date_of_birth}|{gender}||||||||||||||||||||||"
    )

    # OBR — Observation Request
    segments.append(
        f"OBR|1|{barcode}|{sample_id}|ADX-CHEM-200^ES-200||{now}|{now}"
        f"||||||||Serum||||||||||||||||||||||||||||||||"
    )

    # OBX — one per test result
    for idx, (test_id, test_name, base_val, unit, ref_low, ref_high, decimals) in enumerate(tests, start=1):
        value = _vary_value(base_val, decimals)
        flag = _compute_flag(value, ref_low, ref_high)

        # Format value
        if decimals == 0:
            value_str = str(int(round(value)))
        else:
            value_str = f"{value:.{decimals}f}"

        # Format reference range
        if ref_low == int(ref_low) and ref_high == int(ref_high):
            ref_range = f"{int(ref_low)}-{int(ref_high)}"
        else:
            ref_range = f"{ref_low:.2f}-{ref_high:.2f}"

        # OBX-3 = test_id, OBX-4 = test_name (matches device format)
        segments.append(
            f"OBX|{idx}|NM|{test_id}|{test_name}|{value_str}|{unit}|{ref_range}|{flag}|||F||{value_str}|{now}|||"
        )

    return "\r".join(segments)


def parse_dsr_tests(dsr_message: str) -> list[int]:
    """
    Parse test IDs from a DSR^Q03 response.

    DSP segments 29+ contain test orders in format: test_id^^^
    """
    test_ids = []
    for line in dsr_message.split("\r"):
        if not line.startswith("DSP|"):
            continue
        parts = line.split("|")
        if len(parts) < 4:
            continue
        try:
            field_num = int(parts[1])
        except ValueError:
            continue
        # Test orders start at DSP-29 onwards
        if field_num >= 29:
            data = parts[3].strip()
            if data and "^^^" in data:
                test_id_str = data.split("^")[0]
                if test_id_str.isdigit():
                    test_ids.append(int(test_id_str))
    return test_ids


def parse_dsr_sample_id(dsr_message: str) -> str:
    """Parse sample ID (DSP field 22) from DSR^Q03 response."""
    for line in dsr_message.split("\r"):
        if not line.startswith("DSP|"):
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            try:
                if int(parts[1]) == 22:
                    return parts[3].strip()
            except ValueError:
                pass
    return ""


def parse_dsr_patient_name(dsr_message: str) -> str:
    """Parse patient name (DSP field 3) from DSR^Q03 response."""
    for line in dsr_message.split("\r"):
        if not line.startswith("DSP|"):
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            try:
                if int(parts[1]) == 3:
                    return parts[3].strip()
            except ValueError:
                pass
    return ""


def get_tests_for_ids(test_ids: list[int]) -> list[tuple[int, str, float, str, float, float, int]]:
    """Look up test parameters by their integer IDs."""
    id_to_param = {t[0]: t for t in ALL_PARAMETERS}
    return [id_to_param[tid] for tid in test_ids if tid in id_to_param]


# ──────────────────────────────────────────────────
#  Main simulator logic
# ──────────────────────────────────────────────────

async def run_simulator(host: str, port: int):
    """
    Run the ADX AutoChem 200 simulator (host-query mode).

    Interactive workflow:
      1. Connect to the gateway
      2. User enters a barcode to query
      3. Simulator sends QRY^Q02
      4. Receives QCK^Q02 + DSR^Q03
      5. Sends ACK^Q03
      6. Generates and sends ORU^R01 results
      7. Receives ACK^R01
      8. Repeat

    Alternative: user can type a panel name (LFT, KFT, LIPID, ALL) to send
    results directly without querying the worklist.
    """
    logger.info(f"Connecting to gateway at {host}:{port} ...")
    reader, writer = await asyncio.open_connection(host, port)
    logger.info(f"Connected to {host}:{port}")
    logger.info("ADX AutoChem 200 simulator ready (host-query mode)")
    logger.info("")
    logger.info("Commands:")
    logger.info("  <barcode>          — Query worklist for barcode, then send results")
    logger.info("  send <sample_id> <panel> — Send results directly (panels: LFT, KFT, LIPID, ALL)")
    logger.info("  quit               — Exit simulator")
    logger.info("")

    loop = asyncio.get_event_loop()

    try:
        while True:
            user_input = await loop.run_in_executor(
                None, lambda: input("ADX-CHEM-200> ")
            )
            user_input = user_input.strip()

            if not user_input:
                continue
            if user_input.lower() == "quit":
                break

            # Direct send mode: "send <sample_id> <panel>"
            if user_input.lower().startswith("send "):
                parts = user_input.split()
                if len(parts) < 3:
                    logger.error("Usage: send <sample_id> <panel>")
                    continue
                sample_id = parts[1]
                panel_name = parts[2].upper()
                if panel_name not in PANELS:
                    logger.error(f"Unknown panel '{panel_name}'. Available: {', '.join(PANELS.keys())}")
                    continue

                tests = PANELS[panel_name]
                await _send_results(reader, writer, sample_id, sample_id, tests)
                continue

            # Host-query mode: barcode query
            barcode = user_input
            await _query_and_send(reader, writer, barcode)

    except (KeyboardInterrupt, EOFError):
        logger.info("Shutting down simulator ...")
    except Exception as e:
        logger.error(f"Simulator error: {e}", exc_info=True)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        logger.info("Simulator disconnected.")


async def _query_and_send(reader, writer, barcode: str):
    """Query worklist for a barcode and send results."""

    # Step 1: Send QRY^Q02
    qry_msg = build_qry_q02(barcode)
    logger.info(f"Sending QRY^Q02 for barcode '{barcode}' ...")
    _log_message("->", qry_msg)
    await mllp_send(writer, qry_msg)

    # Step 2: Receive QCK^Q02
    try:
        qck_msg = await asyncio.wait_for(mllp_receive(reader), timeout=10.0)
        logger.info("Received QCK^Q02:")
        _log_message("<-", qck_msg)

        if "QAK|" in qck_msg and "NF" in qck_msg:
            logger.warning("No worklist data found for this barcode.\n")
            return
        if "MSA|AE" in qck_msg or "MSA|AR" in qck_msg:
            logger.warning("Query rejected by LIS.\n")
            return
    except asyncio.TimeoutError:
        logger.warning("No QCK^Q02 received within 10s.\n")
        return
    except asyncio.IncompleteReadError:
        logger.error("Connection closed while waiting for QCK.")
        return

    # Step 3: Receive DSR^Q03
    try:
        dsr_msg = await asyncio.wait_for(mllp_receive(reader), timeout=10.0)
        logger.info("Received DSR^Q03:")
        _log_message("<-", dsr_msg)
    except asyncio.TimeoutError:
        logger.warning("No DSR^Q03 received within 10s.\n")
        return
    except asyncio.IncompleteReadError:
        logger.error("Connection closed while waiting for DSR.")
        return

    # Step 4: Send ACK^Q03
    # Extract control ID from DSR MSH-10
    dsr_control_id = _extract_control_id(dsr_msg)
    ack_msg = build_ack_q03(dsr_control_id)
    logger.info("Sending ACK^Q03 ...")
    _log_message("->", ack_msg)
    await mllp_send(writer, ack_msg)

    # Step 5: Parse worklist and send results
    test_ids = parse_dsr_tests(dsr_msg)
    sample_id = parse_dsr_sample_id(dsr_msg)
    patient_name = parse_dsr_patient_name(dsr_msg)

    if not test_ids:
        logger.warning("No test orders found in DSR response.\n")
        return

    logger.info(f"Worklist: sample_id={sample_id}, tests={test_ids}, patient={patient_name}")

    tests = get_tests_for_ids(test_ids)
    if not tests:
        logger.warning(f"No matching test parameters for IDs: {test_ids}\n")
        return

    await _send_results(reader, writer, sample_id, barcode, tests, patient_name=patient_name)


async def _send_results(
    reader, writer,
    sample_id: str, barcode: str,
    tests: list[tuple[int, str, float, str, float, float, int]],
    patient_name: str = "",
):
    """Generate and send ORU^R01 results, wait for ACK^R01."""

    oru_msg = build_oru_r01(
        sample_id=sample_id,
        barcode=barcode,
        tests=tests,
        patient_name=patient_name,
    )

    test_names = [t[1] for t in tests]
    logger.info(f"Sending ORU^R01: sample={sample_id}, tests={test_names}")
    _log_message("->", oru_msg)
    await mllp_send(writer, oru_msg)

    # Wait for ACK^R01
    try:
        ack_msg = await asyncio.wait_for(mllp_receive(reader), timeout=10.0)
        logger.info("Received ACK^R01:")
        _log_message("<-", ack_msg)

        if "MSA|AA" in ack_msg:
            logger.info("Results accepted.\n")
        elif "MSA|AE" in ack_msg:
            logger.warning("Application error from LIS.\n")
        elif "MSA|AR" in ack_msg:
            logger.warning("Results rejected by LIS.\n")
        else:
            logger.warning("Unexpected ACK response.\n")
    except asyncio.TimeoutError:
        logger.warning("No ACK^R01 received within 10s.\n")
    except asyncio.IncompleteReadError:
        logger.error("Connection closed while waiting for ACK.\n")


def _extract_control_id(message: str) -> str:
    """Extract MSH-10 (message control ID) from an HL7 message."""
    for line in message.split("\r"):
        if line.startswith("MSH|"):
            fields = line.split("|")
            if len(fields) > 10:
                return fields[10]
    return "1"


def _log_message(direction: str, message: str):
    """Log each segment of an HL7 message."""
    for line in message.split("\r"):
        if line.strip():
            logger.info(f"  {direction} {line}")


def main():
    parser = argparse.ArgumentParser(
        description="ADX AutoChem 200 Biochemistry Analyzer simulator (HL7 v2.3.1 / MLLP, host-query)"
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Gateway host to connect to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=2575,
        help="MLLP port (default: 2575)"
    )
    args = parser.parse_args()

    asyncio.run(run_simulator(args.host, args.port))


if __name__ == "__main__":
    main()
