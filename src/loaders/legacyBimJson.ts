/**
 * Legacy / hand-authored BIM graph JSON ({ projectName, nodes, links }) -> BimGraphData.
 * This is the format of data/bim-database.json. IFC and ModelInput imports go
 * through @unloaded/ifc-parser + @unloaded/element-graph instead (see parsers.ts).
 */
import { BimGraphData, BimLink, BimNode } from '../types/bim';
import { hashStringToJewelColor, IFC_ENTITY_PALETTE } from '../utils/colors';
import { normalizeGraphData } from '../utils/graphEngine';

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
      color: '#14AE5C',
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
