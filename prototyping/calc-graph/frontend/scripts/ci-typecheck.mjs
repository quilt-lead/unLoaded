// Type gate for `npm run build`. Runs `tsc --noEmit` only in CI (CI=true): type-checking is not
// run on developer laptops (local policy). The help ratchet's "info prop is required" rule is a
// TypeScript rule, so CI is where omissions fail; scripts/check-help.mjs catches the rest everywhere.
import { spawnSync } from 'node:child_process';
if (!process.env.CI) {
  console.log('ci-typecheck: skipped (not CI) - CI runs tsc --noEmit as part of npm run build');
  process.exit(0);
}
const r = spawnSync('npx', ['--no-install', 'tsc', '--noEmit', '-p', 'tsconfig.json'], { stdio: 'inherit' });
process.exit(r.status ?? 1);
