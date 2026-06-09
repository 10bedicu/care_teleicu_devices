#!/usr/bin/env python3
"""
ADX HEME 340 Auto Hematology Analyzer simulator.

Simulates unidirectional HL7 v2.3.1 MLLP communication:
  - Connects to the gateway's ORU port (results, default 2575)
  - Prompts user for sample ID
  - Generates randomized CBC results
  - Sends ORU^R01 message and waits for ACK^R01

Usage:
    python scripts/simulate_adx_heme_340.py [--host 127.0.0.1] [--port 2575]

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
logger = logging.getLogger("adx-heme-340-sim")

# MLLP framing constants
SB = b"\x0b"  # Start Block (VT) 0x0B
EB = b"\x1c"  # End Block (FS) 0x1C
CR = b"\x0d"  # Carriage Return 0x0D

# ──────────────────────────────────────────────────
#  CBC result parameters (3-part diff)
#  Matches actual ADX HEME 340 output format exactly.
#  Each entry: (name, base_value, unit, ref_low, ref_high, decimals)
# ──────────────────────────────────────────────────

CBC_PARAMETERS = [
    ("WBC",    7.2,    "10^3/uL",  4,     10,    1),
    ("Lymph#", 2.1,    "10^9/L",   0.8,   4,     1),
    ("Mid#",   0.5,    "10^9/L",   0.1,   1.5,   1),
    ("Gran#",  4.6,    "10^9/L",   2,     7,     1),
    ("Lymph%", 29.2,   "%",        20,    40,    1),
    ("Mid%",   6.9,    "%",        3,     15,    1),
    ("Gran%",  60.0,   "%",        50,    70,    1),
    ("RBC",    4.50,   "10^6/uL",  3.5,   5.5,   2),
    ("HGB",    13.5,   "g/dL",     11,    16,    1),
    ("HCT",    42.1,   "%",        37,    54,    1),
    ("MCV",    86.8,   "fL",       80,    100,   1),
    ("MCH",    29.3,   "pg",       27,    34,    1),
    ("MCHC",   33.7,   "g/dL",     32,    36,    1),
    ("RDW-CV", 13.1,   "%",        11,    16,    1),
    ("RWD-SD", 42.5,   "fL",       35,    56,    1),
    ("PLT",    245,    "10^3/uL",  100,   300,   0),
    ("MPV",    9.8,    "fL",       6.5,   12,    1),
    ("PDW",    15.8,   "",         15,    17,    1),
    ("PCT",    0.200,  "%",        0.108, 0.282, 3),
    ("PLCC",   62,     "10^9/L",   30,    90,    0),
    ("PLCR",   25.3,   "%",        11,    45,    1),
]


def _now() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


# Global message counter (mimics real device behavior)
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
#  HL7 Message Builder
# ──────────────────────────────────────────────────

def _compute_flag(value: float, ref_low: float, ref_high: float) -> str:
    """
    Compute abnormal flag per ADX HEME 340 convention:
      N  = normal
      H  = high (slightly above range)
      L  = low (slightly below range)
      RH = review high (significantly above range, >15% beyond upper limit)
      RL = review low (significantly below range, >15% beyond lower limit)
    """
    if value > ref_high:
        # Check if significantly out of range (>15% beyond boundary)
        if ref_high > 0 and (value - ref_high) / ref_high > 0.15:
            return "RH"
        return "H"
    elif value < ref_low:
        if ref_low > 0 and (ref_low - value) / ref_low > 0.15:
            return "RL"
        return "L"
    return "N"


def _vary_value(base: float, decimals: int) -> float:
    """Add ±10% random variation to a base value."""
    return round(base * random.uniform(0.90, 1.10), decimals)


def build_oru_r01(sample_id: str, patient_name: str = "", operator: str = "Admin") -> str:
    """
    Build an ORU^R01 message per ADX HEME 340 HL7 v2.3.1 protocol.

    Matches actual device output format:
        MSH
        PID
        PV1
        OBR
        {OBX}  (one per result parameter)
    """
    now = _now()
    msg_id = _next_message_id()

    segments = []

    # MSH — Message Header
    segments.append(
        f"MSH|^~\\&|||||{now}||ORU^R01|{msg_id}|P|2.3.1||||||UNICODE||"
    )

    # PID — Patient Identification (field 5 = patient name)
    segments.append(
        f"PID|{msg_id}||||{patient_name}|||"
    )

    # PV1 — Patient Visit
    segments.append(
        f"PV1|{msg_id}||"
    )

    # OBR — Observation Request
    testing_time = now
    segments.append(
        f"OBR|{msg_id}||{sample_id}||||{testing_time}|||||||||||||||||HM||||||||{operator}"
    )

    # OBX — one per result parameter, with running Set ID
    # OBX Set IDs are a running counter: (msg_id - 1) * num_params + param_index
    num_params = len(CBC_PARAMETERS)
    obx_base = (msg_id - 1) * num_params + 1

    for idx, (name, base_val, unit, ref_low, ref_high, decimals) in enumerate(CBC_PARAMETERS):
        obx_id = obx_base + idx

        value = _vary_value(base_val, decimals)
        flag = _compute_flag(value, ref_low, ref_high)

        # Format value string
        if decimals == 0:
            value_str = str(int(round(value)))
        else:
            value_str = f"{value:.{decimals}f}"

        # Reference range (integers if both bounds are whole numbers, else match decimals)
        if ref_low == int(ref_low) and ref_high == int(ref_high):
            ref_range = f"{int(ref_low)} - {int(ref_high)}"
        else:
            ref_range = f"{ref_low} - {ref_high}"

        segments.append(
            f"OBX|{obx_id}|NM|{name}||{value_str}|{unit}|{ref_range}|{flag}|||F"
        )

    return "\r".join(segments)


# ──────────────────────────────────────────────────
#  Main simulator logic
# ──────────────────────────────────────────────────

async def run_simulator(host: str, port: int):
    """
    Run the ADX HEME 340 simulator (unidirectional — sends results only).

    1. Connect to the gateway ORU port
    2. Prompt user for sample ID
    3. Generate and send ORU^R01 result message
    4. Wait for ACK^R01
    5. Repeat
    """
    logger.info(f"Connecting to gateway at {host}:{port} ...")
    reader, writer = await asyncio.open_connection(host, port)
    logger.info(f"Connected to {host}:{port}")
    logger.info("ADX HEME 340 simulator ready (unidirectional — sends results only)")
    logger.info("Type a sample ID and press Enter to send results. Type 'quit' to exit.\n")

    loop = asyncio.get_event_loop()

    try:
        while True:
            # Read sample ID from stdin (non-blocking)
            sample_id = await loop.run_in_executor(
                None, lambda: input("Enter sample ID (or 'quit'): ")
            )
            sample_id = sample_id.strip()

            if not sample_id:
                continue
            if sample_id.lower() == "quit":
                break

            # Optional: prompt for patient name
            patient_name = await loop.run_in_executor(
                None, lambda: input("Patient name (optional, press Enter to skip): ")
            )
            patient_name = patient_name.strip()

            # Build ORU^R01 message
            oru_msg = build_oru_r01(sample_id, patient_name=patient_name)

            logger.info(f"Sending ORU^R01 for sample '{sample_id}' ...")
            for line in oru_msg.split("\r"):
                if line.strip():
                    logger.info(f"  -> {line}")

            await mllp_send(writer, oru_msg)

            # Wait for ACK^R01 from gateway
            try:
                ack_msg = await asyncio.wait_for(mllp_receive(reader), timeout=10.0)
                logger.info("Received ACK^R01:")
                for line in ack_msg.split("\r"):
                    if line.strip():
                        logger.info(f"  <- {line}")
                # Verify acknowledgment
                if "MSA|AA" in ack_msg:
                    logger.info("Result accepted by gateway.\n")
                elif "MSA|AE" in ack_msg:
                    logger.warning("Gateway returned Application Error.\n")
                else:
                    logger.warning("Unexpected ACK response.\n")
            except asyncio.TimeoutError:
                logger.warning("No ACK received within 10s timeout.\n")
            except asyncio.IncompleteReadError:
                logger.error("Connection closed by gateway.")
                break

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


def main():
    parser = argparse.ArgumentParser(
        description="ADX HEME 340 Auto Hematology Analyzer simulator (HL7 v2.3.1 / MLLP, unidirectional)"
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Gateway host to connect to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=2575,
        help="ORU (results) MLLP port (default: 2575)"
    )
    args = parser.parse_args()

    asyncio.run(run_simulator(args.host, args.port))


if __name__ == "__main__":
    main()
