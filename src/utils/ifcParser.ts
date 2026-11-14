import { BimGraphData, BimLink, BimNode } from '../types/bim';
import { hashStringToJewelColor, IFC_ENTITY_PALETTE } from './colors';
import { normalizeGraphData } from './graphEngine';

export interface BimParserPlugin {
  id: string;
  name: string;
  extensions: string[];
  canParse: (content: string, fileName: string) => boolean;
  parse: (content: string, fileName: string) => { graph: BimGraphData; rawLinks: BimLink[] };
}

function decodeIfcStepString(raw?: string): string {
  if (!raw || raw === '$') return '';
  let s = raw.trim();
  if (s.startsWith("'") && s.endsWith("'")) s = s.slice(1, -1);
  return s
    .replace(/''/g, "'")
    .replace(/\\X2\\([0-9A-Fa-f]{4})\\X0\\/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
}

function splitStepArgs(argStr: string): string[] {
  const args: string[] = [];
  let cur = '';
  let depth = 0;
  let inStr = false;
  for (let i = 0; i < argStr.length; i++) {
    const ch = argStr[i];
    if (ch === "'") {
      inStr = !inStr;
      cur += ch;
    } else if (!inStr && ch === '(') {
      depth++;
      cur += ch;
    } else if (!inStr && ch === ')') {
      depth--;
      cur += ch;
    } else if (!inStr && depth === 0 && ch === ',') {
      args.push(cur.trim());
      cur = '';
    } else {
      cur += ch;
    }
  }
  if (cur.trim() !== '') args.push(cur.trim());
  return args;
}

export function formatIfcPascalName(upperEntity: string): string {
  const map: Record<string, string> = {
    IFCSLAB: 'IfcSlab',
    IFCCOLUMN: 'IfcColumn',
    IFCBEAM: 'IfcBeam',
    IFCWALL: 'IfcWall',
    IFCWALLSTANDARDCASE: 'IfcWall',
    IFCCURTAINWALL: 'IfcCurtainWall',
    IFCFOOTING: 'IfcFooting',
    IFCPILE: 'IfcPile',
    IFCMEMBER: 'IfcMember',
    IFCPLATE: 'IfcPlate',
    IFCMECHANICALFASTENER: 'IfcMechanicalFastener',
    IFCDISCRETEACCESSORY: 'IfcDiscreteAccessory',
    IFCROOF: 'IfcRoof',
    IFCSTAIR: 'IfcStair',
    IFCSTAIRFLIGHT: 'IfcStairFlight',
    IFCRAMP: 'IfcRamp',
    IFCRAMPFLIGHT: 'IfcRampFlight',
    IFCRAILING: 'IfcRailing',
    IFCWINDOW: 'IfcWindow',
    IFCDOOR: 'IfcDoor',
    IFCCOVERING: 'IfcCovering',
    IFCREINFORCINGBAR: 'IfcReinforcingBar',
    IFCREINFORCINGMESH: 'IfcReinforcingMesh',
    IFCTENDON: 'IfcTendon',
    IFCTENDONANCHOR: 'IfcTendonAnchor',
    IFCBUILDINGELEMENTPROXY: 'IfcBuildingElementProxy',
    IFCOPENINGELEMENT: 'IfcOpeningElement',
    IFCSPACE: 'IfcSpace',
    IFCSITE: 'IfcSite',
    IFCBUILDING: 'IfcBuilding',
    IFCDISTRIBUTIONELEMENT: 'IfcDistributionElement',
    IFCFLOWSEGMENT: 'IfcFlowSegment',
    IFCFLOWTERMINAL: 'IfcFlowTerminal',
    IFCFLOWFITTING: 'IfcFlowFitting',
    IFCFLOWCONTROLLER: 'IfcFlowController',
    IFCELEMENTASSEMBLY: 'IfcElementAssembly',
    IFCTRANSPORTELEMENT: 'IfcTransportElement',
    IFCFURNISHINGELEMENT: 'IfcFurnishingElement',
    IFCGEOGRAPHICELEMENT: 'IfcGeographicElement',
    IFCCIVILELEMENT: 'IfcCivilElement',
    IFCBRIDGEPART: 'IfcBridgePart',
    IFCALIGNMENT: 'IfcAlignment',
  };
  if (map[upperEntity]) return map[upperEntity];
  const body = upperEntity.replace(/^IFC/, '');
  return 'Ifc' + body.charAt(0) + body.slice(1).toLowerCase();
}

export function parseRawIfcStepToGraph(stepText: string, fileName: string): { graph: BimGraphData; rawLinks: BimLink[] } {
  const nonElementTypes = new Set([
    'IFCPROJECT', 'IFCOWNERHISTORY', 'IFCPERSON', 'IFCORGANIZATION', 'IFCPERSONANDORGANIZATION',
    'IFCAPPLICATION', 'IFCUNITASSIGNMENT', 'IFCSIUNIT', 'IFCCONVERSIONBASEDUNIT', 'IFCMEASUREWITHUNIT',
    'IFCDIMENSIONALEXPONENTS', 'IFCGEOMETRICREPRESENTATIONCONTEXT', 'IFCGEOMETRICREPRESENTATIONSUBCONTEXT',
    'IFCAXIS2PLACEMENT3D', 'IFCAXIS2PLACEMENT2D', 'IFCCARTESIANPOINT', 'IFCDIRECTION',
    'IFCLOCALPLACEMENT', 'IFCPRODUCTDEFINITIONSHAPE', 'IFCSHAPEREPRESENTATION',
    'IFCEXTRUDEDAREASOLID', 'IFCRECTANGLEPROFILEDEF', 'IFCCIRCLEPROFILEDEF', 'IFCISHAPEPROFILEDEF',
    'IFCARBITRARYCLOSEDPROFILEDEF', 'IFCPOLYLINE', 'IFCCOMPOSITECURVE', 'IFCFACETEDBREP',
    'IFCCLOSEDSHELL', 'IFCFACE', 'IFCFACEOUTERBOUND', 'IFCPOLYLOOP', 'IFCTRIANGULATEDFACESET',
    'IFCCARTESIANPOINTLIST3D', 'IFCRELCONTAINEDINSPATIALSTRUCTURE', 'IFCRELAGGREGATES',
    'IFCRELDEFINESBYPROPERTIES', 'IFCRELDEFINESBYTYPE', 'IFCRELASSOCIATESMATERIAL',
    'IFCRELCONNECTSPATHELEMENTS', 'IFCRELVOIDSELEMENT', 'IFCRELFILLSELEMENT',
    'IFCPROPERTYSET', 'IFCPROPERTYSINGLEVALUE', 'IFCELEMENTQUANTITY', 'IFCQUANTITYLENGTH',
    'IFCQUANTITYAREA', 'IFCQUANTITYVOLUME', 'IFCQUANTITYWEIGHT', 'IFCMATERIAL',
    'IFCMATERIALLAYERSETUSAGE', 'IFCMATERIALLAYERSET', 'IFCMATERIALLAYER',
    'IFCMATERIALPROFILESETUSAGE', 'IFCMATERIALPROFILESET', 'IFCMATERIALPROFILE',
    'IFCPRESENTATIONLAYERASSIGNMENT', 'IFCSTYLEDITEM', 'IFCSURFACESTYLE',
    'IFCSURFACESTYLERENDERING', 'IFCCOLOURRGB', 'IFCBUILDINGSTOREY',
  ]);

  const dataStart = stepText.indexOf('DATA;');
  const dataBody = dataStart >= 0 ? stepText.slice(dataStart + 5) : stepText;
  const rawStatements = dataBody.split(';');

  interface StepEntity {
    stepId: string;
    globalId: string;
    ifcType: string;
    displayClass: string;
    label: string;
    name: string;
    objType: string;
    desc: string;
    storeyId: string | null;
    graphNodeId?: string;
  }

  const entities = new Map<string, StepEntity>();
  const storeys = new Map<string, { id: string; name: string; elevation: number; floorNum?: number }>();
  const relContained: { elements: string[]; structure: string }[] = [];
  const relConnects: [string, string][] = [];
  const relVoids: [string, string][] = [];
  const relAggregates: { host: string; targets: string[] }[] = [];
  let projectLabel = fileName.replace(/\.ifc$/i, '');

  for (let i = 0; i < rawStatements.length; i++) {
    const stmt = rawStatements[i].trim();
    if (!stmt || !stmt.startsWith('#')) continue;
    const eqIdx = stmt.indexOf('=');
    if (eqIdx < 0) continue;
    const stepId = stmt.slice(0, eqIdx).trim();
    const rhs = stmt.slice(eqIdx + 1).trim();
    const openParen = rhs.indexOf('(');
    const closeParen = rhs.lastIndexOf(')');
    if (openParen < 0 || closeParen < 0) continue;

    const typeUpper = rhs.slice(0, openParen).trim().toUpperCase();
    const args = splitStepArgs(rhs.slice(openParen + 1, closeParen));

    if (typeUpper === 'IFCPROJECT') {
      const pName = decodeIfcStepString(args[2]) || decodeIfcStepString(args[7]);
      if (pName) projectLabel = pName;
      continue;
    }

    if (typeUpper === 'IFCBUILDINGSTOREY') {
      const sName = decodeIfcStepString(args[2]) || `Storey ${storeys.size + 1}`;
      const elev = parseFloat(args[9]) || 0;
      storeys.set(stepId, { id: stepId, name: sName, elevation: elev });
      continue;
    }

    if (typeUpper === 'IFCRELCONTAINEDINSPATIALSTRUCTURE') {
      const relList = (args[4] || '')
        .replace(/^[()]|[()]$/g, '')
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      const structureRef = (args[5] || '').trim();
      relContained.push({ elements: relList, structure: structureRef });
      continue;
    }

    if (typeUpper === 'IFCRELCONNECTSPATHELEMENTS' || typeUpper === 'IFCRELCONNECTSELEMENTS') {
      const a = (args[4] || '').trim();
      const b = (args[5] || '').trim();
      if (a.startsWith('#') && b.startsWith('#')) relConnects.push([a, b]);
      continue;
    }

    if (typeUpper === 'IFCRELVOIDSELEMENT' || typeUpper === 'IFCRELFILLSELEMENT' || typeUpper === 'IFCRELAGGREGATES') {
      const host = (args[4] || '').trim();
      const targets = (args[5] || '')
        .replace(/^[()]|[()]$/g, '')
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.startsWith('#'));
      if (typeUpper === 'IFCRELAGGREGATES') relAggregates.push({ host, targets });
      else targets.forEach((t) => relVoids.push([host, t]));
      continue;
    }

    if (
      !nonElementTypes.has(typeUpper) &&
      typeUpper.startsWith('IFC') &&
      !typeUpper.endsWith('TYPE') &&
      !typeUpper.endsWith('STYLE')
    ) {
      const globalId = decodeIfcStepString(args[0]) || stepId;
      const name = decodeIfcStepString(args[2]);
      const desc = decodeIfcStepString(args[3]);
      const objType = decodeIfcStepString(args[4]);
      const tag = decodeIfcStepString(args[7]);
      entities.set(stepId, {
        stepId,
        globalId,
        ifcType: typeUpper,
        displayClass: formatIfcPascalName(typeUpper),
        label: tag || name || `${formatIfcPascalName(typeUpper)}-${stepId.slice(1)}`,
        name,
        objType,
        desc,
        storeyId: null,
      });
    }
  }

  const sortedStoreys = Array.from(storeys.values()).sort((a, b) => a.elevation - b.elevation);
  sortedStoreys.forEach((st, idx) => {
    st.floorNum = idx + 1;
  });

  relContained.forEach(({ elements, structure }) => {
    if (storeys.has(structure)) {
      elements.forEach((eid) => {
        if (entities.has(eid)) entities.get(eid)!.storeyId = structure;
      });
    }
  });

  const nodes: BimNode[] = [
    {
      id: 'proj-1',
      label: projectLabel,
      type: 'Project',
      level: 0,
      floor: 'ALL',
      floorNum: 0,
      r: 36,
      x: 0,
      y: 0,
      color: '#312e81',
      desc: `Imported IFC 4.3 / 2x3 STEP model (${entities.size} physical elements across ${sortedStoreys.length || 1} levels).`,
    },
  ];
  const links: BimLink[] = [];

  const byClass = new Map<string, StepEntity[]>();
  entities.forEach((ent) => {
    if (!byClass.has(ent.ifcType)) byClass.set(ent.ifcType, []);
    byClass.get(ent.ifcType)!.push(ent);
  });

  const classKeys = Array.from(byClass.keys()).sort();
  classKeys.forEach((ifcUpper) => {
    const pascal = formatIfcPascalName(ifcUpper);
    const catId = `cat-${ifcUpper.toLowerCase()}`;
    const catColor = IFC_ENTITY_PALETTE[ifcUpper] || hashStringToJewelColor(ifcUpper);
    const list = byClass.get(ifcUpper)!;

    nodes.push({
      id: catId,
      label: pascal,
      ifcType: ifcUpper,
      type: 'Category',
      level: 1,
      floor: 'ALL',
      floorNum: 0,
      r: 26,
      x: 0,
      y: 0,
      color: catColor,
      desc: `${pascal} (${ifcUpper}) — ${list.length} element${list.length === 1 ? '' : 's'} imported from ${fileName}.`,
    });
    links.push({ source: 'proj-1', target: catId, relation: 'hierarchy' });

    const cols = Math.max(1, Math.ceil(Math.sqrt(list.length)));
    list.forEach((ent, idx) => {
      const st = ent.storeyId ? storeys.get(ent.storeyId) : null;
      const floorLabel = st ? st.name : 'L01';
      const floorNum = st?.floorNum ?? 1;
      const yElev = st ? st.elevation * 3.28084 || floorNum * 12 : floorNum * 12;

      const gx = ((idx % cols) - (cols - 1) / 2) * 18;
      const gz = (Math.floor(idx / cols) - (cols - 1) / 2) * 18;

      let size3d: [number, number, number] = [2.2, 10.0, 2.2];
      let shape3d: 'box' | 'cylinder' | 'joint' = 'box';
      let yPos = yElev - 5.0;

      if (ifcUpper.includes('SLAB') || ifcUpper.includes('ROOF') || ifcUpper.includes('COVERING')) {
        size3d = [16.0, 0.8, 16.0];
        yPos = yElev;
      } else if (ifcUpper.includes('BEAM') || ifcUpper.includes('MEMBER')) {
        size3d = [16.0, 1.4, 1.0];
        yPos = yElev - 0.8;
      } else if (ifcUpper.includes('WALL') || ifcUpper.includes('CURTAIN')) {
        size3d = [16.0, 11.0, 1.2];
        yPos = yElev - 5.5;
      } else if (ifcUpper.includes('FOOTING')) {
        size3d = [8.0, 3.0, 8.0];
        yPos = -1.5;
      } else if (ifcUpper.includes('PILE')) {
        size3d = [1.8, 18.0, 1.8];
        shape3d = 'cylinder';
        yPos = -11.0;
      } else if (ifcUpper.includes('FASTENER') || ifcUpper.includes('PLATE') || ifcUpper.includes('ACCESSORY')) {
        size3d = [2.4, 0.8, 2.4];
        shape3d = 'joint';
        yPos = yElev;
      } else if (ifcUpper.includes('WINDOW') || ifcUpper.includes('DOOR')) {
        size3d = [4.0, 7.5, 0.6];
        yPos = yElev - 7.0;
      }

      const nodeId = `ifc-${ent.stepId.slice(1)}`;
      ent.graphNodeId = nodeId;
      nodes.push({
        id: nodeId,
        label: ent.label,
        type: pascal,
        ifcType: ifcUpper,
        level: 2,
        parent: catId,
        floor: floorLabel,
        floorNum,
        sectionSize: ent.objType || pascal,
        ratedStrength: 65,
        strengthLabel: ent.objType || `${pascal} (IFC)`,
        axialLoadKn: 1200 + (idx % 9) * 450,
        utilization: Number((0.42 + ((idx * 7) % 45) / 100).toFixed(2)),
        r: list.length > 120 ? 7.5 : 11,
        x: 0,
        y: 0,
        color: catColor,
        pos3d: [gx, yPos, gz],
        size3d,
        shape3d,
        desc: `${pascal} (${ent.label}) • GlobalId: ${ent.globalId}${ent.objType ? ` • ObjectType: ${ent.objType}` : ''}${ent.desc ? ` • ${ent.desc}` : ''}`,
      });
      links.push({ source: catId, target: nodeId, relation: 'hierarchy' });
    });
  });

  const addTopoLink = (stepA: string, stepB: string) => {
    const a = entities.get(stepA);
    const b = entities.get(stepB);
    if (a && b && a.graphNodeId && b.graphNodeId && a.graphNodeId !== b.graphNodeId) {
      links.push({ source: a.graphNodeId, target: b.graphNodeId, relation: 'connectivity' });
    }
  };
  relConnects.forEach(([a, b]) => addTopoLink(a, b));
  relVoids.forEach(([a, b]) => addTopoLink(a, b));
  relAggregates.forEach(({ host, targets }) => targets.forEach((t) => addTopoLink(host, t)));

  return {
    graph: normalizeGraphData({ projectName: projectLabel, nodes, links }, projectLabel),
    rawLinks: links,
  };
}

export function normalizeImportedJsonGraph(parsed: any, fileName: string): { graph: BimGraphData; rawLinks: BimLink[] } {
  const rawNodes = Array.isArray(parsed.nodes) ? parsed.nodes : [];
  const rawLinks: BimLink[] = Array.isArray(parsed.links) ? parsed.links : [];

  const hasCategories = rawNodes.some((n: any) => n.type === 'Category' || n.level === 1);
  if (hasCategories) {
    return {
      graph: normalizeGraphData(
        {
          projectName: parsed.projectName || parsed.project || fileName.replace(/\.json$/i, ''),
          nodes: rawNodes,
          links: rawLinks,
        },
        fileName.replace(/\.json$/i, '')
      ),
      rawLinks,
    };
  }

  const projectLabel = parsed.projectName || parsed.project || fileName.replace(/\.json$/i, '');
  const nodes: BimNode[] = [
    {
      id: 'proj-1',
      label: projectLabel,
      type: 'Project',
      level: 0,
      floor: 'ALL',
      floorNum: 0,
      r: 36,
      x: 0,
      y: 0,
      color: '#312e81',
      desc: `Imported BIM model (${rawNodes.length} elements).`,
    },
  ];
  const links: BimLink[] = [...rawLinks];
  const catMap = new Map<string, BimNode>();

  rawNodes.forEach((n: any, idx: number) => {
    if (n.type === 'Project' || n.level === 0) return;
    const rawType = n.ifcType || n.category || n.type || 'IfcBuildingElementProxy';
    const upper = String(rawType).toUpperCase().startsWith('IFC')
      ? String(rawType).toUpperCase()
      : `IFC${String(rawType).toUpperCase().replace(/[^A-Z0-9]/g, '')}`;
    const pascal = formatIfcPascalName(upper);
    const catId = `cat-${upper.toLowerCase()}`;

    if (!catMap.has(catId)) {
      const catColor = IFC_ENTITY_PALETTE[upper] || hashStringToJewelColor(upper);
      const catNode: BimNode = {
        id: catId,
        label: pascal,
        ifcType: upper,
        type: 'Category',
        level: 1,
        floor: 'ALL',
        floorNum: 0,
        r: 26,
        x: 0,
        y: 0,
        color: catColor,
        desc: `${pascal} element group imported from ${fileName}.`,
      };
      catMap.set(catId, catNode);
      nodes.push(catNode);
      links.push({ source: 'proj-1', target: catId, relation: 'hierarchy' });
    }

    const clone: BimNode = {
      ...n,
      id: n.id || `el-${idx}`,
      label: n.label || n.name || n.mark || `Element ${idx + 1}`,
      ifcType: upper,
      level: 2,
      parent: n.parent || catId,
      color: catMap.get(catId)!.color,
    };
    nodes.push(clone);
    links.push({ source: catId, target: clone.id, relation: 'hierarchy' });
  });

  return {
    graph: normalizeGraphData({ projectName: projectLabel, nodes, links }, projectLabel),
    rawLinks: links,
  };
}

// Pluggable parser registry for future IFC / Revit / Tekla / ETABS converters
export const BIM_PARSERS: BimParserPlugin[] = [
  {
    id: 'ifc-step-4.3',
    name: 'IFC 4.3 / 2x3 STEP Physical File Parser',
    extensions: ['.ifc'],
    canParse: (content, fileName) => fileName.toLowerCase().endsWith('.ifc') || content.startsWith('ISO-10303-21'),
    parse: (content, fileName) => parseRawIfcStepToGraph(content, fileName),
  },
  {
    id: 'bim-graph-json',
    name: 'Structural BIM Graph JSON Converter',
    extensions: ['.json'],
    canParse: (_content, fileName) => fileName.toLowerCase().endsWith('.json'),
    parse: (content, fileName) => normalizeImportedJsonGraph(JSON.parse(content), fileName),
  },
];
