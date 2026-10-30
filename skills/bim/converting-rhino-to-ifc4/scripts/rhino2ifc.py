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

from r2i import inventory, model
from r2i.errors import R2IError


def emit(doc):
    print(json.dumps(doc, ensure_ascii=False, indent=2))


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
    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except R2IError as exc:
        emit({"ok": False, "error": exc.to_json()})
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
