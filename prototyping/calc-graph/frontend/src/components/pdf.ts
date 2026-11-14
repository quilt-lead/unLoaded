// pdf.js setup shared by every PdfPage: one worker, one cached document per URL.
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { PDFDocumentProxy } from "pdfjs-dist";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

const docs = new Map<string, Promise<PDFDocumentProxy>>();

export function loadPdf(url: string): Promise<PDFDocumentProxy> {
  let p = docs.get(url);
  if (!p) {
    p = pdfjs.getDocument({ url }).promise;
    p.catch(() => docs.delete(url)); // a failed load is retried next time
    docs.set(url, p);
  }
  return p;
}

export { pdfjs };
