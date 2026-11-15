export type WorkspaceView = 'element-graph' | 'calculation-graph' | '3d' | 'docs';
export type GraphViewMode = 'element-graph' | 'calculation-graph';
export type TraceDirection = 'down' | 'up' | 'both';
export type DockSide = 'float' | 'left' | 'right';

export interface PdfRevision {
  rev: string;
  date: string;
  pages: number;
  pageRef?: string;
  summary: string;
  author?: string;
}

export interface BimDocument {
  id: string;
  title: string;
  type: string;
  code: string;
  rev: string;
  pages: number;
  pageRef?: string;
  date: string;
  summary: string;
  calcCategory?: string; // e.g., 'Beam Design', 'Column Sizing', 'Connection & Fastener Check', 'Slab & Punching Shear', 'Foundation & Geotech'
  revisions?: PdfRevision[];
}

export interface FlattenedDocument extends BimDocument {
  nodeId: string;
  nodeLabel: string;
  nodeColor: string;
  nodeDisplayType: string;
  mappedElementIds: string[];
}


export type DiffStatus = 'added' | 'removed' | 'modified' | 'unchanged';

export interface NodeDiffFieldChange {
  field: string;
  before: string;
  after: string;
}

export interface NodeDiffMeta {
  status: DiffStatus;
  changes: NodeDiffFieldChange[];
  beforeNode?: BimNode;
  afterNode?: BimNode;
}

export interface DatabaseDiffSummary {
  baseName: string;
  compareName: string;
  addedCount: number;
  removedCount: number;
  modifiedCount: number;
  unchangedCount: number;
}

export interface BimNode {
  diffStatus?: DiffStatus;
  diffChanges?: NodeDiffFieldChange[];
  diffBefore?: Partial<BimNode>;
  id: string;
  label: string;
  type: string;
  ifcType?: string;
  level: number;
  parent?: string;
  categoryParent?: string;
  gridCode?: string;
  colNumber?: string;
  floor?: string;
  floorNum?: number;
  ratedStrength?: number;
  strengthLabel?: string;
  axialLoadKn?: number;
  utilization?: number;
  sectionSize?: string;
  baySpacing?: string;
  beamRole?: string;
  r: number;
  x: number;
  y: number;
  color?: string;
  desc?: string;
  pos3d?: [number, number, number];
  size3d?: [number, number, number];
  shape3d?: 'box' | 'cylinder' | 'joint';
  documents?: BimDocument[];
}

export interface BimLink {
  source: string;
  target: string;
  relation?: 'hierarchy' | 'connectivity' | 'load-path' | 'calc-mapping';
  isLoadPath?: boolean;
}

export interface BimGraphData {
  projectName?: string;
  nodes: BimNode[];
  links: BimLink[];
}

export interface NodeGroup {
  id: string;
  name: string;
  nodeIds: string[];
}

export interface FilterState {
  search: string;
  type: string;
  level: string;
}
