"""Build the test .3dm with rhino3dm (metres).

Layers: Existing::Stützen (3 columns, one named C1), Layer 01 (2 columns and
2 floor slabs: mixed), Terrain (one flat mesh), Furniture (an instance of
block Chair coloured by object, and an instance of block Set, which nests a
Chair 1 m along x), Notes (a line), North (a line pointing north-east).
missing_mesh=True adds layer Solids with a Brep box that has no cached mesh.

build_extra: a top-level layer Chair (one box) beside a block Chair (four legs,
a seat and a line) placed twice on layer Furniture and once on Lounge; Decken (floor slabs at
z 0, 3, 6); Facade (10 vertical panels and 10 mullions: mixed); Pebbles (55
small boxes). empty_mesh=True adds layer Empty with a mesh of no vertices.

build_materials: layers whose display colour is black while a render material
gives the visible colour (Painted: 200,100,50; Glass: 30,60,200 at 0.4
transparency), an object with its own material (10,200,30), a block whose
member takes its material by parent, and layers without a usable material
(Plain; Dangling, whose material index is out of range) that keep the display
colour.

build_broken: block B on layer A whose definition lists one object that is
gone; dangling=True adds an instance of a block definition that does not exist.
"""
import sys

import rhino3dm as r


def box(x, y, z, dx, dy, dz):
    m = r.Mesh()
    for X, Y, Z in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]:
        m.Vertices.Add(x + X * dx, y + Y * dy, z + Z * dz)
    for q in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        m.Faces.AddFace(*q)
    return m


def layer(f, name, colour, parent=None):
    lay = r.Layer()
    lay.Name = name
    lay.Color = colour + (255,)
    if parent is not None:
        lay.ParentLayerId = f.Layers.FindIndex(parent).Id
    return f.Layers.Add(lay)


def material(f, name, colour, transparency=0.0):
    m = r.Material()
    m.Name = name
    m.DiffuseColor = colour + (255,)
    m.Transparency = transparency
    return f.Materials.Add(m)


def attrs(index, name="", colour=None, from_parent=False):
    a = r.ObjectAttributes()
    a.LayerIndex = index
    a.Name = name
    if colour:
        a.ColorSource = r.ObjectColorSource.ColorFromObject
        a.ObjectColor = colour + (255,)
    elif from_parent:
        a.ColorSource = r.ObjectColorSource.ColorFromParent
    return a


def build(path, missing_mesh=False):
    f = r.File3dm()
    f.Settings.ModelUnitSystem = r.UnitSystem.Meters
    existing = layer(f, "Existing", (128, 128, 128))
    stuetzen = layer(f, "Stützen", (255, 0, 0), parent=existing)
    for i, x in enumerate((0, 5, 10)):
        f.Objects.AddMesh(box(x, 0, 0, 0.4, 0.4, 3.0), attrs(stuetzen, "C1" if i == 0 else ""))
    mixed = layer(f, "Layer 01", (200, 200, 200))
    for x in (0, 5):
        f.Objects.AddMesh(box(x, 10, 0, 0.3, 0.3, 3.0), attrs(mixed))
    for z in (0.0, 3.0):
        f.Objects.AddMesh(box(0, 10, z, 8, 8, 0.25), attrs(mixed))
    terrain = layer(f, "Terrain", (120, 90, 60))
    ground = r.Mesh()
    for x, y in [(-10, -10), (20, -10), (20, 20), (-10, 20)]:
        ground.Vertices.Add(x, y, -0.5)
    ground.Faces.AddFace(0, 1, 2, 3)
    f.Objects.AddMesh(ground, attrs(terrain))
    parts = layer(f, "Furniture parts", (0, 0, 0))
    furniture = layer(f, "Furniture", (0, 255, 0))
    chair = f.InstanceDefinitions.Add("Chair", "", "", "", r.Point3d(0, 0, 0),
                                      (box(0, 0, 0, 0.5, 0.5, 0.5),),
                                      (attrs(parts, from_parent=True),))
    chair_id = f.InstanceDefinitions.FindIndex(chair).Id
    nested = f.InstanceDefinitions.Add(
        "Set", "", "", "", r.Point3d(0, 0, 0),
        (r.InstanceReference(chair_id, r.Transform.Translation(1, 0, 0)),),
        (attrs(parts, from_parent=True),))
    f.Objects.AddInstanceObject(r.InstanceReference(chair_id, r.Transform.Translation(2, 2, 0)),
                                attrs(furniture, colour=(0, 0, 255)))
    f.Objects.AddInstanceObject(
        r.InstanceReference(f.InstanceDefinitions.FindIndex(nested).Id,
                            r.Transform.Translation(10, 0, 0)), attrs(furniture))
    notes = layer(f, "Notes", (0, 0, 0))
    f.Objects.AddLine(r.Point3d(0, 0, 0), r.Point3d(5, 0, 0), attrs(notes))
    north = layer(f, "North", (0, 0, 0))
    f.Objects.AddLine(r.Point3d(0, 0, 0), r.Point3d(1, 1, 0), attrs(north))
    if missing_mesh:
        solids = layer(f, "Solids", (0, 0, 0))
        f.Objects.AddBrep(r.Brep.CreateFromBox(r.Box(r.BoundingBox(0, 0, 0, 1, 1, 1))),
                          attrs(solids))
    if not f.Write(str(path), 8):
        raise RuntimeError("could not write %s" % path)
    return path


def build_extra(path, empty_mesh=False):
    f = r.File3dm()
    f.Settings.ModelUnitSystem = r.UnitSystem.Meters
    f.Objects.AddMesh(box(20, 0, 0, 0.5, 0.5, 0.5), attrs(layer(f, "Chair", (1, 1, 1))))
    parts = layer(f, "Chair parts", (2, 2, 2))
    legs = [box(x, y, 0, 0.05, 0.05, 0.45) for x in (0, 0.45) for y in (0, 0.45)]
    geometry = legs + [box(0, 0, 0.45, 0.5, 0.5, 0.03),
                       r.LineCurve(r.Point3d(0, 0, 0), r.Point3d(0.5, 0, 0))]
    chair = f.InstanceDefinitions.Add("Chair", "", "", "", r.Point3d(0, 0, 0), tuple(geometry),
                                      tuple(attrs(parts) for _ in geometry))
    chair_id = f.InstanceDefinitions.FindIndex(chair).Id
    furniture = layer(f, "Furniture", (3, 3, 3))
    lounge = layer(f, "Lounge", (3, 3, 3))
    for x, where in ((30, furniture), (32, furniture), (34, lounge)):
        f.Objects.AddInstanceObject(r.InstanceReference(chair_id, r.Transform.Translation(x, 0, 0)),
                                    attrs(where))
    decken = layer(f, "Decken", (4, 4, 4))
    for z in (0.0, 3.0, 6.0):
        f.Objects.AddMesh(box(0, 0, z, 10, 10, 0.25), attrs(decken))
    facade = layer(f, "Facade", (5, 5, 5))
    for i in range(10):
        f.Objects.AddMesh(box(1.5 * i, -5, 0, 1.45, 0.02, 3.0), attrs(facade))
        f.Objects.AddMesh(box(1.5 * i + 1.45, -5, 0, 0.05, 0.05, 3.0), attrs(facade))
    pebbles = layer(f, "Pebbles", (6, 6, 6))
    for i in range(55):
        f.Objects.AddMesh(box(i * 0.2, -10, 0, 0.1, 0.1, 0.1), attrs(pebbles))
    if empty_mesh:
        f.Objects.AddMesh(r.Mesh(), attrs(layer(f, "Empty", (7, 7, 7))))
    if not f.Write(str(path), 8):
        raise RuntimeError("could not write %s" % path)
    return path


def build_materials(path):
    f = r.File3dm()
    f.Settings.ModelUnitSystem = r.UnitSystem.Meters
    painted = layer(f, "Painted", (0, 0, 0))
    f.Layers.FindIndex(painted).RenderMaterialIndex = material(f, "weiss", (200, 100, 50))
    own = material(f, "gruen", (10, 200, 30))
    glass = layer(f, "Glass", (0, 0, 0))
    f.Layers.FindIndex(glass).RenderMaterialIndex = material(f, "glas", (30, 60, 200), 0.4)
    plain = layer(f, "Plain", (9, 8, 7))
    dangling = layer(f, "Dangling", (4, 5, 6))
    f.Layers.FindIndex(dangling).RenderMaterialIndex = 99
    parts = layer(f, "Parts", (1, 2, 3))
    f.Objects.AddMesh(box(0, 0, 0, 1, 1, 1), attrs(painted))
    own_attrs = attrs(painted)
    own_attrs.MaterialSource = r.ObjectMaterialSource.MaterialFromObject
    own_attrs.MaterialIndex = own
    f.Objects.AddMesh(box(2, 0, 0, 1, 1, 1), own_attrs)
    f.Objects.AddMesh(box(4, 0, 0, 1, 1, 1), attrs(glass))
    f.Objects.AddMesh(box(6, 0, 0, 1, 1, 1), attrs(plain))
    f.Objects.AddMesh(box(8, 0, 0, 1, 1, 1), attrs(dangling))
    member = attrs(parts)
    member.MaterialSource = r.ObjectMaterialSource.MaterialFromParent
    cup = f.InstanceDefinitions.Add("Cup", "", "", "", r.Point3d(0, 0, 0),
                                    (box(0, 0, 0, 0.5, 0.5, 0.5),), (member,))
    cup_id = f.InstanceDefinitions.FindIndex(cup).Id
    f.Objects.AddInstanceObject(r.InstanceReference(cup_id, r.Transform.Translation(0, 5, 0)),
                                attrs(painted))
    f.Objects.AddInstanceObject(r.InstanceReference(cup_id, r.Transform.Translation(2, 5, 0)),
                                own_attrs)
    f.Objects.AddInstanceObject(r.InstanceReference(cup_id, r.Transform.Translation(4, 5, 0)),
                                attrs(plain))
    if not f.Write(str(path), 8):
        raise RuntimeError("could not write %s" % path)
    return path


def build_broken(path, dangling=False):
    f = r.File3dm()
    f.Settings.ModelUnitSystem = r.UnitSystem.Meters
    a = layer(f, "A", (1, 1, 1))
    idx = f.InstanceDefinitions.Add("B", "", "", "", r.Point3d(0, 0, 0),
                                    (box(0, 0, 0, 1, 1, 1), box(2, 0, 0, 1, 1, 1)),
                                    (attrs(a), attrs(a)))
    idef = f.InstanceDefinitions.FindIndex(idx)
    f.Objects.Delete(idef.GetObjectIds()[0])
    f.Objects.AddInstanceObject(r.InstanceReference(idef.Id, r.Transform.Translation(5, 0, 0)),
                                attrs(a))
    if dangling:
        f.Objects.AddInstanceObject(r.InstanceReference(r.Layer().Id, r.Transform.Translation(0, 0, 0)),
                                    attrs(a))
    if not f.Write(str(path), 8):
        raise RuntimeError("could not write %s" % path)
    return path


if __name__ == "__main__":
    build(sys.argv[1], missing_mesh="--missing-mesh" in sys.argv)
