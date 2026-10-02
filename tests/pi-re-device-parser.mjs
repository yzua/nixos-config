// Offline regression against the exact packaged agent-device parser; no runCli.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const packageRoot = process.argv[2];
if (!packageRoot) throw new Error('Supply the pinned agent-device Nix package root');
const base = path.join(path.resolve(packageRoot), 'lib/agent-device/dist/src/');
const original = fs.readFileSync(path.join(base, 'cli.js'), 'utf8');
assert(original.includes('export{G as runCli}'), 'Pinned parser exports changed; re-review before updating');
const source = original
  .replaceAll('"./', `"${pathToFileURL(base).href}`)
  .replace('export{G as runCli}', 'export{G as runCli,bt as parse}');
const { parse } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const registry = await import(pathToFileURL(path.join(base, 'registry.js')).href);
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'pi-re-parser-'));
try {
  const serial = 'emulator-5580';
  const state = path.join(temporary, 'private-device-state');
  const controlled = [
    '--platform', 'android', '--serial', serial, '--session', 'pi-re-parser-fixture',
    '--state-dir', state, '--config', path.join(root, 'home-manager/modules/ai/pi-re/agent-device.json'),
    '--session-lock', 'reject', '--android-device-allowlist', serial,
    '--daemon-transport', 'socket', '--daemon-server-mode', 'socket',
  ];
  const user = ['type', '--', 'hello'];
  const options = { cwd: temporary, env: { HOME: temporary } };
  const bad = parse([...user, ...controlled], options);
  assert.notEqual(bad.flags.serial, serial, 'Old-order failure must remain reproducible');
  const good = parse([...controlled, ...user], options);
  assert.equal(good.flags.serial, serial);
  assert.equal(good.flags.platform, 'android');
  assert.equal(good.flags.stateDir, state);
  assert.equal(good.flags.daemonTransport, 'socket');
  assert.equal(good.flags.sessionLock, 'reject');
  assert.equal(registry.n().type(good.positionals, good.flags).text, 'hello');
  console.log('Pinned agent-device parser: controlled routing survives positional separator');
} finally {
  fs.rmSync(temporary, { recursive: true });
}
