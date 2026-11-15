/**
 * stdout carries JSON-RPC only. Route console output (ours and every library's, including web-ifc's
 * wasm logger and pdf.js warnings) to stderr. Must run BEFORE web-ifc / pdf.js are imported, which is
 * why the bin shim calls it before importing the CLI.
 *
 * web-ifc prints one "[WEB-IFC]..." line per entity it cannot fully parse (often hundreds, harmless);
 * pdf.js prints "Warning: ..." lines (missing standard-font data for text it never draws, odd Info
 * keys). Both are counted and suppressed unless verbose.
 */
let suppressed = 0;
let pdfjsWarnings = 0;
let installed = false;
let verbose = false;

export function routeConsoleToStderr(opts: { verbose?: boolean } = {}): void {
  verbose = verbose || !!opts.verbose;
  if (installed) return;
  installed = true;
  const err = console.error.bind(console);
  const out = (...a: unknown[]) => {
    if (!verbose && typeof a[0] === "string") {
      if (a[0].startsWith("[WEB-IFC]")) {
        suppressed += 1;
        return;
      }
      if (a[0].startsWith("Warning: ")) {
        pdfjsWarnings += 1;
        return;
      }
    }
    err(...a);
  };
  for (const k of ["log", "info", "warn", "debug", "error"] as const) console[k] = out;
}

export function setVerbose(v: boolean): void {
  verbose = v;
}

/** Number of web-ifc parser messages suppressed so far. */
export function suppressedWebIfcMessages(): number {
  return suppressed;
}

/** Number of pdf.js "Warning:" lines suppressed so far. */
export function suppressedPdfjsWarnings(): number {
  return pdfjsWarnings;
}
