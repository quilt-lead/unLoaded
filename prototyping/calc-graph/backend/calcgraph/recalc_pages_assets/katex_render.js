// stdin: JSON array of LaTeX strings (display math). stdout: JSON array of KaTeX HTML strings.
// Used by recalc_pages.py; WeasyPrint does not run JavaScript, so math is rendered here first.
const katex = require("katex");
let buf = "";
process.stdin.on("data", (c) => (buf += c));
process.stdin.on("end", () => {
  const out = JSON.parse(buf).map((tex) => {
    try {
      return katex.renderToString(tex, { displayMode: true, output: "html", throwOnError: true, strict: "ignore", trust: false });
    } catch (e) {
      return "__KATEX_ERROR__" + String(e.message || e);
    }
  });
  process.stdout.write(JSON.stringify(out));
});
