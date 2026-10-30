"""Validate a written IFC and report what is in it."""
from collections import Counter

import ifcopenshell
import ifcopenshell.validate

from .errors import R2IError


def validate(path):
    try:
        f = ifcopenshell.open(str(path))
    except Exception as exc:  # ifcopenshell raises several types for unreadable files
        raise R2IError(2, "cannot open %s: %s" % (path, exc), "check the path")
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(f, logger)
    errors = [s["message"] for s in logger.statements if s.get("level") == "error"]
    elements = f.by_type("IfcElement")
    no_geometry = [e.GlobalId for e in elements if not e.Representation]
    header = f.header.file_name
    result = {
        "ok": not errors and not no_geometry,
        "schema": f.schema_identifier,
        "elements": dict(Counter(e.is_a() for e in elements)),
        "schemaErrors": errors[:20],
        "schemaErrorCount": len(errors),
        "withoutGeometry": no_geometry,
        "identity": {t: len(f.by_type(t)) for t in ("IfcOwnerHistory", "IfcPerson",
                                                     "IfcOrganization")},
        "header": {"author": list(header.author), "organization": list(header.organization)},
    }
    return result
