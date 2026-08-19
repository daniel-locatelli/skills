# BTLx 2.3.0 — processing parameter reference

> GENERATED from `BTLx_2_3_0.xsd` by `scripts/generate_reference.py` — do not hand-edit.
> Units: millimeters, degrees, kilograms (schema-wide convention).
> Geometric meaning of parameters lives in the PDF manual and
> `references/btlx-concepts.md`; this file is the wire contract only.

54 processings. Every processing also carries the
shared base parameters listed at the end.

## Processing index

- [JackRafterCut](#jackraftercut)
- [LongitudinalCut](#longitudinalcut)
- [DoubleCut](#doublecut)
- [RidgeValleyCut](#ridgevalleycut)
- [SawCut](#sawcut)
- [Slot](#slot)
- [BirdsMouth](#birdsmouth)
- [HipValleyRafterNotch](#hipvalleyrafternotch)
- [Lap](#lap)
- [LogHouseHalfLap](#loghousehalflap)
- [FrenchRidgeLap](#frenchridgelap)
- [Chamfer](#chamfer)
- [LogHouseJoint](#loghousejoint)
- [LogHouseFront](#loghousefront)
- [Pocket](#pocket)
- [Drilling](#drilling)
- [Tenon](#tenon)
- [Mortise](#mortise)
- [House](#house)
- [HouseMortise](#housemortise)
- [DovetailTenon](#dovetailtenon)
- [DovetailMortise](#dovetailmortise)
- [JapaneseTenon](#japanesetenon)
- [JapaneseMortise](#japanesemortise)
- [Marking](#marking)
- [Text](#text)
- [SimpleScarf](#simplescarf)
- [ScarfJoint](#scarfjoint)
- [StepJoint](#stepjoint)
- [StepJointNotch](#stepjointnotch)
- [ProfileFront](#profilefront)
- [ProfileCambered](#profilecambered)
- [RoundArch](#roundarch)
- [Planing](#planing)
- [ProfileHead](#profilehead)
- [Sphere](#sphere)
- [TriangleCut](#trianglecut)
- [TyroleanDovetail](#tyroleandovetail)
- [Dovetail](#dovetail)
- [FreeContour](#freecontour)
- [SawContour](#sawcontour)
- [MillContour](#millcontour)
- [NailContour](#nailcontour)
- [CrampContour](#crampcontour)
- [ScrewContour](#screwcontour)
- [PenContour](#pencontour)
- [GlueArea](#gluearea)
- [PlaningArea](#planingarea)
- [PlasterArea](#plasterarea)
- [InsulationArea](#insulationarea)
- [LockoutArea](#lockoutarea)
- [FreeSurface](#freesurface)
- [Variant](#variant)
- [PatternContour](#patterncontour)

## JackRafterCut

> Definition of a jackrafter cut (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthType` (double): 0.0 … 50000.0 | 0.0 | no |  |
| `StartDepth` | `WidthType` (double): 0.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |

## LongitudinalCut

> Definition of a longitudinal cut

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolPosition` | `ToolPositionType` (string): enum: left, center, right | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `Inclination` | `Inclination2Type` (double): -90.0 … 90.0 | 45.0 | no |  |
| `StartLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `EndLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `Length` | `LengthType` (double): 0.0 … 100000.0 | 0.0 | no |  |
| `DepthLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `Depth` | `WidthType` (double): 0.0 … 50000.0 | 0.0 | no |  |
| `AngleStart` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `AngleEnd` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |

## DoubleCut

> Definition of a double cut (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `Angle1` | `AngleType` (double): 0.1 … 179.9 | 45.0 | no |  |
| `Inclination1` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Angle2` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination2` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |

## RidgeValleyCut

> Definition of a ridge/valley cut

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthType` (double): 0.0 … 50000.0 | 50.0 | no |  |
| `StartDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `InclinationRefSide` | `InclinationType` (double): -89.9 … 89.9 | 45.0 | no |  |
| `InclinationOppSide` | `InclinationType` (double): -89.9 … 89.9 | 45.0 | no |  |
| `StartLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `EndLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `Length` | `LengthType` (double): 0.0 … 100000.0 | 0.0 | no |  |
| `AngleRefEdgeStart` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `AngleRefEdgeEnd` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `AngleOppEdgeStart` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `AngleOppEdgeEnd` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |

## SawCut

> Definition of a saw cut

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolPosition` | `ToolPositionType` (string): enum: left, center, right | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `StartDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `Angle2NType` (double): -180.0 … 180.0 | 90.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Bevel` | `InclinationType` (double): -89.9 … 89.9 | 0.0 | no |  |
| `Length` | `LengthType` (double): 0.0 … 100000.0 | 100.0 | no |  |
| `Depth` | `WidthType` (double): 0.0 … 50000.0 | 50.0 | no |  |
| `MachiningLimits` | complex → see `SawCutMachiningLimitType` | — | no |  |

## Slot

> Definition of a slot

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `StartDepth` | `WidthType` (double): 0.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `Inclination2Type` (double): -90.0 … 90.0 | 0.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Length` | `LengthType` (double): 0.0 … 100000.0 | 200.0 | no |  |
| `Depth` | `WidthType` (double): 0.0 … 50000.0 | 100.0 | no |  |
| `Thickness` | `WidthType` (double): 0.0 … 50000.0 | 10.0 | no |  |
| `AngleRefPoint` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `AngleOppPoint` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `AddAngleOppPoint` | `AngleNType` (double): -179.9 … 179.9 | 0.0 | no |  |
| `MachiningLimits` | complex → see `MachiningLimitType` | — | no |  |

## BirdsMouth

> Definition of a birds mouth

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `StartDepth` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `Angle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination1` | `Angle2Type` (double): 0.0 … 180.0 | 45.0 | no |  |
| `Inclination2` | `Angle2Type` (double): 0.0 … 180.0 | 135.0 | no |  |
| `Depth` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `Width` | `WidthType` (double): 0.0 … 50000.0 | 0.0 | no |  |
| `WidthCounterPartLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `WidthCounterPart` | `WidthType` (double): 0.0 … 50000.0 | 120.0 | no |  |
| `HeightCounterPartLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `HeightCounterPart` | `WidthType` (double): 0.0 … 50000.0 | 120.0 | no |  |
| `FaceLimitedFront` | `BooleanType` (string): enum: yes, no | no | no |  |
| `FaceLimitedBack` | `BooleanType` (string): enum: yes, no | no | no |  |
| `LeadAngleParallel` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `LeadAngle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `LeadInclinationParallel` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `LeadInclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `RafterNailHole` | `BooleanType` (string): enum: yes, no | no | no |  |

## HipValleyRafterNotch

> Definition of a hip or valley rafter notch

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `StartDepth` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `AngleRefEdge` | `AngleType` (double): 0.1 … 179.9 | 45.0 | no |  |
| `AngleOppEdge` | `AngleType` (double): 0.1 … 179.9 | 45.0 | no |  |
| `Inclination` | `Angle2Type` (double): 0.0 … 180.0 | 30.0 | no |  |
| `WidthCounterPartRefEdgeLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `WidthCounterPartRefEdge` | `WidthType` (double): 0.0 … 50000.0 | 120.0 | no |  |
| `WidthCounterPartOppEdgeLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `WidthCounterPartOppEdge` | `WidthType` (double): 0.0 … 50000.0 | 120.0 | no |  |
| `RafterNailHole` | `BooleanType` (string): enum: yes, no | no | no |  |

## Lap

> Definition of a lap

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Slope` | `InclinationType` (double): -89.9 … 89.9 | 0.0 | no |  |
| `Length` | `LengthType` (double): 0.0 … 100000.0 | 100.0 | no |  |
| `Width` | `WidthType` (double): 0.0 … 50000.0 | 50.0 | no |  |
| `Depth` | `WidthNType` (double): -50000.0 … 50000.0 | 40.0 | no |  |
| `LeadAngleParallel` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `LeadAngle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `LeadInclinationParallel` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `LeadInclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `MachiningLimits` | complex → see `MachiningLimitType` | — | no |  |

## LogHouseHalfLap

> Definition of a log house half lap

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `Angle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 120.0 | no |  |
| `DepthRefSide` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `DepthOppSide` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |

## FrenchRidgeLap

> Definition of a french ridge lap (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `Angle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `RefPosition` | `EdgePositionType` (string): enum: refedge, oppedge | refedge | no |  |
| `Drillhole` | `BooleanType` (string): enum: yes, no | no | no |  |
| `DrillholeDiam` | `LengthSType` (double): 0.0 … 1000.0 | 0.0 | no |  |

## Chamfer

> Definition of a chamfer

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `EndLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `Length` | `LengthType` (double): 0.0 … 100000.0 | 0.0 | no |  |
| `Depth` | double: 0.0 … 100.0 | 1.0 | no |  |
| `ChamferEdge12` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `ChamferEdge23` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `ChamferEdge34` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `ChamferEdge41` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `ChamferExit` | `ChamferExitType` (string): enum: orthogonal, angular, round | orthogonal | no |  |

## LogHouseJoint

> Definition of a log house joint

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `SideLapsLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `DepthSideLaps` | `WidthType` (double): 0.0 … 50000.0 | — | no |  |
| `LapPosition` | `LogLapPositionType` (string): enum: symmetric, forward, backward | symmetric | no |  |
| `LengthRefSide` | `WidthType` (double): 0.0 … 50000.0 | 100.0 | no |  |
| `DepthRefSide` | `WidthType` (double): 0.0 … 50000.0 | 10.0 | no |  |
| `LengthOppSide` | `WidthType` (double): 0.0 … 50000.0 | 100.0 | no |  |
| `DepthOppSide` | `WidthType` (double): 0.0 … 50000.0 | 10.0 | no |  |
| `LengthRefEdge` | `WidthType` (double): 0.0 … 50000.0 | 100.0 | no |  |
| `DepthRefEdge` | `WidthType` (double): 0.0 … 50000.0 | 10.0 | no |  |
| `LengthOppEdge` | `WidthType` (double): 0.0 … 50000.0 | 100.0 | no |  |
| `DepthOppEdge` | `WidthType` (double): 0.0 … 50000.0 | 10.0 | no |  |
| `Drillhole` | `BooleanType` (string): enum: yes, no | no | no |  |
| `ArcRefEdgeStart` | `BooleanType` (string): enum: yes, no | no | no |  |
| `ArcRefEdgeEnd` | `BooleanType` (string): enum: yes, no | no | no |  |
| `ArcOppEdgeStart` | `BooleanType` (string): enum: yes, no | no | no |  |
| `ArcOppEdgeEnd` | `BooleanType` (string): enum: yes, no | no | no |  |
| `ArcRadius` | `WidthType` (double): 0.0 … 50000.0 | 120.0 | no |  |
| `ArcDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 60.0 | no |  |
| `ArcCenter` | `WidthType` (double): 0.0 … 50000.0 | 120.0 | no |  |

## LogHouseFront

> Definition of a log house front joint (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartDepth` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `Angle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 120.0 | no |  |
| `DepthRefEdge` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `DepthOppEdge` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `RefSideOnly` | `BooleanType` (string): enum: yes, no | no | no |  |

## Pocket

> Definition of a pocket

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `StartDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `AngleNType` (double): -179.9 … 179.9 | 0.0 | no |  |
| `Inclination` | `AngleNType` (double): -179.9 … 179.9 | 0.0 | no |  |
| `Slope` | `AngleNType` (double): -179.9 … 179.9 | 0.0 | no |  |
| `Length` | `LengthType` (double): 0.0 … 100000.0 | 200.0 | no |  |
| `Width` | `WidthType` (double): 0.0 … 50000.0 | 50.0 | no |  |
| `InternalAngle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `TiltRefSide` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `TiltEndSide` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `TiltOppSide` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `TiltStartSide` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `MachiningLimits` | complex → see `MachiningLimitType` | — | no |  |

## Drilling

> Definition of a drilling

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `Angle3Type` (double): 0.0 … 360.0 | 0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `DepthLimited` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `Depth` | `WidthType` (double): 0.0 … 50000.0 | 50.0 | no |  |
| `Diameter` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |

## Tenon

> Definition of a tenon (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `StartDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `Angle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Rotation` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `LengthLimitedTop` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `LengthLimitedBottom` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 80.0 | no |  |
| `Width` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Height` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Shape` | `TenonShapeType` (string): enum: automatic, square, round, rounded, radius | automatic | no |  |
| `ShapeRadius` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |
| `Chamfer` | `BooleanType` (string): enum: yes, no | no | no |  |

## Mortise

> Definition of a mortise

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `StartDepth` | `WidthType` (double): 0.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `Angle2NType` (double): -180.0 … 180.0 | 0.0 | no |  |
| `Slope` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `LengthLimitedTop` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `LengthLimitedBottom` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 80.0 | no |  |
| `Width` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Depth` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Shape` | `TenonShapeType` (string): enum: automatic, square, round, rounded, radius | automatic | no |  |
| `ShapeRadius` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |

## House

> Definition of a house

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Tenon` | complex → see `TenonType` | — | yes |  |
| `DovetailTenon` | complex → see `DovetailTenonType` | — | yes |  |

## HouseMortise

> Definition of a house mortise

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Mortise` | complex → see `MortiseType` | — | yes |  |
| `DovetailMortise` | complex → see `DovetailMortiseType` | — | yes |  |

## DovetailTenon

> Definition of a dovetail tenon (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `StartDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `Angle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Rotation` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `LengthLimitedTop` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `LengthLimitedBottom` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 80.0 | no |  |
| `Width` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Height` | `LengthSType` (double): 0.0 … 1000.0 | 28.0 | no |  |
| `ConeAngle` | `ConeAngleType` (double): 0.0 … 30.0 | — | no |  |
| `UseFlankAngle` | `BooleanType` (string): enum: yes, no | no | no |  |
| `FlankAngle` | `FlankAngleType` (double): 5.0 … 35.0 | 15.0 | no |  |
| `Shape` | `TenonShapeType` (string): enum: automatic, square, round, rounded, radius | automatic | no |  |
| `ShapeRadius` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |

## DovetailMortise

> Definition of a dovetail mortise

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `StartDepth` | `WidthType` (double): 0.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `Angle2NType` (double): -180.0 … 180.0 | 0.0 | no |  |
| `Slope` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `LimitationTop` | `LimitationTopType` (string): enum: limited, unlimited, pocket | limited | no |  |
| `LengthLimitedBottom` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 80.0 | no |  |
| `Width` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Depth` | `LengthSType` (double): 0.0 … 1000.0 | 28.0 | no |  |
| `ConeAngle` | `ConeAngleType` (double): 0.0 … 30.0 | — | no |  |
| `UseFlankAngle` | `BooleanType` (string): enum: yes, no | no | no |  |
| `FlankAngle` | `FlankAngleType` (double): 5.0 … 35.0 | 15.0 | no |  |
| `Shape` | `TenonShapeType` (string): enum: automatic, square, round, rounded, radius | automatic | no |  |
| `ShapeRadius` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |

## JapaneseTenon

> Definition of a Japanese tenon (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `Width1` | `LengthType` (double): 0.0 … 100000.0 | 40.0 | no |  |
| `Length1` | `LengthType` (double): 0.0 … 100000.0 | 50.0 | no |  |
| `Width2` | `LengthType` (double): 0.0 … 100000.0 | 60.0 | no |  |
| `Length2` | `LengthType` (double): 0.0 … 100000.0 | 50.0 | no |  |
| `Width3` | `LengthType` (double): 0.0 … 100000.0 | 40.0 | no |  |
| `ConeAngle` | `ConeAngleType` (double): 0.0 … 30.0 | 0.0 | no |  |
| `MiddlePlane` | `LengthType` (double): 0.0 … 100000.0 | 0.0 | no |  |
| `Offset` | `LengthType` (double): 0.0 … 100000.0 | 30.0 | no |  |
| `UseLap` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `LapOffset` | `LengthType` (double): 0.0 … 100000.0 | 10.0 | no |  |
| `LapDepth` | `LengthType` (double): 0.0 … 100000.0 | 20.0 | no |  |

## JapaneseMortise

> Definition of a Japanese mortise

*(no own parameters — inherits the shared base only)*

## Marking

> Definition of a marking

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `Angle2NType` (double): -180.0 … 180.0 | 0 | no |  |
| `LengthLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `Width` | `WidthType` (double): 0.0 … 50000.0 | 100.0 | no |  |
| `InteriorAngle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Style` | `MarkingStyleType` (string): enum: single, double, square | single | no |  |

## Text

> Definition of a text

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `Angle2NType` (double): -180.0 … 180.0 | 0 | no |  |
| `AlignmentVertical` | `AlignmentVerticalType` (string): enum: bottom, center, top | bottom | no |  |
| `AlignmentHorizontal` | `AlignmentHorizontalType` (string): enum: left, center, right | left | no |  |
| `AlignmentMultiline` | `AlignmentHorizontalType` (string): enum: left, center, right | left | no |  |
| `StackedMarking` | `BooleanType` (string): enum: yes, no | no | no |  |
| `TextHeightAuto` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `TextHeight` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `Text` | string | — | yes |  |

## SimpleScarf

> Definition of a simple scarf (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 200.0 | no |  |
| `DepthRefSide` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `DepthOppSide` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `NumDrillHole` | byte: 0 … 2 | 0 | no |  |
| `DrillHoleDiam1` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |
| `DrillHoleDiam2` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |

## ScarfJoint

> Definition of a scarf joint (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `Inclination` | `Inclination3Type` (double): 0.0 … 90.0 | — | no |  |
| `LapLength` | `WidthType` (double): 0.0 … 50000.0 | 100.0 | no |  |
| `LapDepth` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 200.0 | no |  |
| `DepthOppSide` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `ScarfShape` | `ScarfShapeType` (string): enum: refside, baseside, classic | refside | no |  |
| `NumDrillHole` | byte: 0 … 2 | 0 | no |  |
| `DrillHoleDiam1` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |
| `DrillHoleDiam2` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |

## StepJoint

> Definition of a step joint (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StrutInclination` | `AngleType` (double): 0.1 … 179.9 | — | no |  |
| `StepDepth` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `HeelDepth` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `StepShape` | `StepShapeType` (string): enum: double, step, heel, taperedheel | double | no |  |
| `Tenon` | `BooleanType` (string): enum: yes, no | no | no |  |
| `TenonWidth` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `TenonHeight` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |

## StepJointNotch

> Definition of a step joint notch

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `StrutInclination` | `AngleType` (double): 0.1 … 179.9 | — | no |  |
| `NotchLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `NotchWidth` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `StepDepth` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `HeelDepth` | `WidthType` (double): 0.0 … 50000.0 | 20.0 | no |  |
| `StrutHeight` | `WidthType` (double): 0.0 … 50000.0 | 200.0 | no |  |
| `StepShape` | `StepShapeType` (string): enum: double, step, heel, taperedheel | double | no |  |
| `Mortise` | `BooleanType` (string): enum: yes, no | no | no |  |
| `MortiseWidth` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `MortiseHeight` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |

## ProfileFront

> Definition of a profile front

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `ArcShape` | `ArcShapeType` (string): enum: convex, concave | convex | no |  |
| `Depth` | `LengthSType` (double): 0.0 … 1000.0 | 0.0 | no |  |
| `StartRotation` | `Inclination2Type` (double): -90.0 … 90.0 | 0.0 | no |  |
| `Rotation1` | `Angle2Type` (double): 0.0 … 180.0 | 90.0 | no |  |
| `Radius1` | `LengthSType` (double): 0.0 … 1000.0 | 250.0 | no |  |
| `Rotation2` | `Angle2Type` (double): 0.0 … 180.0 | 90.0 | no |  |
| `Radius2` | `LengthSType` (double): 0.0 … 1000.0 | 250.0 | no |  |

## ProfileCambered

> Definition of a profile head cambered

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `Length` | `LengthType` (double): 0.0 … 100000.0 | 0.0 | no |  |
| `StartDepth` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `MaxDepth` | `LengthSType` (double): 0.0 … 1000.0 | 60.0 | no |  |
| `MinDepth` | `LengthSType` (double): 0.0 … 1000.0 | 10.0 | no |  |
| `EndDepth` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Premill` | `PremillType` (string): enum: round, angular | angular | no |  |

## RoundArch

> Definition of a round arch

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `Length` | `LengthType` (double): 0.0 … 100000.0 | 500.0 | no |  |
| `Camber` | `LengthSType` (double): 0.0 … 1000.0 | 30.0 | no |  |
| `ArcShape` | `ArcShapeType` (string): enum: convex, concave | concave | no |  |
| `Premill` | `PremillType` (string): enum: round, angular | angular | no |  |

## Planing

> Definition of a planing

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `Length` | `LengthType` (double): 0.0 … 100000.0 | 0.0 | no |  |
| `Depth` | double: 0.0 … 50.0 | 1.0 | no |  |
| `StartLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `EndLimited` | `BooleanType` (string): enum: yes, no | no | no |  |
| `PlaneSide1` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `PlaneSide2` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `PlaneSide3` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `PlaneSide4` | `BooleanType` (string): enum: yes, no | yes | no |  |

## ProfileHead

> Definition of a profile head

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `Arc1` | inline complex (extends `ProfileArcType`) | — | yes |  |
| `Arc2` | complex → see `ProfileArcType` | — | no |  |
| `LapLength` | `LengthSType` (double): 0.0 … 1000.0 | 10.0 | no |  |
| `LapHeight` | `LengthSType` (double): 0.0 … 1000.0 | 10.0 | no |  |

## Sphere

> Definition of a sphere

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 60.0 | no |  |
| `StartDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 60.0 | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 50.0 | no |  |
| `Radius` | `WidthType` (double): 0.0 … 50000.0 | 50.0 | no |  |
| `StartOffset` | `WidthType` (double): 0.0 … 50000.0 | 0.0 | no |  |

## TriangleCut

> Definition of a triangle cut

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 60.0 | no |  |
| `StartDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 60.0 | no |  |
| `Normal1X` | `WidthNType` (double): -50000.0 … 50000.0 | 1.0 | no |  |
| `Normal1Y` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `Normal1Z` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `Normal2X` | `WidthNType` (double): -50000.0 … 50000.0 | 1.0 | no |  |
| `Normal2Y` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |
| `Normal2Z` | `WidthNType` (double): -50000.0 … 50000.0 | 0.0 | no |  |

## TyroleanDovetail

> Definition of a tyrolean dovetail (separating if CutOff = yes, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `CutOff` | `BooleanType` (string): enum: yes, no | no | no |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthType` (double): 0.0 … 50000.0 | 30.0 | no |  |
| `StartDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `Angle` | `AngleType` (double): 0.1 … 179.9 | — | no |  |
| `Slope` | double: 0.0 … 45.0 | — | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 150.0 | no |  |
| `RebateLength` | `WidthType` (double): 0.0 … 50000.0 | 10.0 | no |  |
| `Height` | `WidthType` (double): 0.0 … 50000.0 | 60 | no |  |
| `LapPosition` | `EdgePositionType` (string): enum: refedge, oppedge | refedge | no |  |
| `LapExit` | `LapExitType` (string): enum: none, mitre, rebate | mitre | no |  |
| `Shape` | `TyroleanDovetailShapeType` (string): enum: angular, straight | angular | no |  |
| `ProcessSide` | `ProcessSideType` (string): enum: both, refside, oppside | both | no |  |
| `Frosch` | inline complex (children: Depth, Width) | — | no | choice |
| `Klingschrot` | inline complex (children: ArcLength, Radius) | — | no | choice |

## Dovetail

> Definition of a dovetail (separating if CutOff = yes, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `CutOff` | `BooleanType` (string): enum: yes, no | no | no |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthType` (double): 0.0 … 50000.0 | 30.0 | no |  |
| `StartDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `Slope` | double: 0.0 … 45.0 | — | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 150.0 | no |  |
| `RebateLength` | `WidthType` (double): 0.0 … 50000.0 | 10.0 | no |  |
| `HeightRefSide` | `WidthType` (double): 0.0 … 50000.0 | 60 | no |  |
| `HeightOppSide` | `WidthType` (double): 0.0 … 50000.0 | 30.0 | no |  |
| `LapPosition` | `EdgePositionType` (string): enum: refedge, oppedge | refedge | no |  |
| `LapExit` | `LapExitType` (string): enum: none, mitre, rebate | mitre | no |  |
| `Shape` | `DovetailShapeType` (string): enum: european, american | european | no |  |
| `ProcessSide` | `ProcessSideType` (string): enum: both, refside, oppside | both | no |  |

## FreeContour

> Definition of a base contour (either a contour or a contour with associated contour)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolID` | unsignedInt | — | no |  |
| `@CounterSink` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@ToolPosition` | `ToolPositionType` (string): enum: left, center, right | — | yes |  |
| `Contour` | inline complex (+ `SingleContourAttributes`, `FreeContourAttributes`; children: Arc, Line, MachiningLimits, NURBS, StartPoint) | — | no | choice |
| `DualContour` | inline complex (+ `FreeContourAttributes`; children: Arc, AssociatedContour, Line, MachiningLimits, NURBS, PrincipalContour, StartPoint) | — | no | choice |
| `Apertures` | inline complex (+ `SingleContourAttributes`, `FreeContourAttributes`; children: Aperture, Arc, AssociatedContour, Contour, DualContour, Line, NURBS, PrincipalContour, …) | — | no | Apertures are only allowed if the Contour is closed |

## SawContour

> Definition of a base contour (either a contour or a contour with associated contour)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolID` | unsignedInt | — | no |  |
| `@ToolPosition` | `ToolPositionType` (string): enum: left, center, right | — | yes |  |
| `Contour` | inline complex (+ `SingleContourAttributes`, `SawOrMillContourAttributes`; children: Arc, Line, MachiningLimits, NURBS, StartPoint) | — | no | choice |
| `DualContour` | inline complex (+ `SawOrMillContourAttributes`; children: Arc, AssociatedContour, Line, MachiningLimits, NURBS, PrincipalContour, StartPoint) | — | no | choice |

## MillContour

> Definition of a mill contour

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolID` | unsignedInt | — | no |  |
| `@CounterSink` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@ToolPosition` | `ToolPositionType` (string): enum: left, center, right | — | yes |  |
| `Contour` | inline complex (+ `SingleContourAttributes`, `SawOrMillContourAttributes`; children: Arc, Line, MachiningLimits, NURBS, StartPoint) | — | no | choice |
| `DualContour` | inline complex (+ `SawOrMillContourAttributes`; children: Arc, AssociatedContour, Line, MachiningLimits, NURBS, PrincipalContour, StartPoint) | — | no | choice |
| `Apertures` | inline complex (+ `SingleContourAttributes`, `SawOrMillContourAttributes`; children: Aperture, Arc, AssociatedContour, Contour, DualContour, Line, NURBS, PrincipalContour, …) | — | no | Apertures are only allowed if the Contour is closed |

## NailContour

> Definition of a nail contour

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolID` | unsignedInt | — | no |  |
| `Contour` | inline complex (+ `NailContourAttributes`; children: Arc, Line, NURBS, StartPoint) | — | yes |  |

## CrampContour

> Definition of a cramp contour

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolID` | unsignedInt | — | no |  |
| `Contour` | inline complex (+ `CrampContourAttributes`, `NailContourAttributes`; children: Arc, Line, NURBS, StartPoint) | — | yes |  |

## ScrewContour

> Definition of a screw contour

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolID` | unsignedInt | — | no |  |
| `Contour` | inline complex (+ `NailContourAttributes`; children: Arc, Line, NURBS, StartPoint) | — | yes |  |

## PenContour

> Definition of a pen contour

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolID` | unsignedInt | — | no |  |
| `Contour` | complex → see `SimpleContour1Type` | — | yes |  |

## GlueArea

> Definition of a glue area (closed polygon)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolID` | unsignedInt | — | no |  |
| `@GlueType` | string | — | no |  |
| `@GlueAmount` | double: 0.0 (excl) … ∞ | — | no |  |
| `Contour` | complex → see `SimpleContourBase2Type` | — | yes |  |
| `Apertures` | inline complex (children: Aperture) | — | no |  |

## PlaningArea

> Definition of a planing area (closed polygon)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolID` | unsignedInt | — | no |  |
| `@Depth` | `LengthSType` (double): 0.0 … 1000.0 | — | no |  |
| `Contour` | complex → see `SimpleContourBase2Type` | — | yes |  |
| `Apertures` | inline complex (children: Aperture) | — | no |  |

## PlasterArea

> Definition of a plaster area (closed polygon)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolID` | unsignedInt | — | no |  |
| `@Thickness` | `LengthSType` (double): 0.0 … 1000.0 | — | no |  |
| `Contour` | complex → see `SimpleContourBase2Type` | — | yes |  |
| `Apertures` | inline complex (children: Aperture) | — | no |  |

## InsulationArea

> Definition of a insulation area (closed polygon)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@PartRefGUID` | `GUIDType` (string) | — | yes | GUID of the referenced insulation part |
| `Contour` | complex → see `SimpleContourBase2Type` | — | yes |  |
| `Apertures` | inline complex (children: Aperture) | — | no |  |

## LockoutArea

> Definition of a lockout area (closed polygon)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ForMarking` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@ForMilling` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@ForSawing` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@ForNailing` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@ForGluing` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@ForPlaning` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@ForPlastering` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@ForInsulation` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@ForFreeContour` | `BooleanType` (string): enum: yes, no | — | no |  |
| `Contour` | complex → see `SimpleContourBase2Type` | — | yes |  |

## FreeSurface

> Definition of a free NURBS surface

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ToolID` | unsignedInt | — | no |  |
| `Surface` | complex → see `NURBSPatchType` | — | yes |  |

## Variant

> Definition of a variant

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | no |  |
| `CutOff` | `BooleanType` (string): enum: yes, no | no | no |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | — | no |  |
| `StartY` | `LengthPosType` (double): -100000.0 … 100000.0 | — | no |  |
| `StartDepth` | `LengthPosType` (double): -100000.0 … 100000.0 | — | no |  |
| `VariantParameter` | complex → see `ParameterType` | — | yes |  |

## PatternContour

> Definition of a pattern contour

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `InsertionPatterns` | inline complex (children: InsertionPattern) | — | yes |  |
| `Contour` | inline complex (+ `PatternContourAttributes`; children: Arc, Line, StartPoint) | — | yes |  |

---

# Shared base (all processings)

## (base) ProcessingType

> Definition of a machining to be executed on the superior part

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ReferencePlaneID` | unsignedInt: 1 … ∞ | — | yes | can refer to a global reference plane (1-6) or a user defined reference plane (100-) |

## (base) ProcessingBaseType

> Definition of a machining to be executed on the superior part

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@Name` | string | — | yes |  |
| `@Process` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@ProcessingQuality` | `ProcessingQualityType` (string): enum: automatic, visible, fast | — | no |  |
| `@Recess` | `RecessAdvType` (string): enum: automatic, manual, exact, directionLength, directionWidth, directionDiagonal, … (7 values) | — | no |  |
| `@Priority` | int | — | no |  |
| `@ProcessID` | unsignedInt | — | yes |  |
| `@Comment` | string | — | no |  |
| `UserAttributes` | inline complex (children: UserAttribute) | — | no |  |

---

# Auxiliary complex types referenced above

## `DovetailMortiseType`

> Definition of a dovetail mortise

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `StartDepth` | `WidthType` (double): 0.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `Angle2NType` (double): -180.0 … 180.0 | 0.0 | no |  |
| `Slope` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `LimitationTop` | `LimitationTopType` (string): enum: limited, unlimited, pocket | limited | no |  |
| `LengthLimitedBottom` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 80.0 | no |  |
| `Width` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Depth` | `LengthSType` (double): 0.0 … 1000.0 | 28.0 | no |  |
| `ConeAngle` | `ConeAngleType` (double): 0.0 … 30.0 | — | no |  |
| `UseFlankAngle` | `BooleanType` (string): enum: yes, no | no | no |  |
| `FlankAngle` | `FlankAngleType` (double): 5.0 … 35.0 | 15.0 | no |  |
| `Shape` | `TenonShapeType` (string): enum: automatic, square, round, rounded, radius | automatic | no |  |
| `ShapeRadius` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |

## `DovetailTenonType`

> Definition of a dovetail tenon (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `StartDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `Angle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Rotation` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `LengthLimitedTop` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `LengthLimitedBottom` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 80.0 | no |  |
| `Width` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Height` | `LengthSType` (double): 0.0 … 1000.0 | 28.0 | no |  |
| `ConeAngle` | `ConeAngleType` (double): 0.0 … 30.0 | — | no |  |
| `UseFlankAngle` | `BooleanType` (string): enum: yes, no | no | no |  |
| `FlankAngle` | `FlankAngleType` (double): 5.0 … 35.0 | 15.0 | no |  |
| `Shape` | `TenonShapeType` (string): enum: automatic, square, round, rounded, radius | automatic | no |  |
| `ShapeRadius` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |

## `MachiningLimitType`

> Definition of the limited faces of a processing

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@FaceLimitedStart` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@FaceLimitedEnd` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@FaceLimitedFront` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@FaceLimitedBack` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@FaceLimitedTop` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@FaceLimitedBottom` | `BooleanType` (string): enum: yes, no | — | no |  |

## `MortiseType`

> Definition of a mortise

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `StartDepth` | `WidthType` (double): 0.0 … 50000.0 | 0.0 | no |  |
| `Angle` | `Angle2NType` (double): -180.0 … 180.0 | 0.0 | no |  |
| `Slope` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `LengthLimitedTop` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `LengthLimitedBottom` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 80.0 | no |  |
| `Width` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Depth` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Shape` | `TenonShapeType` (string): enum: automatic, square, round, rounded, radius | automatic | no |  |
| `ShapeRadius` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |

## `NURBSPatchType`

> Definition of a NURBS patch

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@DegreeU` | positiveInteger | — | yes | degree in U |
| `@DegreeV` | positiveInteger | — | yes | degree in V |
| `@CountU` | positiveInteger | — | yes | number of control points in U |
| `@CountV` | positiveInteger | — | yes | number of control points in V |
| `ControlPoints` | inline complex (children: ControlPoint) | — | yes | the list of control points is organized row wise with CountV rows and CountU control points per row, i.e.: CP(U=0, V=0), CP(U=1, V=0), ..., CP(U=CountU-1, V=0), CP(U=0, V=1), ..., CP(U=CountU-1, V=1), ... |
| `KnotsU` | `KnotListType` (KnotListType) | — | yes | number of knots in U = Count in U + Degree in U |
| `KnotsV` | `KnotListType` (KnotListType) | — | yes | number of knots in V = Count in V + Degree in V |

## `ParameterType`

> Definition of a parameter in a variant

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@Name` | string | — | yes |  |
| `Value` | `LengthPosType` (double): -100000.0 … 100000.0 | — | no |  |
| `StringValue` | string | — | no |  |

## `ProfileArcType`

> Definition of a profile arc

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@ArcShape` | `ArcShapeType` (string): enum: convex, concave | — | no |  |
| `@LapLength` | `LengthSType` (double): 0.0 … 1000.0 | — | no |  |
| `@LapHeight` | `LengthSType` (double): 0.0 … 1000.0 | — | no |  |
| `@Displacement` | `LengthSType` (double): 0.0 … 1000.0 | — | no |  |
| `QuarterArc` | inline complex | — | yes |  |
| `Segment` | inline complex | — | yes |  |

## `SawCutMachiningLimitType`

> Definition of the limited faces of a processing

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@FaceLimitedStart` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@FaceLimitedEnd` | `BooleanType` (string): enum: yes, no | — | no |  |
| `@FaceLimitedBottom` | `BooleanType` (string): enum: yes, no | — | no |  |

## `SimpleContour1Type`

> Definition of a simple contour (one point and multiple lines and arcs)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartPoint` | complex → see `PointType` | — | yes |  |
| `Line` | complex → see `LineType` | — | no | choice |
| `Arc` | complex → see `ArcType` | — | no | choice |
| `NURBS` | complex → see `NURBSCurveType` | — | no | choice; the first control point U=0 has to be identical to the endpoint of the previous segment |

## `SimpleContourBase2Type`

> Definition of a simple contour (one point and multiple lines and arcs)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `StartPoint` | complex → see `PointType` | — | yes |  |
| `Line` | complex → see `LineBaseType` | — | no | choice |
| `Arc` | complex → see `ArcBaseType` | — | no | choice |
| `NURBS` | complex → see `NURBSCurveBaseType` | — | no | choice; the first control point U=0 has to be identical to the endpoint of the previous segment |

## `TenonType`

> Definition of a tenon (separating, see graphical documentation)

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `Orientation` | `OrientationType` (string): enum: start, end | — | yes |  |
| `StartX` | `LengthPosType` (double): -100000.0 … 100000.0 | 0.0 | no |  |
| `StartY` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `StartDepth` | `WidthNType` (double): -50000.0 … 50000.0 | 50.0 | no |  |
| `Angle` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Inclination` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `Rotation` | `AngleType` (double): 0.1 … 179.9 | 90.0 | no |  |
| `LengthLimitedTop` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `LengthLimitedBottom` | `BooleanType` (string): enum: yes, no | yes | no |  |
| `Length` | `WidthType` (double): 0.0 … 50000.0 | 80.0 | no |  |
| `Width` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Height` | `LengthSType` (double): 0.0 … 1000.0 | 40.0 | no |  |
| `Shape` | `TenonShapeType` (string): enum: automatic, square, round, rounded, radius | automatic | no |  |
| `ShapeRadius` | `LengthSType` (double): 0.0 … 1000.0 | 20.0 | no |  |
| `Chamfer` | `BooleanType` (string): enum: yes, no | no | no |  |

## `ArcType`

> Definition of a contour arc

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@Process` | `BooleanType` (string): enum: yes, no | — | no |  |
| `PointOnArc` | complex → see `CoordinateType` | — | yes |  |

## `LineType`

> Definition of a contour line

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@Process` | `BooleanType` (string): enum: yes, no | — | no |  |

## `NURBSCurveType`

> Definition of a NURBS curve

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@Process` | `BooleanType` (string): enum: yes, no | — | no |  |

## `PointType`

> Definition of a contour point

*(no own parameters — inherits the shared base only)*

## `ArcBaseType`

> Definition of a contour arc

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `PointOnArc` | complex → see `CoordinateType` | — | yes |  |

## `LineBaseType`

> Definition of a contour line

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `EndPoint` | complex → see `CoordinateType` | — | yes |  |

## `NURBSCurveBaseType`

> Definition of a NURBS curve

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@Degree` | positiveInteger | — | yes | degree |
| `@Count` | positiveInteger | — | yes | number of control points |
| `ControlPoints` | inline complex (children: ControlPoint) | — | yes | list of control points ordered from 0 to Count-1 |
| `Knots` | `KnotListType` (KnotListType) | — | yes | number of knots = Count + Degree |

## `CoordinateType`

> Definition of a vector or point

| Parameter | Type / range | Default | Required | Notes |
|---|---|---|---|---|
| `@X` | double | — | yes |  |
| `@Y` | double | — | yes |  |
| `@Z` | double | — | yes |  |

---

# Attribute groups (carried by contour segment elements)

## `SingleContourAttributes`

> group of attributes for single contours

| Attribute | Type / range | Default |
|---|---|---|
| `@Inclination` | `InclinationType` (double): -89.9 … 89.9 | 0.0 |

## `FreeContourAttributes`

> group of attributes for free contours

| Attribute | Type / range | Default |
|---|---|---|
| `@Recess` | `ContourRecessType` (string): enum: automatic, noPassOver, passOverStart, passOverEnd, passOverAll | — |
| `@FaceLimited` | `BooleanType` (string): enum: yes, no | yes |

## `SawOrMillContourAttributes`

> group of attributes for saw and mill contours

| Attribute | Type / range | Default |
|---|---|---|
| `@Recess` | `ContourRecessType` (string): enum: automatic, noPassOver, passOverStart, passOverEnd, passOverAll | — |
| `@FaceLimited` | `BooleanType` (string): enum: yes, no | yes |

## `NailContourAttributes`

> group of attributes for nail contours

| Attribute | Type / range | Default |
|---|---|---|
| `@NailSpacing` | `LengthType` (double): 0.0 … 100000.0 | — |

## `CrampContourAttributes`

> group of attributes for cramp contours

| Attribute | Type / range | Default |
|---|---|---|
| `@CrampAngleRef` | `CrampAngleRefType` (string): enum: segment, part, grain | segment |
| `@CrampAngle` | `AngleNType` (double): -179.9 … 179.9 | — |

## `PatternContourAttributes`

> group of attributes for pattern contours

| Attribute | Type / range | Default |
|---|---|---|
| `@NodeSpacing` | `LengthType` (double): 0.0 … 100000.0 | 0 |
| `@NodeAtStart` | `BooleanType` (string): enum: yes, no | yes |
| `@NodeAtEnd` | `BooleanType` (string): enum: yes, no | yes |

