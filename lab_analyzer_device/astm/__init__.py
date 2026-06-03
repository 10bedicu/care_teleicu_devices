"""ASTM (E1381/E1394) protocol support for lab analyzer devices.

Parallels the :mod:`lab_analyzer_device.hl7` package: device profiles parse
ASTM result records into the shared :class:`~lab_analyzer_device.hl7.extractor.ORUData`
payload, so the downstream DiagnosticReport pipeline is protocol-agnostic.
"""
