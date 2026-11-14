# Structural schema: BHoM and Speckle mapping

calc-graph's structural analysis types live in `backend/calcgraph/schema/structural.py`. They
take their shape from BHoM Structure_oM, the most complete open structural object model. This
page maps each of our types and fields to:

- **BHoM**: Structure_oM, plus the Spatial_oM profiles and the ETABS_Toolkit `ETABSId` fragment.
- **Speckle v2**: the typed `Objects.Structural` kit.
- **Speckle v3**: what the current SDK and the CSi connector actually emit.

The point is that a future BHoM or Speckle adapter only has to follow this table.

Sources were read on 2026-11-14. We read class shapes only and copied no source code: BHoM is
LGPL-3.0, and this repo is Apache-2.0.

- BHoM: `github.com/BHoM/BHoM` (develop): `Structure_oM/**`, `Spatial_oM/ShapeProfiles/*`,
  `BHoM/Base`. Serialiser behaviour comes from `github.com/BHoM/BHoM_Engine` (develop):
  `Serialiser_Engine/Compute/Serialise/*`.
- ETABS adapter fragment: `github.com/BHoM/ETABS_Toolkit` (develop): `ETABS_oM/Fragments/ETABSId.cs`.
- Speckle v2: `github.com/specklesystems/speckle-sharp`, `Objects/Objects/Structural/**`. That repo
  is **archived** (last push 2025-07-11).
- Speckle v3: `github.com/specklesystems/speckle-sharp-sdk` (`src/Speckle.Sdk/Objects/Models/Data/*`,
  `src/Speckle.Sdk.BundleMigrator/Migration/StructuralResultsMigrator.cs`,
  `src/Speckle.Sdk.Parquet/.../StructuralResultsWriter.cs`) and
  `github.com/specklesystems/speckle-sharp-connectors`
  (`Converters/CSi/Speckle.Converters.CSiShared/ToSpeckle/Helpers/*`).

## What we found about Speckle (verified in source)

- **The typed structural kit is gone from the current SDK.** `Objects.Structural.*` (Node,
  Element1D, Restraint, Property1D, SectionProfile, StructuralMaterial, LoadCase,
  LoadCombination, LoadBeam/LoadNode/LoadFace/LoadGravity, Result1D/ResultNode/ResultGlobal,
  Model) exists only in the archived `speckle-sharp`. It is absent from `speckle-sharp-sdk` and
  from `specklepy` main, which has no structural module at all.
- **v3 ("next gen") CSi connectors send loose data objects.** They send
  `Objects.Data.EtabsObject` (`name`, `type`, `units`, `elements`, `displayValue`,
  `properties: dict`). Structure lives in property keys, not in types. The frame keys seen in
  the converter are `Frame Assignments - Summary`, `End Releases`, `I-End Joint`, `J-End Joint`,
  section/material/length/cross-section keys, and `Area`, `As2`, `As3`, `I22`, `I33`, `Torsion`.
  The joint keys are `Restraints` with `UX..RZ Restrained`.
- **v3 analysis results** sit on the CSi root as `analysisResults`, a nested dict per result type
  (`frameForces`, `jointReact`, `baseReact`, `modalPeriodsAndFrequencies`, `pierForces`,
  `spandrelForces`, ...). Each is grouped by `Elm` / `LoadCase` / `ElmSta` / `StepNum`, with leaf
  keys taken from the ETABS tables (`P`, `V2`, `V3`, `T`, `M2`, `M3`).
- **A v4 bundle format is in development.** It flattens results into an EAV table
  (`*.eav.structural_results.parquet`: `object_index`, `element_name`, `location`,
  `result_type`, `load_case`, `component`, `position_label`, `station`, `step`, `value`,
  `value_text`).

So the **Speckle v3** column below names property keys and result keys, not classes. We have not
seen a real v3 CSi payload, so the exact key nesting is **unverified**. It needs one captured
send from the desk's Speckle ETABS connector.

## Conventions that differ (read before mapping)

| Topic | BHoM | calc-graph | Speckle v2 |
|---|---|---|---|
| Units | SI everywhere (m, N, N·m, Pa, rad, kg/m³) | any unit in the closed vocabulary; every number is a `Quantity`, and each field checks its dimension | per-object `units` string |
| Section axes | y = major, z = minor (`Iy` = strong axis) | x = major, y = minor (US: `Ix` = strong) | `Iyy` major / `Izz` minor (per kit doc) |
| Release semantics | `BarRelease` per DOF: `Fixed` = connected, `Free` = released; `Release = null` means fully fixed | same as BHoM (`EndReleases`) | `Restraint.code` per end, 6 letters (`F` fixed, `R` released, `K` spring) |
| ETABS releases | n/a | `EndReleases.from_etabs_released` inverts (ETABS: True = released) | n/a |
| Density | mass density kg/m³ | weight density (`unit_weight`, force/volume); converted ×g0 = 9.80665 m/s², and the rule text says so | `density` (unit per model) |
| Positions | `Point` in the model's metres | `Point3` in a named frame: `ModelM(doc)` for a BHoM or ETABS export, `BuildingFt(set)` for drawing-derived models | `Point` + units |
| Ids | `BHoM_Guid`, plus adapter ids in `Fragments` (`ETABSId`: Id, Label, Story, PersistentId) | stable string id; the external identity is kept in `refs: [ExternalRef]` | `applicationId`, `id` (hash) |
| Provenance | none | mandatory on every type (`Provenance`); results also carry `source` | none |

## Mapping table

Legend: ✓ verified in source on 2026-11-14 · ? not verified · — no counterpart.

### Constraints: supports, end releases, offsets

| calc-graph | BHoM | Speckle v2 | Speckle v3 (CSi) |
|---|---|---|---|
| `Fixity6` | `Constraints.Constraint6DOF` ✓ | `Geometry.Restraint` ✓ | joint `Restraints` keys ✓ |
| `Fixity6.{tx,ty,tz,rx,ry,rz}.type` (`DOFType`: free, fixed, fixed-±, spring, spring-±, spring-relative-±, nonlinear, friction, damped, gap) | `TranslationX..RotationZ` (`DOFType` enum, all 14 values) ✓ | `code` letters (F/R/K only) ✓ | `UX..RZ Restrained` (bool) ✓ |
| `Dof.stiffness` (N/m-type; N·m/rad-type) | `TranslationalStiffnessX..`, `RotationalStiffnessX..` (SI) ✓ | `stiffnessX..stiffnessZZ` ✓ | — |
| `Support` (`node_id`, `fixity`) | `Elements.Node.Support` ✓ | `Node.restraint` ✓ | joint `Restraints` ✓ |
| — (reported as unmapped) | `Elements.Bar.Support` (`Constraint4DOF`, linear support) ✓ | — | — |
| `EndReleases` (`start`, `end`: `Fixity6`) | `Constraints.BarRelease` (`StartRelease`, `EndRelease`) ✓ | `Element1D.end1Releases`, `end2Releases` ✓ | frame `End Releases` (`End-I` / `End-J`) ✓ |
| `Offset` (`start`, `end`: length `QVector`, axis local) | `Offsets.Offset` (`Start`, `End` vectors, bar local axes: x tangential, z major-normal) ✓ | `end1Offset`, `end2Offset` (`Vector`) ✓ | ? (end length offsets not seen in the converter) |

### Materials and sections

| calc-graph | BHoM | Speckle v2 | Speckle v3 (CSi) |
|---|---|---|---|
| `MaterialGrade` | `MaterialFragments.Steel` / `Concrete` / `Aluminium` / `GenericIsotropicMaterial` (`IMaterialFragment`) ✓ | `Materials.StructuralMaterial` (+ `Steel`, `Concrete`) ✓ | frame property `MATERIAL` key ✓ (values ?) |
| `.kind` | the concrete type (Steel → steel ...) ✓ | `materialType` ✓ | ? |
| `.standard`, `.grade` | — (Name only) | `designCode`, `grade` ✓ | ? |
| `.E` | `YoungsModulus` (Pa) ✓ | `elasticModulus` ✓ | ? |
| `.G` | — (BHoM derives it from E and ν) | `shearModulus` ✓ | ? |
| `.nu` | `PoissonsRatio` ✓ | `poissonsRatio` ✓ | ? |
| `.unit_weight` | `Density` (kg/m³) × g0 ✓ | `density` ✓ | ? |
| `.damping_ratio` | `DampingRatio` ✓ | `dampingRatio` ✓ | — |
| `.thermal_expansion_per_degC` | `ThermalExpansionCoeff` ✓ | `thermalExpansivity` ✓ | — |
| `.fy`, `.fu` | `Steel.YieldStress`, `UltimateStress` (Pa) ✓ | `Steel.yieldStrength`, `ultimateStrength` ✓ | ? |
| `.fy_expected`, `.fu_expected` (AISC 341 Ry·Fy, Rt·Fu) | — | — | — (ETABS has them as EFy/EFu: `PropMaterial.GetOSteel`) |
| `.fc`, `.fcu` | `Concrete.CylinderStrength`, `CubeStrength` ✓ | `Concrete.compressiveStrength` ? | ? |
| `SectionPropertySet` | `SectionProperties.SteelSection` / `ConcreteSection` / `ExplicitSection` / `GenericSection` (`ISectionProperty`) ✓ | `Properties.Property1D` + `Profiles.SectionProfile` ✓ | frame `SECTION` key + section extractor ✓ |
| `.designation` | `Name` ✓ | `SectionProfile.name` / `Catalogue.sectionName` ✓ | ? |
| `.shape` | `SectionProfile` type (`ISectionProfile`, `BoxProfile`, `TubeProfile`, ...) ✓ | `shapeType` / subclass (`ISection`, `Rectangular`, `Circular`, ...) ✓ | ? |
| `.material_id` | `Material` ✓ | `Property1D.material` ✓ | `MATERIAL` ✓ |
| `.d`, `.bf`, `.tw`, `.tf`, `.t_design` | `ISectionProfile.Height/Width/WebThickness/FlangeThickness`; `BoxProfile.Thickness` ✓ | `depth`, `width`, `webThickness`, `flangeThickness`, `wallThickness` ✓ | ? |
| `.A` | `Area` ✓ | `area` ✓ | `Area` ✓ |
| `.Ix`, `.Iy` (major, minor) | `Iy`, `Iz` ✓ | `Iyy`, `Izz` ✓ | `I33`, `I22` ✓ |
| `.J` | `J` ✓ | `J` ✓ | `Torsion` ✓ (key seen; meaning ?) |
| `.Cw` | `Iw` ✓ | — | — |
| `.Sx`, `.Sy` | `Wely`, `Welz` ✓ | — | — |
| `.Zx`, `.Zy` | `Wply`, `Wplz` ✓ | — | — |
| `.rx`, `.ry` | `Rgy`, `Rgz` ✓ | — | — |
| `.Avx`, `.Avy` (shear areas) | `Asz`, `Asy` ✓ (axis pairing ? check against a BHoM-computed W shape) | `Ky`, `Kz` (shear factors, not areas) ✓ | `As2`, `As3` ✓ |
| `.weight_per_length` | — | `weight` ✓ | ? |
| (not stored) | `CentreY/Z`, `Vy/Vpy/Vz/Vpz` (BHoM recomputes them from the profile) ✓ | — | — |
| `SurfacePropertySet` (minimal) | `SurfaceProperties.ConstantThickness`, `SlabOnDeck`, ... ✓ | `Property2D` ? | shell section extractor ✓ |

### Analytical elements (and the physical split)

| calc-graph | BHoM | Speckle v2 | Speckle v3 (CSi) |
|---|---|---|---|
| `Element` (schema/models.py: the PHYSICAL member from drawings, schedules, IFC) | `Physical_oM.Elements.Beam` / `Column` / `Bracing` (`Location` curve, `Property` = `ConstantFramingProperty`: Profile, Material, OrientationAngle) ✓ | `BuiltElements.Beam/Column/Brace` (+ `Revit*`) ? | — |
| `AnalyticalNode` | `Elements.Node` (`Position`, `Orientation`, `Support`) ✓ | `Geometry.Node` (`basePoint`, `constraintAxis`, `restraint`, spring/mass/damper) ✓ | `EtabsObject` type point ✓ |
| `.position` (framed `Point3`) | `Position` (m) ✓ | `basePoint` ✓ | `displayValue` geometry ✓ |
| — (reported as unmapped if set) | `Orientation` (Basis) ✓ | `constraintAxis` ✓ | — |
| `.physical_id` | — (BHoM keeps physical and analytical apart; the link sits in the adapter) | `Element1D.parent` ✓ | — |
| `AnalyticalBar` | `Elements.Bar` ✓ | `Geometry.Element1D` ✓ | `EtabsObject` type frame ✓ |
| `.start_node`, `.end_node` | `Start`, `End` ✓ | `end1Node`, `end2Node` ✓ | `I-End Joint`, `J-End Joint` ✓ |
| `.section_id` | `SectionProperty` ✓ | `property` ✓ | `SECTION` ✓ |
| `.orientation_angle` (angle `Quantity`) | `OrientationAngle` (rad) ✓ | `orientationAngle` ✓ | ? |
| `.releases` | `Release` ✓ | `end1Releases/end2Releases` ✓ | `End Releases` ✓ |
| `.offset` | `Offset` ✓ | `end1Offset/end2Offset` ✓ | ? |
| `.fea_type` (flexural / axial / compression-only / tension-only) | `FEAType` (`BarFEAType`) ✓ | `type` (`ElementType1D`) ? | ? |
| `.usage` (beam / column / brace / cable / pile) | `StructuralUsage1D` (on physical framing) ✓ | `Property1D.memberType` ✓ | ETABS design orientation ? |
| `AnalyticalPanel` (schema only; not converted yet) | `Elements.Panel` (`ExternalEdges`, `Openings`, `Property`, `OrientationAngle`) ✓ | `Geometry.Element2D` (`topology`, `openings`, `offset`) ✓ | `EtabsObject` type shell ✓ |

### Loading

| calc-graph | BHoM | Speckle v2 | Speckle v3 (CSi) |
|---|---|---|---|
| `LoadCase` | `Loads.Loadcase` (`Name`, `Nature`, `Number`) ✓ | `Loading.LoadCase` (`name`, `loadType`, `group`, `actionType`, `description`) ✓ | load pattern names in results only ? |
| `.nature` | `Nature` (`LoadNature`: Dead, SuperDead, Live, Wind, Seismic, Temperature, Snow, Accidental, Prestress, Notional, Other) ✓. Our `roof-live` writes `Live` plus Tag `calcgraph:roof-live`, because BHoM has no roof-live value | `loadType` (`LoadType` enum) ✓ | ? |
| `.self_weight_multiplier` | — (BHoM writes self weight as a `GravityLoad`) | — | — (ETABS `LoadPatterns.GetSelfWTMultiplier`) |
| `LoadCombination` | `Loads.LoadCombination` (`LoadCases: List<Tuple<double, ICase>>`, `Number`) ✓ | `Loading.LoadCombination` (`loadCases`, `loadFactors`, `combinationType`) ✓ | ? |
| `.terms[{case_id, factor}]` | `LoadCases` items `[factor, case]` (serialised as a 2-array) ✓ | parallel lists `loadCases` / `loadFactors` ✓ | ? |
| `.kind` (linear-add / envelope / abs / srss) | — (BHoM `CaseType` enum exists; not on `LoadCombination`) | `combinationType` ✓ | ? |
| `PointLoad` | `Loads.PointLoad` (`Force`, `Moment`, `Objects`, `Axis`, `Projected`) ✓ | `Loading.LoadNode` (`nodes`, `direction`, `value`) ✓ | ? |
| `BarPointLoad` | `Loads.BarPointLoad` (`DistanceFromA`, `Force`, `Moment`) ✓ | `LoadBeam` (`loadType` = point, `values`, `positions`) ✓ | ? |
| `BarDistributedLoad` (uniform) | `Loads.BarUniformlyDistributedLoad` (`Force`, `Moment`) ✓ | `LoadBeam` (`loadType` = uniform) ✓ | ? |
| `BarDistributedLoad` (varying) | `Loads.BarVaryingDistributedLoad` (`StartPosition`, `ForceAtStart`, `MomentAtStart`, `EndPosition`, `ForceAtEnd`, `MomentAtEnd`, `RelativePositions`) ✓ | `LoadBeam` (`loadType` = linear / trapezoidal) ✓ | ? |
| `AreaLoad` (schema only; needs panels) | `Loads.AreaUniformlyDistributedLoad` (`Pressure`) ✓ | `Loading.LoadFace` ✓ | ? |
| `GravityLoad` | `Loads.GravityLoad` (`GravityDirection`) ✓ | `Loading.LoadGravity` (`gravityFactors`) ✓ | ? |
| `axis` (global / local), `projected` | `Axis` (`LoadAxis`), `Projected` ✓ | `loadAxisType`, `isProjected` ✓ | ? |

### Result requests and results

| calc-graph | BHoM | Speckle v2 | Speckle v3 (CSi) |
|---|---|---|---|
| `ResultRequest` | `Requests.BarResultRequest` / `NodeResultRequest` / `GlobalResultRequest` (`ResultType`, `Cases`, `Modes`, `ObjectIds`, `Divisions`, `DivisionType`, `Axis`) ✓ | — (connector settings) | — (connector settings) |
| `ResultSource` on every result | — | — | — |
| `BarForceResult` (`position` 0..1, `fx..mz`) | `Results.BarForce` (`ObjectId`, `ResultCase`, `ModeNumber`, `TimeStep`, `Position`, `Divisions`, `FX..MZ`) ✓ | `Results.Result1D` (`position`, `forceX..momentZZ`) ✓ | `analysisResults.frameForces` (`Elm`, `LoadCase`, `ElmSta`, `StepNum` → `P`, `V2`, `V3`, `T`, `M2`, `M3`) ✓ |
| `NodeReactionResult` | `Results.NodeReaction` (`FX..MZ`) ✓ | `ResultNode.reactionX..reactionZZ` ✓ | `analysisResults.jointReact` ✓ |
| `NodeDisplacementResult` | `Results.NodeDisplacement` (`UX..RZ`) ✓ | `ResultNode.dispX..rotZZ` ✓ | ? |
| `GlobalReactionResult` | `Results.GlobalReactions` (`FX..MZ`) ✓ | `ResultGlobal.reactionX..` ✓ | `analysisResults.baseReact` ✓ |
| `StoreyDriftResult` (`storey`, `direction` x/y, `ratio`) | `Results.StoreyDrift` (`Storey`, `Direction` vector, `Ratio`) ✓ | — | ? (a drift pivot exists in the v4 migrator) |
| `UtilisationResult` (`ratio`, `ratio_type`, `components`) | `Results.SteelUtilisation` (16 named ratios; we keep all of them in `components`, and the governing one is `ratio`) ✓. `MajorEffectiveLength`, `MinorEffectiveLength` and `SteelClass` are not mapped and are reported when set | — | ? |

## Coverage

- **Structure_oM types the converter reads and writes** (`schema/adapters/bhom_json.py`): Node,
  Bar, Constraint6DOF (supports + releases), BarRelease, Offset, Steel, Concrete, Aluminium,
  GenericIsotropicMaterial, SteelSection, ConcreteSection, ExplicitSection, GenericSection,
  Loadcase, LoadCombination, PointLoad, BarPointLoad, BarUniformlyDistributedLoad,
  BarVaryingDistributedLoad, GravityLoad, Bar/Node/GlobalResultRequest, BarForce, NodeReaction,
  NodeDisplacement, GlobalReactions, StoreyDrift, SteelUtilisation. That is **28 types**.
- **In the schema but not yet converted:** Panel, the SurfaceProperty family, AreaUniformlyDistributedLoad.
  These need curve and edge geometry; a BHoM payload containing them is reported as
  `unsupported`, never dropped silently.
- **Out of scope for now:** FEMesh, Opening, RigidLink and LinkConstraint, the temperature,
  prestress, contour, acceleration and velocity loads, mesh and modal results, FloorSystem,
  Reinforcement and Design.
- Every BHoM field the converter does not map is listed in `Report.unmapped` whenever it holds a
  non-default value. `scripts/bhom_roundtrip.py` prints this list for any payload, including a
  real capture.

## Wire format with the Windows bridge (agreed by reading `windows-bridge/calcgraph_bridge/`)

BHoM objects cross the wire as BHoM Serialiser JSON (`BH.Engine.Serialiser.Convert.ToJson`):

- Every object is `{"_t": "<full type name>", <every public property>}`. A BHoMObject adds
  `BHoM_Guid` and `Name`, and `Fragments` / `Tags` / `CustomData` only when non-empty.
- Nested objects are written in full each time; the converter de-duplicates them by `BHoM_Guid`.
- Enums are their names; an enum in an object slot is `{"_t":"System.Enum","TypeName","Value"}`.
- A `Tuple` is a JSON array, or `{"_t", "_v": [...]}` when the declared type differs.
- Values are in SI units.

| Call | Body | Reply | Adapter use |
|---|---|---|---|
| `GET /health` | n/a | `{"ok": true, "service", "version", "host", "pid", "uptime_s", "clr"}` | up / down |
| `POST /bhom/etabs/push` | `{"objects": [BHoM JSON], "tag", "model_path"?}` | `{"pushed", "echoed", "objects", "source"}` | route `bhom` send |
| `POST /bhom/etabs/pull` | `{"type": "BH.oM.Structure.Elements.Bar"}` or `{"request": <BHoM request JSON>}` | `{"count", "objects": [BHoM JSON], "adapter", "source"}` | route `bhom` pull: Node, Bar, Loadcase, LoadCombination, then BarForce / NodeReaction / StoreyDrifts requests |
| `POST /csi/start` | `{"product": "ETABS", "attach": false, "visible": false}` | `{"started", "attached", "product", "version", "source"}` | route `csi` send |
| `POST /csi/open` | `{"e2k_text": "...", "filename"}` | `{"model", "summary": {..., "present_units"}, "source"}` | route `csi`; `present_units` labels the result units |
| `POST /csi/run` | `{}` | `{"saved", "seconds", "source"}` | route `csi` |
| `POST /csi/results` | `{"kinds": [...], "cases": [], "combos": [...]}` | `{"frame_forces": [rows], "joint_reactions", "story_drifts", "steel_dc", "source"}` (OAPI by-ref output names as columns) | route `csi` pull |
| `POST /csi/call` | `{"path": "SapModel.FrameObj", "method": "GetLabelFromName", "inputs": {"Name": n}}` | the by-ref outputs (`Label`, `Story` expected; **unverified**) | maps an ETABS unique name to label@story, then to the registry id |

Errors: 503 `not_installed`, 409 `no_session`, 400 `bad_request`, 500 with the .NET text. The
adapter keeps the status and body in `job["bridge"]` and falls back to the mock or to PyNite.

**Gaps the bridge needs to close:**

- There is no "run analysis" call for the BHoM adapter's ETABS session. A BHoM push is
  therefore never analysed: `/csi/run` only knows models opened through `/csi/open`.
- `GetLabelFromName` output names are unverified.
- The CSI `eUnits` integer→unit table in `analysis/bhom_etabs.py` comes from memory and is
  unverified. Results in an unknown unit system are refused, never guessed.

## Integration edits not yet made (files owned by other agents)

- `backend/calcgraph/analysis/__init__.py`: add `"bhom_etabs"` to `ADAPTERS` and a
  `get_adapter` branch that returns `bhom_etabs.BhomEtabsAdapter(design)`.
- `backend/calcgraph/schema/__init__.py` and `models.TS_MODELS`: re-export `schema.structural`
  and append `STRUCTURAL_TS_MODELS`, so that `scripts/gen_ts_types.py` emits the structural types.
  Optionally add `structural: StructuralBundle | None` to `Bundle`.
- `models.DocKind` has no `analysis` kind for a BHoM, ETABS or Speckle export. Evidence on those
  is `ModelEvidence` against the payload's sha256, with no `Document` row yet.
