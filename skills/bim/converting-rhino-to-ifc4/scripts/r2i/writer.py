"""Write the IFC: Project > Site > Building [> Storeys], one element per object
(or per key when merged), tessellated bodies, colours, Pset_RhinoSource."""
import math

import ifcopenshell
import ifcopenshell.guid

from . import model as rmodel
from .errors import R2IError

STOREY_TOLERANCE = 0.3   # m: floor slab bottoms closer than this share a level
MAX_IDS = 50             # object GUIDs listed in Pset_RhinoSource of a merged element


class Writer:
    def __init__(self, schema, north=None, georef=None):
        f = ifcopenshell.file(schema=schema)
        self.f = f
        name = f.header.file_name
        name.author = ("",)
        name.organization = ("",)
        name.authorization = ""
        name.originating_system = "rhino2ifc"
        name.preprocessor_version = ""
        units = f.create_entity("IfcUnitAssignment", Units=[
            f.create_entity("IfcSIUnit", UnitType=u, Name=n) for u, n in (
                ("LENGTHUNIT", "METRE"), ("AREAUNIT", "SQUARE_METRE"),
                ("VOLUMEUNIT", "CUBIC_METRE"), ("PLANEANGLEUNIT", "RADIAN"))])
        self.ctx = f.create_entity(
            "IfcGeometricRepresentationContext", ContextType="Model",
            CoordinateSpaceDimension=3, Precision=1e-5, WorldCoordinateSystem=self.axis(),
            TrueNorth=f.create_entity("IfcDirection", DirectionRatios=north) if north else None)
        self.body = f.create_entity(
            "IfcGeometricRepresentationSubContext", ContextIdentifier="Body",
            ContextType="Model", ParentContext=self.ctx, TargetView="MODEL_VIEW")
        f.create_entity(  # for 2D/axis representations; v1 writes bodies only
            "IfcGeometricRepresentationSubContext", ContextIdentifier="Reference",
            ContextType="Model", ParentContext=self.ctx, TargetView="GRAPH_VIEW")
        self.project = self.root("IfcProject", "Project", RepresentationContexts=[self.ctx],
                                 UnitsInContext=units)
        if georef:
            epsg, e, n, h, rot = georef
            crs = f.create_entity("IfcProjectedCRS", Name="EPSG:%d" % epsg)
            f.create_entity("IfcMapConversion", SourceCRS=self.ctx, TargetCRS=crs,
                            Eastings=e, Northings=n, OrthogonalHeight=h,
                            XAxisAbscissa=math.cos(math.radians(rot)),
                            XAxisOrdinate=math.sin(math.radians(rot)), Scale=1.0)
        self.site = self.root("IfcSite", "Site", ObjectPlacement=self.placement())
        self.building = self.root("IfcBuilding", "Building", ObjectPlacement=self.placement())
        self.aggregate(self.project, [self.site])
        self.aggregate(self.site, [self.building])
        self.styles = {}

    def root(self, cls, name, **kw):
        return self.f.create_entity(cls, GlobalId=ifcopenshell.guid.new(), Name=name, **kw)

    def axis(self, xyz=(0.0, 0.0, 0.0)):
        pt = self.f.create_entity("IfcCartesianPoint", Coordinates=xyz)
        return self.f.create_entity("IfcAxis2Placement3D", Location=pt)

    def placement(self, relative_to=None, z=0.0):
        return self.f.create_entity("IfcLocalPlacement", PlacementRelTo=relative_to,
                                    RelativePlacement=self.axis((0.0, 0.0, float(z))))

    def aggregate(self, whole, parts):
        self.root("IfcRelAggregates", None, RelatingObject=whole, RelatedObjects=parts)

    def style(self, colour):
        if colour not in self.styles:
            rgb = self.f.create_entity("IfcColourRgb", None, *(c / 255.0 for c in colour))
            shading = self.f.create_entity("IfcSurfaceStyleShading", SurfaceColour=rgb)
            self.styles[colour] = self.f.create_entity(
                "IfcSurfaceStyle", Side="BOTH", Styles=[shading])
        return self.styles[colour]

    def shape(self, items, scale):
        faces_sets = []
        for item in items:
            mesh = item.mesh
            coords = self.f.create_entity("IfcCartesianPointList3D", CoordList=[
                (round(v.X * scale, 6), round(v.Y * scale, 6), round(v.Z * scale, 6))
                for v in mesh.Vertices])
            faces = []
            for face in mesh.Faces:
                idx = face[:3] if face[2] == face[3] else face
                faces.append(self.f.create_entity(
                    "IfcIndexedPolygonalFace", CoordIndex=[i + 1 for i in idx]))
            fs = self.f.create_entity("IfcPolygonalFaceSet", Coordinates=coords,
                                      Closed=bool(mesh.IsClosed), Faces=faces)
            self.f.create_entity("IfcStyledItem", Item=fs, Styles=[self.style(item.colour)])
            faces_sets.append(fs)
        rep = self.f.create_entity(
            "IfcShapeRepresentation", ContextOfItems=self.body, RepresentationIdentifier="Body",
            RepresentationType="Tessellation", Items=faces_sets)
        return self.f.create_entity("IfcProductDefinitionShape", Representations=[rep])

    def pset(self, element, values):
        props = []
        for name, value in values:
            kind = "IfcInteger" if isinstance(value, int) else "IfcText"
            props.append(self.f.create_entity(
                "IfcPropertySingleValue", Name=name,
                NominalValue=self.f.create_entity(kind, value)))
        ps = self.root("IfcPropertySet", "Pset_RhinoSource", HasProperties=props)
        self.root("IfcRelDefinesByProperties", None, RelatedObjects=[element],
                  RelatingPropertyDefinition=ps)


def elements_of(entry, rows):
    """[(name, [(item, stats)])]: one per key when merged, else one per Rhino
    object or block instance (all its parts in one element)."""
    key = entry["key"]
    leaf = key[len("block:"):] if rows and rows[0][0].kind == "block" else key.split("::")[-1]
    if entry["merge"]:
        return [(leaf, rows)]
    by_object = {}
    for it, st in rows:
        by_object.setdefault(it.object_id, []).append((it, st))
    return [(rs[0][0].name or leaf, rs) for rs in by_object.values()]


def detect_levels(planned):
    """Bottoms of the Rhino objects in IfcSlab FLOOR elements (merged ones too),
    clustered at STOREY_TOLERANCE."""
    zs = sorted({it.object_id: st["zMin"] for entry, _, rows in planned for it, st in rows
                 if entry["class"] == "IfcSlab" and entry["predefinedType"] == "FLOOR"}.values())
    if not zs:
        raise R2IError(2, "--storeys found no IfcSlab FLOOR elements",
                       "give the levels: --storeys 0,3.2,6.4 (metres)")
    levels = [zs[0]]
    for z in zs[1:]:
        if z - levels[-1] > STOREY_TOLERANCE:
            levels.append(z)
    return levels


def convert(model, groups, mapping, out_path, storeys=None, georef=None, north_layer=None):
    """storeys: None (no storeys), "auto", or a list of levels in metres."""
    planned, skipped = [], []
    for key, entry in sorted(mapping["entries"].items()):
        if entry["skip"]:
            skipped.append(key)
            continue
        rows = groups[key]
        missing = [{"key": key, "objectId": it.object_id, "geometryType": it.geometry_type}
                   for it, _ in rows if it.mesh is None]
        if missing:
            raise R2IError(3, "objects without a cached mesh", missingMesh=missing,
                           fix="save the .3dm normally in Rhino (not Save Small), "
                               "or skip that key")
        for name, erows in elements_of(entry, rows):
            planned.append((entry, name, erows))

    north = rmodel.north(model, north_layer) if north_layer else None
    w = Writer(mapping["schema"], north=north, georef=georef)
    levels = None
    if storeys == "auto":
        levels = detect_levels(planned)
    elif storeys:
        levels = sorted(set(storeys))
    containers = {}
    storey_objs = []
    if levels:
        for i, z in enumerate(levels):
            storey_objs.append(w.root("IfcBuildingStorey", "Level %d" % i, Elevation=z,
                                      ObjectPlacement=w.placement(w.building.ObjectPlacement, z)))
        w.aggregate(w.building, storey_objs)

    counts = {}
    for entry, name, rows in planned:
        kw = {}
        if entry["predefinedType"]:
            kw["PredefinedType"] = entry["predefinedType"]
        if entry["objectType"]:
            kw["ObjectType"] = entry["objectType"]
        element = w.root(entry["class"], name, ObjectPlacement=w.placement(),
                         Representation=w.shape([it for it, _ in rows], model.scale), **kw)
        ids = list(dict.fromkeys(it.object_id for it, _ in rows))
        values = [("LayerPath", ";".join(dict.fromkeys(it.layer for it, _ in rows))),
                  ("ObjectIds", ";".join(ids[:MAX_IDS]))]
        if len(ids) > MAX_IDS:
            values.append(("ObjectCount", len(ids)))
        values += [("Confidence", entry["confidence"]), ("Rationale", entry["rationale"])]
        w.pset(element, values)
        if entry["class"] == "IfcGeographicElement":
            container = w.site
        elif levels:
            z = min(st["zMin"] for _, st in rows)
            idx = max([i for i, lv in enumerate(levels) if lv <= z + 1e-6] or [0])
            container = storey_objs[idx]
        else:
            container = w.building
        containers.setdefault(container, []).append(element)
        counts[entry["class"]] = counts.get(entry["class"], 0) + 1
    for container, elements in containers.items():
        w.root("IfcRelContainedInSpatialStructure", None,
               RelatingStructure=container, RelatedElements=elements)
    try:
        w.f.write(str(out_path))
    except (OSError, RuntimeError) as exc:  # ifcopenshell raises RuntimeError for a folder
        raise R2IError(2, "cannot write %s: %s" % (out_path, exc),
                       "give -o a path in an existing, writable folder")
    return {"ok": True, "output": str(out_path), "schema": mapping["schema"],
            "elements": counts, "storeys": levels or [], "skipped": skipped}
