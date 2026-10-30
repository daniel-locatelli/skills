"""Group items into mapping keys and summarise each key for the agent.

A key is a layer path or `block:<definition name>`. Statistics, forms and
counts are per object: a Rhino object, or a block instance with all its
exploded parts as one vertex set. A key is mixed when two or more forms each
hold at least MIXED_SHARE of its meshed objects; it is then split into
clusters `<key>#1..n`, one per such form (largest first, ties by form name),
and objects of rarer forms join cluster 1. The agent maps either the mixed
key itself (all its objects, one class) or every one of its clusters;
`parentKeys` lists the clusters of each mixed key.
"""
from collections import Counter

import numpy as np

from . import shape

MIXED_SHARE = 0.1


def _objects(items, scale):
    """[(parts, stats)] per Rhino object or block instance; stats None when a part has no mesh."""
    by_object = {}
    for it in items:
        by_object.setdefault(it.object_id, []).append(it)
    out = []
    for parts in by_object.values():
        if any(it.mesh is None for it in parts):
            out.append((parts, None))
        else:
            pts = np.concatenate([shape.points(it.mesh, scale) for it in parts])
            out.append((parts, shape.stats(pts)))
    return out


def _rows(objects):
    """[(item, stats)]: every part carries the stats of its object."""
    return [(it, st) for parts, st in objects for it in parts]


def resolve(model):
    """(records, groups, parents): records for inventory.json; groups maps every
    mapping key, mixed keys included, to its [(item, stats)] (stats None when
    the object lacks a mesh); parents maps each mixed key to its cluster keys."""
    by_key = {}
    for item in model.items:
        by_key.setdefault(item.key, []).append(item)

    records, groups, parents = [], {}, {}
    for key, items in by_key.items():
        objects = _objects(items, model.scale)
        meshed = [(parts, st) for parts, st in objects if st is not None]
        record = {
            "key": key,
            "kind": items[0].kind,
            "layer": items[0].layer if items[0].kind == "layer" else None,
            "count": len(objects),
            "geometryTypes": dict(Counter(it.geometry_type for it in items)),
            "colour": list(model.layer_colours.get(key, items[0].colour)),
            "missingMesh": [{"key": key, "objectId": it.object_id, "geometryType": it.geometry_type}
                            for it in items if it.mesh is None],
        }
        record.update(_describe(meshed))
        groups[key] = _rows(objects)
        forms = Counter(st["form"] for _, st in meshed)
        main = sorted((f for f, n in forms.items() if n >= MIXED_SHARE * len(meshed)),
                      key=lambda f: (-forms[f], f))
        if len(main) >= 2:
            record["clusters"] = []
            members = {f: [] for f in main}
            for parts, st in meshed:
                members[st["form"] if st["form"] in members else main[0]].append((parts, st))
            parents[key] = []
            for i, f in enumerate(main, 1):
                ckey = "%s#%d" % (key, i)
                parents[key].append(ckey)
                groups[ckey] = _rows(members[f])
                record["clusters"].append(dict({"key": ckey, "form": f,
                                                "count": len(members[f])}, **_describe(members[f])))
            groups[key + "#1"] += _rows((parts, st) for parts, st in objects if st is None)
        records.append(record)
    return records, groups, parents


def _describe(rows):
    """Union bbox, forms and min/median/max statistics of [(_, stats)]."""
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
    """(inventory.json document, groups): groups maps every key a mapping may use,
    the mixed keys of `parentKeys` included, to its [(item, stats)]."""
    records, groups, parents = resolve(model)
    missing = [m for rec in records for m in rec["missingMesh"]]
    per_object = {it.object_id: st for rec in records for it, st in groups[rec["key"]]
                  if st is not None}
    doc = {
        "units": {"model": model.unit, "toMetres": model.scale},
        "objectCount": len({it.object_id for it in model.items}),
        "extent": _describe([(None, st) for st in per_object.values()]).get("bbox"),
        "keys": sorted(k for k in groups if k not in parents),
        "parentKeys": parents,
        "layers": records,
        "nonGeometric": model.non_geometric,
    }
    if missing:
        doc["error"] = {"code": 3, "missingMesh": missing,
                        "fix": "open the .3dm in Rhino and save it normally (not Save Small), "
                               "or mesh those objects via Cordyceps, then rerun inventory"}
    return doc, groups
