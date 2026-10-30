"""Load and check the agent's mapping.json against the inventory keys and the schema.

Every problem is collected, so one run tells the agent everything to fix.
"""
import json

import ifcopenshell
import ifcopenshell.ifcopenshell_wrapper as w

from .errors import R2IError

SCHEMAS = ("IFC4", "IFC4X3_ADD2")
CONFIDENCE = ("high", "medium", "low")
NOT_ELEMENTS = ("IfcFeatureElement", "IfcVirtualElement")  # openings, projections, virtual


def element_class(schema, name):
    """(canonical name, declaration) if name is a concrete IfcElement subtype that
    is a physical element (not a feature or virtual element), else None."""
    if not isinstance(name, str):
        return None
    try:
        decl = ifcopenshell.schema_by_name(schema).declaration_by_name(name)
    except (RuntimeError, TypeError):
        return None
    if not isinstance(decl, w.entity) or decl.is_abstract():
        return None
    sup = decl
    while sup is not None:
        if sup.name() in NOT_ELEMENTS:
            return None
        if sup.name() == "IfcElement":
            return decl.name(), decl
        sup = sup.supertype()
    return None


def predefined_types(decl):
    """Allowed PredefinedType values, or None when the class has no such attribute."""
    for attr in decl.all_attributes():
        if attr.name() == "PredefinedType":
            return set(attr.type_of_attribute().declared_type().enumeration_items())
    return None


def _refuse(problems):
    raise R2IError(2, "mapping has %d problem(s)" % len(problems),
                   "fix each entry and rerun convert", problems=problems)


def load(path, keys, parents):
    """keys: the inventory keys; parents: {mixed key: [its cluster keys]}. A mixed
    key is mapped either itself or through all of its clusters, never both."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise R2IError(2, "cannot read mapping %s: %s" % (path, exc), "write valid JSON")
    if not isinstance(data, dict):
        _refuse(['top level must be an object: {"schema": ..., "entries": [...]}'])
    schema = data.get("schema", "IFC4")
    if schema not in SCHEMAS:
        raise R2IError(2, "schema %r is not one of %s" % (schema, ", ".join(SCHEMAS)),
                       'set "schema" to "IFC4" (default) or "IFC4X3_ADD2"')
    raw_entries = data.get("entries", [])
    if not isinstance(raw_entries, list):
        _refuse(["entries must be a list of objects"])
    problems = []
    entries, seen = {}, set()
    allowed = set(keys) | set(parents)
    for i, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            problems.append("entry %d: not an object" % i)
            continue
        key = raw.get("key")
        where = "entry %d (%s)" % (i, key)
        if not isinstance(key, str):
            problems.append("%s: key must be a string" % where)
            continue
        if key in seen:
            problems.append("%s: key listed twice" % where)
            continue
        seen.add(key)
        if key not in allowed:
            problems.append("%s: not an inventory key" % where)
            continue
        entry = _check(schema, raw, where, problems)
        if entry:
            entries[key] = entry
    covered = set(seen)
    for parent, clusters in sorted(parents.items()):
        if parent in seen:
            both = sorted(c for c in clusters if c in seen)
            if both:
                problems.append("%s: map the whole key or its clusters %s, not both (also "
                                "listed: %s)" % (parent, ", ".join(clusters), ", ".join(both)))
            covered.update(clusters)
    for key in sorted(set(keys) - covered):
        parent = next((p for p, cs in parents.items() if key in cs), None)
        also = " (or map all of %s at once with key %r)" % (parent, parent) if parent else ""
        problems.append("%s: missing; classify it or add {\"key\": %r, \"skip\": true, "
                        "\"rationale\": ...}%s" % (key, key, also))
    if problems:
        _refuse(problems)
    return {"schema": schema, "entries": entries}


def _check(schema, raw, where, problems):
    if not isinstance(raw.get("rationale"), str) or not raw["rationale"].strip():
        problems.append("%s: rationale missing" % where)
    if raw.get("skip"):
        return {"key": raw["key"], "skip": True, "rationale": raw.get("rationale", "")}
    found = element_class(schema, raw.get("class"))
    if not found:
        problems.append("%s: %r is not a concrete IfcElement subtype in %s (openings, "
                        "projections and virtual elements are not)" % (where, raw.get("class"), schema))
        return None
    name, decl = found
    if raw.get("confidence") not in CONFIDENCE:
        problems.append("%s: confidence must be one of %s" % (where, ", ".join(CONFIDENCE)))
    ptype = raw.get("predefinedType")
    ptype = ptype.upper() if isinstance(ptype, str) else None
    allowed = predefined_types(decl)
    if ptype and allowed is None:
        problems.append("%s: %s has no PredefinedType" % (where, name))
    elif ptype and ptype not in allowed:
        problems.append("%s: PredefinedType %s not in %s" % (where, ptype, sorted(allowed)))
    if ptype == "USERDEFINED" and not raw.get("objectType"):
        problems.append("%s: USERDEFINED needs objectType" % where)
    return {"key": raw["key"], "skip": False, "class": name, "predefinedType": ptype,
            "objectType": raw.get("objectType"), "merge": bool(raw.get("merge", False)),
            "confidence": raw.get("confidence"), "rationale": raw.get("rationale", "")}
