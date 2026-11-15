/**
 * A minimal valid PDF written byte by byte (US Letter pages, Helvetica, no embedded fonts), one text
 * line per entry, top to bottom. Used by the vitest fixtures (test/fixtures.ts) and by the parity
 * script's --two-pdf mode, so neither needs a committed or generated binary.
 */
export interface PdfLine {
  text: string;
  size: number;
}

const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");

/** A minimal valid PDF (US Letter pages, Helvetica), one text line per entry, top to bottom. */
export function minimalPdf(pages: PdfLine[][]): Uint8Array {
  const objs: string[] = [];
  const pageIds = pages.map((_, i) => 4 + i * 2);
  objs[1] = "<< /Type /Catalog /Pages 2 0 R >>";
  objs[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(" ")}] /Count ${pages.length} >>`;
  objs[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>";
  pages.forEach((lines, i) => {
    let y = 740;
    const ops = lines.map((l) => {
      const s = `BT /F1 ${l.size} Tf 50 ${y} Td (${esc(l.text)}) Tj ET`;
      y -= l.size + 10;
      return s;
    }).join("\n");
    const pid = pageIds[i]!, cid = pid + 1;
    objs[pid] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${cid} 0 R >>`;
    objs[cid] = `<< /Length ${ops.length} >>\nstream\n${ops}\nendstream`;
  });
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  for (let id = 1; id < objs.length; id++) {
    offsets[id] = out.length;
    out += `${id} 0 obj\n${objs[id]}\nendobj\n`;
  }
  const xref = out.length;
  out += `xref\n0 ${objs.length}\n0000000000 65535 f \n`;
  for (let id = 1; id < objs.length; id++) out += `${String(offsets[id]).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objs.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return new TextEncoder().encode(out);
}
