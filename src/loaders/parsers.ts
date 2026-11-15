/**
 * Pluggable model importers: file bytes -> ElementGraph (or a calc-graph export).
 *
 * Pipelines
 * - .ifc (STEP)                        -> @unloaded/ifc-parser -> ModelInput -> buildGraph -> ElementGraph
 * - .json, dispatched on content:
 *     model bundle                     -> calc-mapper parseBundle -> its element graph (deserialize) + its calc graph
 *                                         (stored with the model revision; projectService shows it when there is no calc PDF)
 *     serialized element graph         -> ElementGraph.deserialize
 *     ModelInput                       -> buildGraph -> ElementGraph
 *     legacy BIM graph ({ nodes, links }) -> refused, naming scripts/convert-legacy-demo.ts (convert it to a bundle)
 *     calc-graph export                -> returned as-is for src/data/loadProject.ts (read-only view)
 *     calc-graph project file          -> validated (@unloaded/project-file parseProjectFile) for projectStore importProject
 *
 * A model's ElementGraph is stored with its revision in the local project store and goes through
 * src/loaders/elementGraphToBim.ts (the only ElementGraph -> view adapter). The store refuses a
 * serialized graph that calc-mapper's parseGraph (what reopens a saved project) rejects, so an
 * imported model can always be saved and reopened (projectStore checkStorableRevision).
 * - drawing set PDF (an explicit choice: a calc package is a PDF too, so PDFs are never sniffed into this)
 *                                      -> @unloaded/drawing-parser in the engine worker -> ModelInput -> importDrawingModel
 *                                         (projectService addDrawingRevision); elements keep Drawing.* params,
 *                                         incl. Drawing.Occurrences (where each is printed: src/data/drawingOccurrences.ts)
 * New formats (Revit, Tekla, ETABS, ...) should emit a ModelInput and reuse the element-graph
 * pipeline, so connectivity inference and load paths come for free.
 */
import { buildGraph, ElementGraph, ELEMENT_GRAPH_FORMAT, type ModelInput, type SerializedElementGraph } from '@unloaded/element-graph';
import type { IfcParsePhase } from '@unloaded/ifc-parser';
import type { Export } from '@unloaded/calc-mapper/types';
import { isBundle, parseBundle, type BundleCalcGraph, type BundleMeta } from '@unloaded/calc-mapper';
import { isCalcGraphExport, normaliseExport } from '../data/loadProject';
import { isProjectFileFormat, parseProjectFile, type ProjectFile } from '@unloaded/project-file';

export type ImportResult =
  | {
      kind: 'model';
      /** Domain graph: the single source of elements and topology. */
      elementGraph: ElementGraph;
      projectName: string;
      /** 'ifc' when the bytes were an IFC (it can then be uploaded as a model revision); 'drawing' for a drawing set PDF. */
      format: 'ifc' | 'element-graph' | 'model-input' | 'bundle' | 'drawing';
      /** A model bundle's calc graph (null: the bundle has none; absent: not a bundle). */
      calcGraph?: BundleCalcGraph | null;
      /** A model bundle's meta (its revision label, whether it is demo data). */
      bundleMeta?: BundleMeta;
      /** Parser + graph-build warnings, prefixed with their origin. */
      warnings: string[];
    }
  | { kind: 'export'; export: Export; warnings: string[] }
  | { kind: 'project-file'; project: ProjectFile; warnings: string[] };

export interface BimParserPlugin {
  id: string;
  name: string;
  extensions: string[];
  /** Cheap sniff on the file name and first bytes. */
  canParse: (fileName: string, head: Uint8Array) => boolean;
  parse: (bytes: Uint8Array, fileName: string, onProgress: (message: string) => void) => Promise<ImportResult>;
}

/** Directory containing web-ifc.wasm (copied into public/wasm by scripts/copy-assets.mjs). */
export const WASM_PATH = `${import.meta.env.BASE_URL}wasm/`;

const PHASE_LABEL: Record<IfcParsePhase, string> = {
  init: 'Starting IFC engine',
  open: 'Opening model',
  index: 'Indexing entities',
  elements: 'Reading elements',
  geometry: 'Computing geometry',
  relations: 'Reading relations',
  done: 'Parsed',
};

/** Let the browser paint progress before synchronous heavy work. */
const nextFrame = () => new Promise<void>((r) => setTimeout(r, 16));

function stripExt(fileName: string): string {
  return fileName.replace(/\.[^.]+$/, '');
}

function looksLikeJson(head: Uint8Array): boolean {
  for (const b of head) {
    if (b === 0x20 || b === 0x0a || b === 0x0d || b === 0x09 || b === 0xef || b === 0xbb || b === 0xbf) continue;
    return b === 0x7b; // "{"
  }
  return false;
}

function hasStepHeader(head: Uint8Array): boolean {
  let s = '';
  for (let i = 0; i < Math.min(head.length, 64); i++) s += String.fromCharCode(head[i]!);
  return s.replace(/^﻿|^ï»¿/, '').trimStart().startsWith('ISO-10303-21');
}

function isSerializedGraph(d: unknown): d is SerializedElementGraph {
  return typeof d === 'object' && d !== null && (d as { format?: unknown }).format === ELEMENT_GRAPH_FORMAT;
}

function isModelInput(d: unknown): d is ModelInput {
  if (typeof d !== 'object' || d === null) return false;
  const m = d as Partial<ModelInput>;
  return Array.isArray(m.elements) && typeof m.meta === 'object' && m.meta !== null;
}

/** The retired legacy demo format ({ nodes: [...] }, no format / meta / elements): named in the error, so its owner knows to convert it. */
function isLegacyNodesJson(d: unknown): boolean {
  if (typeof d !== 'object' || d === null) return false;
  const o = d as { nodes?: unknown; format?: unknown; meta?: unknown; elements?: unknown };
  return Array.isArray(o.nodes) && o.format === undefined && o.meta === undefined && o.elements === undefined;
}

function decodeJson(bytes: Uint8Array, fileName: string): unknown {
  try {
    return JSON.parse(new TextDecoder().decode(bytes).replace(/^﻿/, ''));
  } catch (e) {
    throw new Error(`${fileName}: invalid JSON (${(e as Error).message})`);
  }
}

async function fromModelInput(
  input: ModelInput,
  fileName: string,
  format: 'ifc' | 'model-input' | 'drawing',
  onProgress: (m: string) => void
): Promise<Extract<ImportResult, { kind: 'model' }>> {
  onProgress(`Inferring connectivity (${input.elements.length} elements)`);
  await nextFrame();
  const { graph: elementGraph, warnings } = buildGraph(input);
  return {
    kind: 'model',
    elementGraph,
    projectName: input.meta.project || stripExt(fileName),
    format,
    warnings: [...(input.warnings ?? []).map((w) => `parser: ${w}`), ...warnings.map((w) => `graph: ${w}`)],
  };
}

/**
 * A drawing set's ModelInput (from @unloaded/drawing-parser, parsed in the engine worker) -> the element graph,
 * like any ModelInput. Kept apart from BIM_PARSERS on purpose: which PDFs are drawings is the user's choice.
 */
export function importDrawingModel(
  input: ModelInput,
  fileName: string,
  onProgress: (m: string) => void = () => {},
): Promise<Extract<ImportResult, { kind: 'model' }>> {
  return fromModelInput(input, fileName, 'drawing', onProgress);
}

export const BIM_PARSERS: BimParserPlugin[] = [
  {
    id: 'ifc',
    name: 'IFC (web-ifc) → Element Graph',
    extensions: ['.ifc'],
    canParse: (fileName, head) => /\.ifc$/i.test(fileName) || hasStepHeader(head),
    parse: async (bytes, fileName, onProgress) => {
      // web-ifc (~3 MB JS + 1.2 MB wasm) is only fetched when an IFC is opened.
      const { parseIfc } = await import('@unloaded/ifc-parser');
      let lastPhase: IfcParsePhase | null = null;
      const input = await parseIfc(bytes, {
        fileName,
        wasmPath: WASM_PATH,
        onProgress(phase) {
          if (phase !== lastPhase) {
            lastPhase = phase;
            onProgress(PHASE_LABEL[phase]);
          }
        },
      });
      return fromModelInput(input, fileName, 'ifc', onProgress);
    },
  },
  {
    id: 'json',
    name: 'JSON (model bundle / Element Graph / ModelInput / calc-graph export / project file)',
    extensions: ['.json'],
    canParse: (fileName, head) => /\.json$/i.test(fileName) || looksLikeJson(head),
    parse: async (bytes, fileName, onProgress) => {
      const data = decodeJson(bytes, fileName);
      // a file that says it is a bundle is validated in full; its error names the field at fault
      if (isBundle(data)) {
        onProgress('Loading model bundle');
        await nextFrame();
        const b = parseBundle(data);
        return {
          kind: 'model',
          elementGraph: ElementGraph.deserialize(b.elementGraph),
          projectName: b.meta.project || b.elementGraph.meta?.project || stripExt(fileName),
          format: 'bundle',
          calcGraph: b.calcGraph,
          bundleMeta: b.meta,
          warnings: b.meta.demo ? ['model bundle: demo data (invented calcs, no PDF)'] : [],
        };
      }
      if (isSerializedGraph(data)) {
        onProgress('Loading element graph');
        await nextFrame();
        return {
          kind: 'model',
          elementGraph: ElementGraph.deserialize(data),
          projectName: data.meta?.project || stripExt(fileName),
          format: 'element-graph',
          warnings: [],
        };
      }
      if (isModelInput(data)) return fromModelInput(data, fileName, 'model-input', onProgress);
      // a file that says it is a project file is validated in full; its error names the field at fault
      if (isProjectFileFormat(data)) return { kind: 'project-file', project: parseProjectFile(data), warnings: [] };
      if (isCalcGraphExport(data)) return { kind: 'export', export: normaliseExport(data), warnings: [] };
      if (isLegacyNodesJson(data)) {
        throw new Error(
          `${fileName}: this is a legacy { nodes, links } BIM graph, which the app no longer opens. Convert it to a model bundle with: node scripts/convert-legacy-demo.ts ${fileName} out.bundle.json`,
        );
      }
      throw new Error(`${fileName}: JSON is not a model bundle, an element graph, a ModelInput, a calc-graph export or a project file`);
    },
  },
];

export const ACCEPTED_EXTENSIONS = Array.from(new Set(BIM_PARSERS.flatMap((p) => p.extensions)));

/** Pick the first parser that accepts the file and run it. */
export async function importModel(
  fileName: string,
  bytes: Uint8Array,
  onProgress: (message: string) => void = () => {}
): Promise<ImportResult & { parser: BimParserPlugin }> {
  const head = bytes.subarray(0, 1024);
  const parser = BIM_PARSERS.find((p) => p.canParse(fileName, head));
  if (!parser) {
    throw new Error(`${fileName}: unsupported file. Expected ${ACCEPTED_EXTENSIONS.join(' or ')}.`);
  }
  onProgress(`Reading ${fileName}`);
  await nextFrame();
  return { ...(await parser.parse(bytes, fileName, onProgress)), parser };
}
