#!/usr/bin/env node
// Launcher for the MCP server CLI. The workspace packages ship TypeScript sources, run directly by
// Node's type stripping (Node >= 22.18, the version CI pins).
const [major, minor] = process.versions.node.split(".").map(Number);
if (major < 22 || (major === 22 && minor < 18)) {
  console.error(`unloaded-mcp-server needs Node >= 22.18 (this is ${process.versions.node}).`);
  process.exit(1);
}
await import("../src/cli.ts");
