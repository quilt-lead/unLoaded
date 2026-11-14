"""Synthetic CSI 3-part project manual (structural divisions) for the v2 designed building.

    write(exp, d, path)   # called by synth.v2.generate

Cover, table of contents, then one section per CSI MasterFormat number (01 45 33, 03 20 00,
03 30 00, 05 05 19, 05 05 23, 05 12 00, 05 31 00, 07 81 00) in the 3-part format: PART 1
GENERAL / PART 2 PRODUCTS / PART 3 EXECUTION, articles 1.1.., paragraphs A., B., sub-
paragraphs 1., 2.; running header (project) and footer ("05 12 00 - 3"). The article text is
written for this synthetic project (no master-spec text is copied); section numbers and titles
are the public MasterFormat ones.

Articles govern TYPES, materials and systems, never instances. Each paragraph names what it
governs (a material, a section type family, a typical detail, a frame or a deck) and that is
recorded as:
- exp["spec_articles"]: one entry per paragraph, id "SPEC:05 12 00/2.1.A", with page + bbox
- exp["relations"]: {src: <governed id>, dst: <spec id>, kind: "specified-by"}
- exp["occurrences"]: doc "specs", how "spec_article", for the spec id and each governed id
- exp["spec_sections"]: section number, title, first / last page

Byte-stable: base-14 fonts only, fixed metadata, deterministic order.
"""
from __future__ import annotations

import pymupdf

W, H = 612.0, 792.0
ROMAN, BOLD = "tiro", "tibo"
_FONT = {ROMAN: pymupdf.Font("tiro"), BOLD: pymupdf.Font("tibo"), "helv": pymupdf.Font("helv")}
ASC, DESC = _FONT[ROMAN].ascender, _FONT[ROMAN].descender
LM, RM, TOP, BOT = 72.0, W - 72.0, 86.0, H - 70.0
SIZE, LEAD = 10.0, 12.6
PROJECT = "HARBOR VIEW OFFICE BUILDING"
PROJECT_NO = "2611-SYN"
ISSUE = "PERMIT SUBMITTAL - 10/23/2026 / PLAN CHECK RESPONSE 1 - 11/14/2026"
FIRM = "QUILLFEATHER STRUCTURAL ENGINEERS"


def tlen(s: str, size: float = SIZE, font: str = ROMAN) -> float:
    return _FONT[font].text_length(s, fontsize=size)


def r2(v: float) -> float:
    return round(v, 2)


def wrap(s: str, width: float, size: float = SIZE, font: str = ROMAN) -> list[str]:
    out, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if cur and tlen(t, size, font) > width:
            out.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        out.append(cur)
    return out


# =========================================================================== content
def content(exp: dict) -> list[dict]:
    """The spec book as data. A paragraph is (text, governs, [subparagraphs])."""
    types = exp["types"]
    w_types = [t["id"] for t in types if t.get("kind") == "section" and t.get("material") == "MAT:A992"]
    hss = [t["id"] for t in types if t.get("kind") == "section" and t.get("material") == "MAT:A500C"]
    st = [t["id"] for t in types if t["id"].startswith("DETAIL:ST-")]
    dc = [t["id"] for t in types if t["id"].startswith("DETAIL:DC-")]
    bg = [t["id"] for t in types if t["id"].startswith("DETAIL:BG-")]
    bp = [t["id"] for t in types if t["id"].startswith("DETAIL:BP-")]
    piers = [t["id"] for t in types if t.get("kind") == "pier"]
    frames = [e["id"] for e in exp["elements"] if e["type"] == "frame"]
    smf = [f for f in frames if "SMF" in f]
    scbf = [f for f in frames if "SCBF" in f]
    floor_decks = [e["id"] for e in exp["elements"] if e["type"] == "deck" and e["level"] != "RF"]
    roof_deck = [e["id"] for e in exp["elements"] if e["type"] == "deck" and e["level"] == "RF"]
    crit = next(r["values"] for r in exp["records"] if r["id"] == "A1-CRIT")
    smf_lines = ", ".join(f.split("-")[-1] for f in smf)
    scbf_lines = ", ".join(f.split("-")[-1] for f in scbf)
    w_list = ", ".join(t.split(":")[1] for t in w_types)
    hss_list = ", ".join(t.split(":")[1] for t in hss)

    def P(text, governs=(), subs=()):
        return {"text": text, "governs": list(governs), "subs": list(subs)}

    def A(title, *paras):
        return {"title": title, "paras": list(paras)}

    return [
        {"no": "01 45 33", "title": "CODE-REQUIRED SPECIAL INSPECTIONS", "parts": [
            ("GENERAL", [
                A("SUMMARY",
                  P("This Section describes the special inspections and tests required by Chapter 17 of the building code "
                    "for the structural work, and the Contractor's obligations to facilitate them. The Owner engages the "
                    "special inspector and testing agency."),
                  P("Related Sections: 03 20 00 Concrete Reinforcing; 03 30 00 Cast-in-Place Concrete; 05 05 19 "
                    "Post-Installed Concrete Anchors; 05 05 23 Metal Fastenings; 05 12 00 Structural Steel Framing; "
                    "05 31 00 Steel Decking; 07 81 00 Applied Fireproofing.")),
                A("REFERENCES",
                  P("Building code: " + crit["codes"].split(",")[0].strip() + ", Chapter 17, as amended by the "
                    "jurisdiction."),
                  P("Steel: AISC 360-16 Chapter N and AISC 341-16 Chapter J (quality control and quality assurance)."),
                  P("Concrete: ACI 318-19 Chapter 26 (construction documents and inspection).")),
                A("DEFINITIONS",
                  P("Continuous special inspection: the inspector is present in the area where the work is performed "
                    "for the full duration of that work."),
                  P("Periodic special inspection: part-time or intermittent observation, with a final observation of the "
                    "completed work before it is concealed.")),
                A("QUALITY ASSURANCE",
                  P("Special inspectors shall be qualified for each inspection they perform (AWS CWI for welding, ICC "
                    "certification for concrete and bolting) and independent of the Contractor."),
                  P("Testing agency: accredited to ISO/IEC 17025 for the tests it performs.")),
                A("SUBMITTALS",
                  P("Inspection reports: distribute to the Owner, Architect, Engineer and building official within seven "
                    "days of each inspection, listing discrepancies and their resolution."),
                  P("Final report: a signed statement that the inspected work conforms to the approved construction "
                    "documents, before final inspection.")),
            ]),
            ("PRODUCTS", [A("NOT USED", P("Products are specified in the related Sections."))]),
            ("EXECUTION", [
                A("STRUCTURAL STEEL",
                  P("Material identification and fabrication: periodic inspection of shapes, plates and HSS against the "
                    "approved shop drawings and mill certificates.", ["MAT:A992", "MAT:A500C", "MAT:A36"]),
                  P(f"Special moment frames (lines {smf_lines}): continuous inspection of demand critical complete joint "
                    "penetration (CJP) groove welds at beam flange to column connections MC-1, and ultrasonic testing of "
                    "100 percent of those welds after cooling.", smf + ["DETAIL:MC-1", "MAT:E70XX"],
                    ["Verify the reduced beam section (RBS) cut geometry and surface finish before welding.",
                     "Verify that backing bars are removed, the root back-gouged and reinforced, and weld tabs removed."]),
                  P(f"Special concentrically braced frames (line {scbf_lines}): continuous inspection of gusset plate "
                    "welds and brace end connections; verify the gusset clearance zone.", scbf + bg),
                  P("High-strength bolting: observe pre-installation verification; periodic inspection of snug-tight joints; "
                    "continuous inspection of pretensioned and slip-critical joints in the seismic force-resisting system.",
                    ["MAT:F3125-A325"] + dc),
                  P("Protected zones: verify that no welds, attachments, shot pins or holes are placed within the protected "
                    "zone of any RBS.", ["DETAIL:MC-1"])),
                A("CONCRETE AND REINFORCING",
                  P("Reinforcing: periodic inspection of size, grade, spacing, cover and lap length before each placement.",
                    ["MAT:REBAR-A615"]),
                  P("Concrete: continuous inspection of placement; sample and test at the point of placement for slump, air, "
                    "temperature and unit weight, and cast strength specimens.", ["MAT:CONC-4000", "MAT:CONC-LW3000"]),
                  P("Anchor rods: periodic inspection of anchor rod size, grade, projection and position before concrete is "
                    "placed.", ["MAT:F1554"] + bp)),
                A("STEEL DECK AND STUDS",
                  P("Periodic inspection of deck attachment (welds, side-lap fasteners) and of headed stud welding, "
                    "including the daily bend tests.", floor_decks + roof_deck + ["MAT:DECK-3VLI20", "MAT:STUD"])),
                A("SPRAYED FIRE-RESISTANT MATERIALS",
                  P("Periodic inspection of surface condition, thickness, density and bond strength of sprayed "
                    "fire-resistant material.", ["MAT:SFRM"])),
                A("NONCONFORMING WORK",
                  P("Work found not to conform shall be corrected and re-inspected at the Contractor's expense. Do not "
                    "conceal work before the special inspector has accepted it.")),
            ]),
        ]},
        {"no": "03 20 00", "title": "CONCRETE REINFORCING", "parts": [
            ("GENERAL", [
                A("SUMMARY",
                  P("This Section includes reinforcing bars and welded wire reinforcement for footings, piers, grade beams, "
                    "slab on grade and concrete fill on metal deck.")),
                A("REFERENCES",
                  P("ACI 318-19; ACI SP-66 (detailing manual); CRSI Manual of Standard Practice.")),
                A("SUBMITTALS",
                  P("Shop drawings: placing drawings showing bar marks, sizes, bends, laps and supports for every footing "
                    "mark, pier type and grade beam mark shown on the drawings."),
                  P("Mill certificates for each heat of reinforcing delivered.", ["MAT:REBAR-A615"])),
            ]),
            ("PRODUCTS", [
                A("REINFORCING",
                  P("Deformed bars: ASTM A615, Grade 60, uncoated.", ["MAT:REBAR-A615"]),
                  P("Welded wire reinforcement in concrete fill on metal deck: ASTM A1064, 6x6-W2.9xW2.9, flat sheets.",
                    floor_decks),
                  P("Tie wire: 16 gauge annealed steel.")),
                A("ACCESSORIES",
                  P("Bar supports: plastic or plastic-tipped wire chairs; concrete bricks on grade for footing mats. Do not "
                    "use wood, brick or rock to support reinforcing.")),
                A("FABRICATION",
                  P("Fabricate to the tolerances of ACI 117; bend bars cold. Standard hooks and seismic hooks per ACI 318.",
                    ["MAT:REBAR-A615"]),
                  P("Pier ties: closed hoops with 135-degree seismic hooks at piers supporting the seismic force-resisting "
                    "system.", piers)),
            ]),
            ("EXECUTION", [
                A("PLACEMENT",
                  P("Place, support and tie reinforcing so it does not move during concrete placement.",
                    subs=["Clear cover: 3 in. for concrete cast against earth; 2 in. formed and exposed; 1-1/2 in. to pier "
                          "ties.",
                          "Center welded wire reinforcement in the concrete fill above the deck ribs."]),
                  P("Grade beam bars: continuous through footings with Class B lap splices staggered; hook top and bottom "
                    "bars into the end footings.", ["MAT:REBAR-A615"])),
                A("SPLICES",
                  P("Lap splices only where shown or permitted. Do not weld reinforcing bars. Mechanical splices only with "
                    "the Engineer's written acceptance.")),
                A("FIELD QUALITY CONTROL",
                  P("Special inspection per Section 01 45 33. Notify the inspector 24 hours before each placement.",
                    ["MAT:REBAR-A615"])),
            ]),
        ]},
        {"no": "03 30 00", "title": "CAST-IN-PLACE CONCRETE", "parts": [
            ("GENERAL", [
                A("SUMMARY",
                  P("This Section includes concrete for spread footings, piers, grade beams, slab on grade, base plate "
                    "grout and lightweight concrete fill on composite steel deck.")),
                A("REFERENCES",
                  P("ACI 301-20, ACI 318-19, ACI 117, ACI 304R (measuring, mixing, placing), ACI 308.1 (curing).")),
                A("SUBMITTALS",
                  P("Mix designs for each class of concrete with field strength test records or trial batches establishing "
                    "the required average strength.", ["MAT:CONC-4000", "MAT:CONC-LW3000"])),
            ]),
            ("PRODUCTS", [
                A("MATERIALS",
                  P("Portland cement: ASTM C150, Type II. Fly ash: ASTM C618 Class F, maximum 20 percent of cementitious "
                    "content."),
                  P("Normal weight aggregate: ASTM C33. Lightweight aggregate: ASTM C330.", ["MAT:CONC-LW3000"]),
                  P("Admixtures: ASTM C494, chloride free. Air entrainment not required (interior, no freeze-thaw "
                    "exposure).")),
                A("CONCRETE MIXES",
                  P("Footings, piers and grade beams: f'c = 4,000 psi at 28 days, normal weight, maximum w/cm 0.50, slump "
                    "4 in. plus or minus 1 in.", ["MAT:CONC-4000"] + piers),
                  P("Slab on grade: f'c = 4,000 psi, normal weight, maximum w/cm 0.48, shrinkage-reducing admixture "
                    "permitted.", ["MAT:CONC-4000"]),
                  P("Concrete fill on metal deck: f'c = 3,000 psi lightweight, equilibrium density 110 pcf plus or minus "
                    "3 pcf, slump 5 in. maximum.", ["MAT:CONC-LW3000"] + floor_decks)),
                A("RELATED MATERIALS",
                  P("Non-shrink grout under base plates: ASTM C1107, non-metallic, 5,000 psi at 28 days.", bp),
                  P("Vapor retarder under slab on grade: ASTM E1745 Class A, 15 mil.")),
            ]),
            ("EXECUTION", [
                A("PREPARATION",
                  P("Footing excavations shall be observed by the geotechnical engineer before reinforcing is placed. "
                    "Remove water, loose soil and debris.")),
                A("PLACEMENT",
                  P("Place concrete continuously between construction joints. Consolidate with internal vibrators. Do not "
                    "drop concrete more than 5 ft.", ["MAT:CONC-4000"]),
                  P("Deck pours: place fill so that the construction live load on the deck does not exceed the deck "
                    "manufacturer's limits; screed to the specified total thickness, not to a level surface where the "
                    "framing deflects.", floor_decks + ["MAT:CONC-LW3000"]),
                  P("Base plate grout: place after columns are plumbed and leveling nuts set; dry-pack or flow from one "
                    "side to avoid voids.", bp)),
                A("CURING",
                  P("Keep concrete moist for at least seven days, or apply a membrane curing compound compatible with "
                    "finishes.")),
                A("FIELD QUALITY CONTROL",
                  P("Strength tests: one set of cylinders for each 50 cubic yards or each day's placement of each class, "
                    "whichever is more; acceptance per ACI 318 Section 26.12.", ["MAT:CONC-4000", "MAT:CONC-LW3000"])),
            ]),
        ]},
        {"no": "05 05 19", "title": "POST-INSTALLED CONCRETE ANCHORS", "parts": [
            ("GENERAL", [
                A("SUMMARY",
                  P("This Section includes mechanical and adhesive anchors installed in hardened concrete, for attachments "
                    "shown on the drawings and for corrective work. Post-installed anchors shall not replace cast-in "
                    "anchor rods at column base plates without the Engineer's written acceptance.", bp)),
                A("REFERENCES",
                  P("ACI 318-19 Chapter 17; ACI 355.2 (mechanical anchors); ACI 355.4 (adhesive anchors); ICC-ES AC193 and "
                    "AC308.")),
                A("SUBMITTALS",
                  P("Current ICC-ES evaluation reports showing qualification for cracked concrete and seismic design "
                    "categories C through F."),
                  P("Installer certification (ACI/CRSI Adhesive Anchor Installer) for adhesive anchors installed "
                    "horizontally or overhead under sustained tension.")),
            ]),
            ("PRODUCTS", [
                A("ANCHORS",
                  P("Mechanical expansion and screw anchors: qualified per ACI 355.2 for cracked concrete and seismic "
                    "loads, carbon steel, zinc plated."),
                  P("Adhesive anchors: qualified per ACI 355.4 for the installation conditions; threaded rod ASTM F1554 "
                    "Grade 36 or ASTM A193 Grade B7 as noted.", ["MAT:F1554"])),
            ]),
            ("EXECUTION", [
                A("INSTALLATION",
                  P("Install per the manufacturer's printed installation instructions (MPII), including hole diameter, "
                    "depth, cleaning and torque."),
                  P("Locate existing reinforcing by non-destructive scanning before drilling. Do not cut reinforcing; if "
                    "reinforcing is encountered, abandon the hole, fill with grout and relocate.", ["MAT:REBAR-A615"])),
                A("FIELD QUALITY CONTROL",
                  P("Proof load 10 percent of anchors of each type and size to the load shown, minimum one per group. "
                    "Continuous special inspection of adhesive anchors under sustained tension per Section 01 45 33.")),
            ]),
        ]},
        {"no": "05 05 23", "title": "METAL FASTENINGS", "parts": [
            ("GENERAL", [
                A("SUMMARY",
                  P("This Section includes high-strength bolts, nuts and washers, anchor rods, welding electrodes and headed "
                    "shear studs used in the structural steel and steel deck work.")),
                A("REFERENCES",
                  P("RCSC Specification for Structural Joints Using High-Strength Bolts (2020); AWS D1.1, AWS D1.8 and AWS "
                    "D1.3; ASTM F3125, F1554, A563, F436 and A108.")),
                A("SUBMITTALS",
                  P("Manufacturer's certified test reports for bolts, nuts, washers and anchor rods, by lot.",
                    ["MAT:F3125-A325", "MAT:F1554"]),
                  P("Welding procedure specifications and filler metal certificates, including Charpy V-notch data for "
                    "demand critical welds.", ["MAT:E70XX"])),
            ]),
            ("PRODUCTS", [
                A("HIGH-STRENGTH BOLTS",
                  P("Bolts: ASTM F3125 Grade A325, Type 1, heavy hex, plain finish, 3/4 in. diameter unless noted.",
                    ["MAT:F3125-A325"] + st,
                    ["Nuts: ASTM A563 Grade DH, heavy hex.", "Washers: ASTM F436, hardened."]),
                  P("Direct tension indicators: ASTM F959 compressible-washer type, permitted for pretensioned joints.",
                    ["MAT:F3125-A325"])),
                A("ANCHOR RODS",
                  P("Gravity column base plates: ASTM F1554 Grade 36, headed or with a heavy hex nut and plate washer at "
                    "the embedded end.", ["MAT:F1554"] + [b for b in bp if b.endswith(("1", "2"))]),
                  P("Seismic force-resisting system base plates: ASTM F1554 Grade 55 with supplementary requirement S1 "
                    "(weldability).", ["MAT:F1554"] + [b for b in bp if b.endswith(("3", "4"))])),
                A("WELDING ELECTRODES",
                  P("E70XX low hydrogen electrodes and equivalent FCAW/SMAW filler metals, AWS A5.1, A5.20 or A5.29.",
                    ["MAT:E70XX"]),
                  P("Demand critical welds: filler metal with Charpy V-notch toughness of 20 ft-lb at minus 20 deg F and "
                    "40 ft-lb at 70 deg F, per AWS D1.8.", ["MAT:E70XX", "DETAIL:MC-1"] + bg)),
                A("HEADED SHEAR STUDS",
                  P("3/4 in. diameter headed studs, ASTM A108, AWS D1.1 Type B, length after welding as shown.",
                    ["MAT:STUD"])),
            ]),
            ("EXECUTION", [
                A("BOLT INSTALLATION",
                  P("Snug-tight joints: single-plate shear tab connections ST-2 through ST-7, with short-slotted holes in "
                    "the plate.", st),
                  P("Pretensioned joints: all bolted joints in the seismic force-resisting system, including drag "
                    "connections and SMF shear plates, by turn-of-nut, calibrated wrench or direct tension indicator.",
                    dc + ["DETAIL:MC-1", "MAT:F3125-A325"]),
                  P("Slip-critical joints: Class A faying surfaces, unpainted, where noted on the drawings. Perform "
                    "pre-installation verification for each lot and method.", ["MAT:F3125-A325"])),
                A("WELDING",
                  P("Weld per AWS D1.1; welds in the seismic force-resisting system also per AWS D1.8.", smf + scbf),
                  P("CJP groove welds at RBS beam flanges: remove backing bars, back-gouge to sound metal and reinforce "
                    "with a 5/16 in. fillet; remove weld tabs and grind smooth.", ["DETAIL:MC-1"] + smf),
                  P("Headed studs: weld through the deck with automatic stud welding equipment; bend-test the first two "
                    "studs of each shift to 15 degrees.", ["MAT:STUD"])),
            ]),
        ]},
        {"no": "05 12 00", "title": "STRUCTURAL STEEL FRAMING", "parts": [
            ("GENERAL", [
                A("SUMMARY",
                  P("This Section includes structural steel framing: floor and roof beams and girders, columns, base "
                    f"plates, special moment frames on lines {smf_lines}, special concentrically braced frames on line "
                    f"{scbf_lines}, collectors, and their connections.", frames),
                  P("Related Sections: 05 05 23 Metal Fastenings; 05 31 00 Steel Decking; 07 81 00 Applied Fireproofing; "
                    "01 45 33 Code-Required Special Inspections.")),
                A("REFERENCES",
                  P("AISC 303-22 Code of Standard Practice; AISC 360-16; AISC 341-16 Seismic Provisions; AISC 358-16 "
                    "Prequalified Connections; RCSC 2020; AWS D1.1 and D1.8.")),
                A("DEFINITIONS",
                  P("Seismic force-resisting system (SFRS): members marked with an asterisk on the drawings, and their "
                    "connections.", frames),
                  P("Protected zone: the region of an SMF beam from the column face to the far end of the RBS cut, where "
                    "attachments are prohibited.", ["DETAIL:MC-1"])),
                A("SUBMITTALS",
                  P("Shop and erection drawings: member sizes, camber, stud counts, connection types per the typical "
                    "details, and SFRS members identified."),
                  P("Mill certificates for all shapes, HSS and plates; welding procedure specifications.",
                    ["MAT:A992", "MAT:A500C", "MAT:A36"])),
                A("QUALITY ASSURANCE",
                  P("Fabricator: AISC Certified (Building Fabricator). Erector: AISC Certified Steel Erector, or equivalent "
                    "quality program accepted by the building official."),
                  P("Welders: qualified per AWS D1.1 for the processes and positions used; per AWS D1.8 Annex for demand "
                    "critical welds.", ["MAT:E70XX"])),
            ]),
            ("PRODUCTS", [
                A("MATERIALS",
                  P("W shapes: ASTM A992, Fy = 50 ksi. Sizes on this project: " + w_list + ".", ["MAT:A992"] + w_types),
                  P("Hollow structural sections: ASTM A500 Grade C, Fy = 50 ksi. Sizes on this project: " + hss_list + ".",
                    ["MAT:A500C"] + hss),
                  P("Plates, angles and channels: ASTM A36 unless noted. Gusset, continuity and doubler plates: ASTM A572 "
                    "Grade 50.", ["MAT:A36"] + bg),
                  P("SFRS members shall be produced to the expected yield strength ratios of AISC 341 Table A3.1; heat "
                    "numbers traceable to the member.", frames)),
                A("FABRICATION",
                  P("Camber: fabricate beams with the midspan camber shown (c=X\") with the camber up; tolerance minus 0, "
                    "plus 1/2 in.", ["MAT:A992"]),
                  P("Shear connections: single-plate shear tabs ST-2 through ST-7 per the typical details, with the bolt "
                    "count shown for the end reaction.", st),
                  P("Reduced beam sections: thermally cut to the dimensions on detail MC-1 and ground to a surface "
                    "roughness of 1,000 microinches or smoother, with no notches; corners rounded.", ["DETAIL:MC-1"]),
                  P("Brace gussets: provide the 2t linear clearance zone for brace buckling; slot HSS braces and fit "
                    "without gaps over 1/16 in.", bg + hss),
                  P("Drag connections DC-1 through DC-3: shop weld drag plates to columns; field bolt to collector beams.",
                    dc),
                  P("Base plates: mill or plane bearing surfaces over 4 in. thick; anchor rod holes oversized per AISC "
                    "Table 14-2 with plate washers.", bp)),
                A("SHOP PRIMING",
                  P("Do not prime steel that will receive sprayed fire-resistant material or that forms a slip-critical "
                    "faying surface.", ["MAT:SFRM"]),
                  P("Steel exposed in the finished work: one coat of shop primer compatible with the finish system.")),
            ]),
            ("EXECUTION", [
                A("ERECTION",
                  P("Erect per AISC 303. Set base plates on leveling nuts; grout after the frame is plumbed and the deck "
                    "is attached.", bp),
                  P("Provide temporary bracing until the deck diaphragm, frames and braces are complete.", frames),
                  P("Column plumbness: 1/500 of the height between splice points, per AISC 303.")),
                A("SEISMIC FORCE-RESISTING SYSTEM",
                  P("Do not field splice braces. Do not make field holes, welds or attachments in protected zones.",
                    ["DETAIL:MC-1"] + scbf),
                  P("Report any RBS cut, CJP weld or gusset deviation to the Engineer before proceeding.",
                    smf + scbf)),
                A("FIELD QUALITY CONTROL",
                  P("Special inspection and testing per Section 01 45 33; correct rejected work and retest.", frames)),
            ]),
        ]},
        {"no": "05 31 00", "title": "STEEL DECKING", "parts": [
            ("GENERAL", [
                A("SUMMARY",
                  P("This Section includes composite steel floor deck at Level 2 and Level 3, steel roof deck, and deck "
                    "accessories.", floor_decks + roof_deck)),
                A("REFERENCES",
                  P("SDI C-2017 (composite deck), SDI RD-2017 (roof deck), SDI Diaphragm Design Manual, AWS D1.3, ASTM "
                    "A653.")),
                A("SUBMITTALS",
                  P("Shop drawings: deck layout, gauge, attachment pattern, pour stops, openings and reinforcing at "
                    "openings."),
                  P("Product data and ICC-ES report for the deck and side-lap fasteners.", ["MAT:DECK-3VLI20"])),
            ]),
            ("PRODUCTS", [
                A("COMPOSITE FLOOR DECK",
                  P("3 in. deep composite deck, 20 gauge, ASTM A653 SS Grade 50, G60 galvanized, embossed, interlocking "
                    "side laps.", ["MAT:DECK-3VLI20"] + floor_decks),
                  P("Concrete fill: 3-1/4 in. lightweight concrete above the ribs (6-1/4 in. total) per Section 03 30 00.",
                    ["MAT:CONC-LW3000"] + floor_decks)),
                A("ROOF DECK",
                  P("1-1/2 in. wide rib (Type B) roof deck, 20 gauge, ASTM A653 SS Grade 50, G60 galvanized.",
                    roof_deck + ["MAT:DECK-3VLI20"])),
                A("ACCESSORIES",
                  P("Pour stops, cell closures and column closures of the same material, minimum 20 gauge; pour stop gauge "
                    "per the SDI pour stop table for the slab edge overhang.")),
            ]),
            ("EXECUTION", [
                A("INSTALLATION",
                  P("Bear deck at least 1-1/2 in. on supporting steel. Lap ends over supports or butt over supports as "
                    "shown.", floor_decks + roof_deck),
                  P("Attach with 5/8 in. effective diameter arc spot welds in a 36/4 pattern at supports and side-lap "
                    "fasteners at 12 in. on center, or as required for the diaphragm shear.", floor_decks + roof_deck),
                  P("Weld headed shear studs through the deck to the beam flange; studs count toward deck attachment.",
                    ["MAT:STUD"])),
                A("DIAPHRAGM",
                  P("The deck is the floor and roof diaphragm; transfer forces to collectors and drag connections as "
                    "shown. Do not omit attachments at collector lines.", floor_decks + roof_deck + dc)),
                A("REPAIR",
                  P("Repair damaged galvanizing with zinc-rich paint, ASTM A780.")),
            ]),
        ]},
        {"no": "07 81 00", "title": "APPLIED FIREPROOFING", "parts": [
            ("GENERAL", [
                A("SUMMARY",
                  P("This Section includes sprayed fire-resistant material (SFRM) on structural steel columns, beams, "
                    "girders and braces to achieve the fire-resistance ratings shown on the architectural drawings.",
                    ["MAT:SFRM"])),
                A("REFERENCES",
                  P("UL Fire Resistance Directory; ASTM E119; ASTM E605 (thickness and density); ASTM E736 (bond "
                    "strength).")),
                A("SUBMITTALS",
                  P("Product data and the UL design for each rated assembly, with thickness schedules by member size.",
                    ["MAT:SFRM"] + w_types + hss)),
            ]),
            ("PRODUCTS", [
                A("SPRAYED FIRE-RESISTANT MATERIAL",
                  P("Cementitious SFRM, minimum dry density 15 pcf, minimum bond strength 150 psf, asbestos free.",
                    ["MAT:SFRM"]),
                  P("Thickness: as required by the listed design for the member size and rating; columns and braces "
                    "2-hour, floor and roof framing 1-hour unless the architectural drawings show otherwise.",
                    ["MAT:SFRM"] + w_types + hss)),
            ]),
            ("EXECUTION", [
                A("PREPARATION",
                  P("Surfaces shall be clean, dry and unprimed unless the primer is listed for the design.", ["MAT:SFRM"]),
                  P("Do not apply SFRM to SMF protected zones or slip-critical faying surfaces until the special "
                    "inspector has accepted the welding and bolting.", ["DETAIL:MC-1"] + smf)),
                A("APPLICATION",
                  P("Apply after the deck and roofing are installed and the space is enclosed, above 40 deg F.",
                    ["MAT:SFRM"])),
                A("FIELD QUALITY CONTROL",
                  P("Thickness and density per ASTM E605 and bond strength per ASTM E736 on each floor, per Section "
                    "01 45 33.", ["MAT:SFRM"])),
            ]),
        ]},
    ]


# =========================================================================== writer
class Book:
    def __init__(self, exp: dict):
        self.exp = exp
        self.doc = pymupdf.open()
        self.page = None
        self.y = TOP
        self.sec = None
        self.sec_page = 0

    def text(self, x, y, s, size=SIZE, font=ROMAN, anchor="l") -> list[float]:
        w = tlen(s, size, font)
        if anchor == "c":
            x -= w / 2
        elif anchor == "r":
            x -= w
        self.page.insert_text((x, y), s, fontname=font, fontsize=size)
        a = _FONT[font].ascender
        d = _FONT[font].descender
        return [r2(x), r2(y - a * size), r2(x + w), r2(y - d * size)]

    def new_page(self):
        self.page = self.doc.new_page(width=W, height=H)
        self.sec_page += 1
        self.text(LM, 40, PROJECT, 8, "helv")
        self.text(RM, 40, f"PROJECT NO. {PROJECT_NO}", 8, "helv", anchor="r")
        self.text(LM, 50, ISSUE, 7, "helv")
        self.page.draw_line((LM, 55), (RM, 55), width=0.5)
        self.page.draw_line((LM, H - 52), (RM, H - 52), width=0.5)
        self.text(LM, H - 40, self.sec["title"], 8.5, "helv")
        self.text(RM, H - 40, f"{self.sec['no']} - {self.sec_page}", 9, "helv", anchor="r")
        self.text(W / 2, H - 28, "SAMPLE - SYNTHETIC PROJECT MANUAL - NOT FOR CONSTRUCTION", 6, "helv", anchor="c")
        self.y = TOP

    def need(self, h):
        if self.y + h > BOT:
            self.new_page()

    def lines(self, x_label, label, x_text, s, size=SIZE, font=ROMAN) -> list[float]:
        ls = wrap(s, RM - x_text, size, font)
        self.need(LEAD * min(len(ls), 2))
        boxes = []
        if label:
            self.text(x_label, self.y, label, size, font)
        for ln in ls:
            self.need(LEAD)
            boxes.append((self.doc.page_count, self.text(x_text, self.y, ln, size, font)))
            self.y += LEAD
        return boxes

    def write(self) -> None:
        exp = self.exp
        exp.setdefault("occurrences", [])
        exp.setdefault("spec_articles", [])
        exp.setdefault("spec_sections", [])
        sections = content(exp)
        self.doc.new_page(width=W, height=H)     # cover, written last
        self.doc.new_page(width=W, height=H)     # table of contents, written once page counts are known
        rels = []
        for sec in sections:
            self.sec = sec
            self.sec_page = 0
            self.new_page()
            first = self.doc.page_count
            self.text(W / 2, self.y, f"SECTION {sec['no']} - {sec['title']}", 11.5, BOLD, anchor="c")
            self.y += LEAD * 2
            for pn, (part, arts) in enumerate(sec["parts"], 1):
                self.need(LEAD * 4)
                self.text(LM, self.y, f"PART {pn} - {part}", SIZE, BOLD)
                self.y += LEAD * 1.6
                for an, art in enumerate(arts, 1):
                    self.need(LEAD * 3)
                    ano = f"{pn}.{an}"
                    self.text(LM, self.y, ano, SIZE, BOLD)
                    self.text(LM + 36, self.y, art["title"], SIZE, BOLD)
                    self.y += LEAD * 1.4
                    for k, para in enumerate(art["paras"]):
                        letter = chr(ord("A") + k)
                        boxes = self.lines(LM + 36, f"{letter}.", LM + 58, para["text"])
                        for sn, sub in enumerate(para["subs"], 1):
                            boxes += self.lines(LM + 58, f"{sn}.", LM + 80, sub)
                        self.y += LEAD * 0.5
                        self._record(sec, ano, art["title"], letter, para, boxes, rels)
                    self.y += LEAD * 0.4
            self.need(LEAD * 3)
            self.y += LEAD
            self.text(W / 2, self.y, f"END OF SECTION {sec['no']}", SIZE, BOLD, anchor="c")
            exp["spec_sections"].append({"section": sec["no"], "title": sec["title"], "page": first,
                                         "page_end": self.doc.page_count, "pages": self.doc.page_count - first + 1})
        exp["relations"].extend(rels)
        self._cover(self.doc[0])
        self._toc(self.doc[1], exp["spec_sections"])

    def _record(self, sec, ano, atitle, letter, para, boxes, rels):
        exp = self.exp
        sid = f"SPEC:{sec['no']}/{ano}.{letter}"
        text = " ".join([para["text"]] + [f"{n}. {s}" for n, s in enumerate(para["subs"], 1)])
        page = boxes[0][0]
        on_first = [b for p, b in boxes if p == page]
        bbox = [min(b[0] for b in on_first), min(b[1] for b in on_first), max(b[2] for b in on_first), max(b[3] for b in on_first)]
        exp["spec_articles"].append({"id": sid, "section": sec["no"], "section_title": sec["title"], "article": ano,
                                     "paragraph": letter, "title": atitle, "text": text, "page": page, "bbox": bbox,
                                     "governs": list(dict.fromkeys(para["governs"]))})
        for ref in [sid] + list(dict.fromkeys(para["governs"])):
            exp["occurrences"].append({"ref": ref, "doc": "specs", "page": page, "sheet": sec["no"], "bbox": bbox,
                                       "how": "spec_article", "text": text})
        for g in dict.fromkeys(para["governs"]):
            rels.append({"src": g, "dst": sid, "kind": "specified-by"})

    def _cover(self, page):
        self.page = page
        page.draw_rect(pymupdf.Rect(54, 54, W - 54, H - 54), width=1.5)
        self.text(W / 2, 200, "PROJECT MANUAL", 26, BOLD, anchor="c")
        self.text(W / 2, 250, PROJECT, 18, ROMAN, anchor="c")
        self.text(W / 2, 274, "1200 Tidewater Way, Port Calder, CA 90000", 11, ROMAN, anchor="c")
        self.text(W / 2, 330, "STRUCTURAL SPECIFICATIONS", 14, BOLD, anchor="c")
        self.text(W / 2, 350, "DIVISIONS 01, 03, 05 AND 07 (STRUCTURAL SECTIONS)", 11, ROMAN, anchor="c")
        self.text(W / 2, 410, f"PROJECT NO. {PROJECT_NO}", 11, ROMAN, anchor="c")
        self.text(W / 2, 428, ISSUE, 9, ROMAN, anchor="c")
        self.text(W / 2, 520, "STRUCTURAL ENGINEER", 8, "helv", anchor="c")
        self.text(W / 2, 536, FIRM, 11, BOLD, anchor="c")
        self.text(W / 2, 551, "410 Lantern Row, Suite 3, Port Calder, CA 90000", 9, ROMAN, anchor="c")
        self.text(W / 2, 590, "ARCHITECT", 8, "helv", anchor="c")
        self.text(W / 2, 606, "MARROW & FINCH ARCHITECTS", 11, BOLD, anchor="c")
        page.draw_circle((W / 2, 680), 40, width=0.8)
        self.text(W / 2, 678, "SAMPLE", 12, BOLD, anchor="c")
        self.text(W / 2, 690, "NO SEAL", 7, "helv", anchor="c")

    def _toc(self, page, secs):
        self.page = page
        self.text(W / 2, 90, "TABLE OF CONTENTS", 14, BOLD, anchor="c")
        self.text(W / 2, 108, PROJECT + " - STRUCTURAL SECTIONS", 10, ROMAN, anchor="c")
        y = 150
        div_names = {"01": "DIVISION 01 - GENERAL REQUIREMENTS", "03": "DIVISION 03 - CONCRETE",
                     "05": "DIVISION 05 - METALS", "07": "DIVISION 07 - THERMAL AND MOISTURE PROTECTION"}
        self.text(RM, y - 20, "PAGES", 8, BOLD, anchor="r")
        last = None
        for s in secs:
            div = s["section"][:2]
            if div != last:
                y += 10
                self.text(LM, y, div_names[div], 10, BOLD)
                y += 18
                last = div
            self.text(LM + 18, y, s["section"], SIZE)
            self.text(LM + 90, y, s["title"], SIZE)
            pg = f"{s['pages']}"
            x0 = LM + 90 + tlen(s["title"]) + 6
            x1 = RM - tlen(pg) - 6
            dots = "." * max(0, int((x1 - x0) / tlen(".")))
            self.text(x0, y, dots, SIZE)
            self.text(RM, y, pg, SIZE, anchor="r")
            y += 16
        self.text(LM, y + 30, "END OF TABLE OF CONTENTS", 9, BOLD)

    def save(self, path):
        self.doc.set_metadata({
            "title": "Project manual (structural) - Harbor View Office Building (synthetic)", "author": "calc-graph synth",
            "subject": "Synthetic CSI 3-part specifications with ground truth", "creator": "calc-graph synth generator",
            "producer": "PyMuPDF", "creationDate": "D:20261114090000-05'00'", "modDate": "D:20261114090000-05'00'",
            "keywords": "",
        })
        self.doc.save(path, garbage=3, deflate=True, no_new_id=True)


def write(exp: dict, d: dict, path: str) -> dict:
    b = Book(exp)
    b.write()
    b.save(path)
    return {"pages": b.doc.page_count, "articles": len(exp["spec_articles"]),
            "specified_by": sum(1 for r in exp["relations"] if r["kind"] == "specified-by")}
