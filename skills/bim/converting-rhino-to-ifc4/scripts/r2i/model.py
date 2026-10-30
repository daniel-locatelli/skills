"""Read a .3dm with rhino3dm into world-space items, one per meshable object.

rhino3dm cannot tessellate: Brep and Extrusion geometry comes from the render
meshes Rhino cached in the file. An item whose mesh is missing (or empty)
keeps `mesh=None`; callers decide whether that stops the run. A block key is
`block:<definition name>`, so a layer and a block of one name never collide.
"""
from dataclasses import dataclass, field

import rhino3dm as r

from .errors import R2IError

UNIT_TO_M = {
    "Microns": 1e-6, "Millimeters": 1e-3, "Centimeters": 1e-2, "Decimeters": 0.1,
    "Meters": 1.0, "Kilometers": 1e3, "Inches": 0.0254, "Feet": 0.3048,
    "Yards": 0.9144, "Miles": 1609.344,
}
MESHABLE = (r.Mesh, r.Brep, r.Extrusion, r.Surface, r.SubD)
MAX_NESTING = 32


@dataclass
class Item:
    key: str            # layer path, or "block:" + the outermost block definition name
    kind: str           # "layer" | "block"
    layer: str          # layer path of the top-level object (the instance, for blocks)
    object_id: str      # Rhino GUID of the top-level object
    name: str           # Rhino object name ("" when unset)
    geometry_type: str  # rhino3dm class name of the meshed geometry
    colour: tuple       # (r, g, b), 0-255: the render material's diffuse colour, else the display colour
    mesh: object        # rhino3dm.Mesh in world coordinates, model units; None = no cached mesh
    transparency: float = 0.0  # 0 opaque .. 1 clear; only a render material carries it


@dataclass
class Model:
    doc: object                 # rhino3dm.File3dm
    unit: str
    scale: float                # model unit -> metres
    items: list = field(default_factory=list)
    non_geometric: dict = field(default_factory=dict)  # layer path -> {type: count}
    layer_colours: dict = field(default_factory=dict)  # layer path -> (r, g, b)


def mesh_of(geom):
    """The cached mesh of a meshable geometry, or None (also when it has no faces)."""
    mesh = _cached_mesh(geom)
    if mesh is None or len(mesh.Vertices) == 0 or len(mesh.Faces) == 0:
        return None
    return mesh


def _cached_mesh(geom):
    if isinstance(geom, r.Mesh):
        return geom
    if isinstance(geom, r.Brep):
        out = r.Mesh()
        for face in geom.Faces:
            m = face.GetMesh(r.MeshType.Render)
            if m is None:
                m = face.GetMesh(r.MeshType.Any)
            if m is None:
                return None
            out.Append(m)
        return out
    if isinstance(geom, r.Extrusion):
        m = geom.GetMesh(r.MeshType.Render)
        return m if m is not None else geom.GetMesh(r.MeshType.Any)
    return None  # Surface, SubD: rhino3dm exposes no cached mesh


def material_of(doc, attrs, layer, parent_material):
    """(diffuse (r, g, b), transparency) of the render material an object shows, or None.

    The visible colour of most models is a render material, while every layer's
    display colour stays black. Source "by object" uses the object's material,
    "by parent" the enclosing instance's (the layer's at top level or when the
    parent has none), "by layer" the layer's. An index outside the file's
    material table counts as no material.
    """
    src = attrs.MaterialSource
    if src == r.ObjectMaterialSource.MaterialFromObject:
        index = attrs.MaterialIndex
    elif src == r.ObjectMaterialSource.MaterialFromParent and parent_material is not None:
        return parent_material
    else:
        index = layer.RenderMaterialIndex
    if index < 0 or index >= len(doc.Materials):
        return None
    material = doc.Materials[index]
    return tuple(material.DiffuseColor[:3]), float(material.Transparency)


def appearance_of(doc, attrs, layer, layer_colour, parent):
    """(colour, transparency, material) for an object; the render material wins,
    the display colour (colour_of) is the fallback. `parent` is the enclosing
    instance's (colour, material) or None; `material` is passed on to block members."""
    material = material_of(doc, attrs, layer, parent[1] if parent else None)
    colour = colour_of(attrs, layer_colour, parent[0] if parent else None)
    if material is None:
        return colour, 0.0, None
    return material[0], material[1], material


def colour_of(attrs, layer_colour, parent_colour):
    src = attrs.ColorSource
    if src == r.ObjectColorSource.ColorFromObject:
        return tuple(attrs.ObjectColor[:3])
    if src == r.ObjectColorSource.ColorFromParent and parent_colour is not None:
        return parent_colour
    return layer_colour


def read(path):
    doc = r.File3dm.Read(str(path))
    if doc is None:
        raise R2IError(2, "cannot read %s" % path, "check the path; it must be a Rhino .3dm file")
    unit = doc.Settings.ModelUnitSystem.name
    if unit not in UNIT_TO_M:
        raise R2IError(2, "unsupported model unit %s" % unit,
                       "set a metric or imperial unit in Rhino (Document Properties > Units)")
    model = Model(doc=doc, unit=unit, scale=UNIT_TO_M[unit])
    layers = {layer.Index: layer for layer in doc.Layers}
    for layer in layers.values():
        model.layer_colours[layer.FullPath] = tuple(layer.Color[:3])
    defs = {d.Id: d for d in doc.InstanceDefinitions}

    for obj in doc.Objects:
        attrs = obj.Attributes
        if attrs.IsInstanceDefinitionObject:
            continue
        layer = _layer(layers, attrs)
        path = layer.FullPath
        colour, transparency, material = appearance_of(
            doc, attrs, layer, model.layer_colours[path], None)
        geom = obj.Geometry
        top = dict(layer=path, object_id=str(attrs.Id), name=attrs.Name or "")
        if isinstance(geom, r.InstanceReference):
            idef = _definition(defs, geom, attrs)
            _explode(model, layers, defs, idef, geom.Xform, (colour, material),
                     dict(top, key="block:" + idef.Name, kind="block"), 0)
        elif isinstance(geom, MESHABLE):
            model.items.append(Item(key=path, kind="layer", geometry_type=type(geom).__name__,
                                    colour=colour, transparency=transparency,
                                    mesh=mesh_of(geom), **top))
        else:
            _count(model, path, type(geom).__name__)
    return model


def _count(model, path, name):
    counts = model.non_geometric.setdefault(path, {})
    counts[name] = counts.get(name, 0) + 1


def _layer(layers, attrs):
    if attrs.LayerIndex not in layers:
        raise R2IError(2, "object %s refers to layer index %d, which the file does not have"
                       % (attrs.Id, attrs.LayerIndex),
                       "open and save the .3dm in Rhino (Audit3dmFile repairs it)")
    return layers[attrs.LayerIndex]


def _definition(defs, geom, attrs):
    if geom.ParentIdefId not in defs:
        raise R2IError(2, "block instance %s refers to block definition %s, which the file "
                       "does not have" % (attrs.Id, geom.ParentIdefId),
                       "delete or re-insert that block instance in Rhino and save")
    return defs[geom.ParentIdefId]


def _explode(model, layers, defs, idef, xform, parent, top, depth):
    if depth > MAX_NESTING:
        raise R2IError(2, "block %s nests deeper than %d" % (top["key"], MAX_NESTING),
                       "explode the block in Rhino")
    for oid in idef.GetObjectIds():
        obj = model.doc.Objects.FindId(oid)
        if obj is None:
            _count(model, top["layer"], "unresolved block object")
            continue
        attrs = obj.Attributes
        layer = _layer(layers, attrs)
        colour, transparency, material = appearance_of(
            model.doc, attrs, layer, model.layer_colours[layer.FullPath], parent)
        geom = obj.Geometry
        if isinstance(geom, r.InstanceReference):
            _explode(model, layers, defs, _definition(defs, geom, attrs),
                     r.Transform.Multiply(xform, geom.Xform), (colour, material), top, depth + 1)
        elif isinstance(geom, MESHABLE):
            mesh = mesh_of(geom)
            if mesh is not None:
                mesh = mesh.Duplicate()
                mesh.Transform(xform)
            model.items.append(Item(geometry_type=type(geom).__name__, colour=colour,
                                    transparency=transparency, mesh=mesh, **top))
        else:
            _count(model, top["layer"], type(geom).__name__)  # curves, text inside the block


def north(model, layer_path):
    """(x, y) unit vector of the first curve on layer_path, start -> end."""
    for obj in model.doc.Objects:
        if obj.Attributes.IsInstanceDefinitionObject:
            continue
        layer = model.doc.Layers.FindIndex(obj.Attributes.LayerIndex)
        geom = obj.Geometry
        if layer.FullPath == layer_path and isinstance(geom, r.Curve):
            a, b = geom.PointAtStart, geom.PointAtEnd
            dx, dy = b.X - a.X, b.Y - a.Y
            n = (dx * dx + dy * dy) ** 0.5
            if n > 0:
                return (round(dx / n, 9), round(dy / n, 9))
    raise R2IError(2, "no curve on layer %r for --north" % layer_path,
                   "draw one line pointing north on that layer, or drop --north")
