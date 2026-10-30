"""Group items into mapping keys and summarise each key for the agent.

A key is a layer path or a block definition name. A key is mixed when two or
more forms each hold at least MIXED_SHARE of its meshed objects; it is then
split into clusters `<key>#1..n`, one per such form (largest first, ties by
form name), and objects of rarer forms join cluster 1. The agent maps the
cluster keys, never the mixed key itself.
"""
from collections import Counter

import numpy as np

from . import shape

MIXED_SHARE = 0.1


def resolve(model):
    """(records, groups): records for inventory.json; groups maps every
    mapping key to its [(item, stats)] (stats None when the mesh is missing)."""
    by_key = {}
    for item in model.items:
        by_key.setdefault(item.key, []).append(item)

    records, groups = [], {}
    for key, items in by_key.items():
        rows = [(it, shape.stats(shape.points(it.mesh, model.scale)) if it.mesh is not None else None)
                for it in items]
        meshed = [(it, st) for it, st in rows if st is not None]
        record = {
            "key": key,
            "kind": items[0].kind,
            "layer": items[0].layer if items[0].kind == "layer" else None,
            "count": len({it.object_id for it in items}),
            "geometryTypes": dict(Counter(it.geometry_type for it in items)),
            "colour": list(model.layer_colours.get(key, items[0].colour)),
            "missingMesh": [{"key": key, "objectId": it.object_id, "geometryType": it.geometry_type}
                            for it, st in rows if st is None],
        }
        record.update(_describe(meshed))
        forms = Counter(st["form"] for _, st in meshed)
        main = sorted((f for f, n in forms.items() if n >= MIXED_SHARE * len(meshed)),
                      key=lambda f: (-forms[f], f))
        if len(main) >= 2:
            record["clusters"] = []
            members = {f: [] for f in main}
            for it, st in meshed:
                members[st["form"] if st["form"] in members else main[0]].append((it, st))
            for i, f in enumerate(main, 1):
                ckey = "%s#%d" % (key, i)
                groups[ckey] = members[f]
                record["clusters"].append(dict({"key": ckey, "form": f,
                                                "count": len(members[f])}, **_describe(members[f])))
            groups.setdefault(key + "#1", []).extend((it, st) for it, st in rows if st is None)
        else:
            groups[key] = rows
        records.append(record)
    return records, groups


def _describe(rows):
    if not rows:
        return {}
    stats = [st for _, st in rows]
    lo = np.min([st["bbox"][0] for st in stats], axis=0)
    hi = np.max([st["bbox"][1] for st in stats], axis=0)
    return {
        "bbox": {"min": [round(float(x), 3) for x in lo], "max": [round(float(x), 3) for x in hi]},
        "forms": dict(Counter(st["form"] for st in stats)),
        "size": {axis: shape.summary([st["size"][i] for st in stats])
                 for i, axis in enumerate(("dx", "dy", "dz"))},
        "slenderness": shape.summary([st["slenderness"] for st in stats]),
        "zMin": shape.summary([st["zMin"] for st in stats]),
        "zMax": shape.summary([st["zMax"] for st in stats]),
    }


def build(model):
    """The inventory.json document and the groups convert needs."""
    records, groups = resolve(model)
    missing = [m for rec in records for m in rec["missingMesh"]]
    all_stats = [st for rows in groups.values() for _, st in rows if st is not None]
    doc = {
        "units": {"model": model.unit, "toMetres": model.scale},
        "objectCount": len({it.object_id for it in model.items}),
        "extent": _describe([(None, st) for st in all_stats]).get("bbox"),
        "keys": sorted(groups),
        "layers": records,
        "nonGeometric": model.non_geometric,
    }
    if missing:
        doc["error"] = {"code": 3, "missingMesh": missing,
                        "fix": "open the .3dm in Rhino and save it normally (not Save Small), "
                               "or mesh those objects via Cordyceps, then rerun inventory"}
    return doc, groups
