// Open a file in the browser without uploading it: an IFC, a serialized element graph or a ModelInput
// (topology only, source 'local'), or a calc-graph export JSON (topology from the export + its calc
// data, source 'file'). Read-only either way; the views are fed through the same two adapters and
// the same merge as a backend project.
import { importModel } from '../loaders/parsers';
import { elementGraphToBim } from '../loaders/elementGraphToBim';
import type { ProjectViewModel } from '../types/bim';
import { exportToElementGraph, toCalcData } from './loadProject';
import { mergeProject } from './mergeProject';
import { urls } from '../api/client';

export interface OpenedFile {
  view: ProjectViewModel;
  warnings: string[];
  /** release the object URL made for an IFC's 3D view */
  dispose: () => void;
}

export async function openFileLocally(file: File, backendOnline: boolean, onProgress: (m: string) => void): Promise<OpenedFile> {
  const res = await importModel(file.name, new Uint8Array(await file.arrayBuffer()), onProgress);
  if (res.kind === 'export') {
    const exp = res.export;
    const view = mergeProject(elementGraphToBim(exportToElementGraph(exp)), toCalcData(exp), {
      source: 'file',
      projectId: null,
      // the export names a backend revision; its IFC is only reachable while the backend is up
      modelFileUrl: backendOnline && exp.model_revision != null ? urls.revisionFile(exp.model_revision) : null,
    });
    return { view, warnings: res.warnings, dispose: () => {} };
  }
  const objectUrl = res.format === 'ifc' ? URL.createObjectURL(file) : null;
  const view = mergeProject(elementGraphToBim(res.elementGraph, { projectName: res.projectName }), null, {
    source: 'local',
    projectId: null,
    modelFileUrl: objectUrl,
  });
  return { view, warnings: res.warnings, dispose: () => objectUrl && URL.revokeObjectURL(objectUrl) };
}
