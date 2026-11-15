import { describe, expect, it } from "vitest";
import { normaliseProfile, profileFromText } from "../src/index.ts";
import { createKindResolver } from "../src/kind-map.ts";

describe("profile designation", () => {
  it.each([
    ["Beam W12x26 typ", "W12X26"],
    ["HSS6x6x3/8", "HSS6X6X3/8"],
    ["IPE 300", "IPE300"],
    ["HEA200", "HEA200"],
    ["305x165x40 UB", "305X165X40UB"],
    ["GL24h 600 x 300", "600X300"],
    ["W310×97", "W310X97"],
  ])("%s -> %s", (text, expected) => {
    expect(profileFromText([text])).toBe(expected);
  });
  it("returns undefined without a designation", () => {
    expect(profileFromText(["girder", undefined])).toBeUndefined();
  });
  it("normalises", () => {
    expect(normaliseProfile(" hea 200 ")).toBe("HEA200");
    expect(normaliseProfile("600 × 300")).toBe("600X300");
  });
});

describe("kind resolution", () => {
  const k = createKindResolver();
  const kind = (ifcType: string, predefinedType?: string, ...names: string[]) => k.resolve({ ifcType, predefinedType, names }).kind;
  it("maps by type, predefined type and name", () => {
    expect(kind("IfcMember", "BRACE")).toBe("brace");
    expect(kind("IfcMember", "STUD")).toBe("other");
    expect(kind("IfcMember", "NOTDEFINED")).toBe("brace");
    expect(kind("IfcMechanicalFastener")).toBe("fastener");
    expect(kind("IfcBuildingElementProxy", undefined, "Shear Tab ST-1")).toBe("connection");
    expect(kind("IfcBuildingElementProxy", undefined, "origin")).toBe("other");
    expect(kind("IfcElementAssembly", "USERDEFINED", "Base plate BP3")).toBe("connection");
    expect(kind("IfcPlate", "CURTAIN_PANEL")).toBe("other");
    expect(kind("ifcwallstandardcase")).toBe("wall");
    expect(k.handles("IfcChimney")).toBe(false);
  });
});
