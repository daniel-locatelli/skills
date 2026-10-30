#!/usr/bin/env python3
"""Rhino .3dm -> IFC4 (or IFC4X3_ADD2), classified by an agent.

  rhino2ifc.py inventory <in.3dm> [-o inventory.json]
  rhino2ifc.py convert <in.3dm> <mapping.json> -o <out.ifc>
               [--storeys [z1,z2,...]] [--georef EPSG:<code>,<E>,<N>,<H>[,<rot_deg>]]
               [--north <layer path>]
  rhino2ifc.py validate <file.ifc>

JSON on stdout for every outcome. Exit 0 ok, 2 input error, 3 objects
without a cached mesh, 4 validation failed.
"""
import argparse
import json
import sys

from r2i import checks, inventory, mapping, model, writer
from r2i.errors import R2IError


def emit(doc):
    print(json.dumps(doc, ensure_ascii=False, indent=2))


def parse_levels(text):
    if text == "auto":
        return "auto"
    try:
        return [float(x) for x in text.split(",")]
    except ValueError:
        raise R2IError(2, "--storeys %r is not a list of numbers" % text,
                       "use --storeys alone, or --storeys 0,3.2,6.4")


def parse_georef(text):
    try:
        crs, *nums = text.split(",")
        if not crs.upper().startswith("EPSG:") or len(nums) not in (3, 4):
            raise ValueError
        vals = [float(x) for x in nums] + ([0.0] if len(nums) == 3 else [])
        return (int(crs[5:]), *vals)
    except ValueError:
        raise R2IError(2, "--georef %r is malformed" % text,
                       "use EPSG:<code>,<E>,<N>,<H>[,<rotation deg>], e.g. EPSG:2056,2600000,1200000,400")


def cmd_inventory(args):
    doc, _ = inventory.build(model.read(args.model))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
        emit({"ok": "error" not in doc, "output": args.output, "keys": len(doc["keys"]),
              "objectCount": doc["objectCount"], **({"error": doc["error"]} if "error" in doc else {})})
    else:
        emit(doc)
    return 3 if "error" in doc else 0


def cmd_convert(args):
    m = model.read(args.model)
    _, groups = inventory.build(m)
    mp = mapping.load(args.mapping, set(groups))
    storeys = parse_levels(args.storeys) if args.storeys else None
    georef = parse_georef(args.georef) if args.georef else None
    emit(writer.convert(m, groups, mp, args.output, storeys=storeys, georef=georef,
                        north_layer=args.north))
    return 0


def cmd_validate(args):
    result = checks.validate(args.ifc)
    emit(result)
    return 0 if result["ok"] else 4


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="rhino2ifc", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("inventory")
    s.add_argument("model")
    s.add_argument("-o", "--output")
    s.set_defaults(fn=cmd_inventory)
    s = sub.add_parser("convert")
    s.add_argument("model")
    s.add_argument("mapping")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--storeys", nargs="?", const="auto")
    s.add_argument("--georef")
    s.add_argument("--north")
    s.set_defaults(fn=cmd_convert)
    s = sub.add_parser("validate")
    s.add_argument("ifc")
    s.set_defaults(fn=cmd_validate)
    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except R2IError as exc:
        emit({"ok": False, "error": exc.to_json()})
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
