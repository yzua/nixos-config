#!/usr/bin/env python3
"""Offline surface regressions: Herdr must win over inherited outer tmux."""

import json
import os
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SURFACES = (
    REPO
    / "home-manager/modules/ai/pi/extensions/interactive-subagents/pi-extension/subagents/tmux.ts"
)

SHIM = """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['MUX_CALLS'], 'a') as f:
    f.write(json.dumps([Path(sys.argv[0]).name, args]) + '\\n')
if Path(sys.argv[0]).name == 'tmux':
    raise SystemExit('BUG: targeted the outer tmux')
if args[:2] == ['pane', 'run'] and os.environ.get('SESSION_FILE'):
    session = Path(os.environ['SESSION_FILE'])
    n = len(session.read_text().splitlines()) if session.exists() else 0
    if n == 0:
        session.write_text(json.dumps({'type': 'session', 'id': 'fixture-child', 'version': 3}) + '\\n')
    with session.open('a') as f:
        f.write(json.dumps({'type': 'message', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': f'RUN_{n}'}]}}) + '\\n')
if args[:2] == ['pane', 'layout']:
    width = 70 if os.environ.get('NARROW_PANE') == '1' else 160
    print(json.dumps({'result': {'layout': {'panes': [{'pane_id': os.environ['HERDR_PANE_ID'], 'rect': {'width': width, 'height': 50}}]}}}))
elif args[:2] == ['pane', 'split']:
    print(json.dumps({'result': {'pane': {'pane_id': os.environ.get('NEW_PANE', 'w2:p7')}}}))
elif args[:2] == ['pane', 'read']:
    if os.environ.get('MISSING_PANE') == '1':
        raise SystemExit(1)
    print('__SUBAGENT_DONE_0__')
elif args[:2] == ['pane', 'list']:
    print(json.dumps({'result': {'panes': []}}))
"""


class HerdrSurfaces(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pi-herdr-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ["herdr", "tmux"]:
            shim = self.bin / name
            shim.write_text(SHIM)
            shim.chmod(0o755)
        endpoint = socket.socket(socket.AF_UNIX)
        self.addCleanup(endpoint.close)
        endpoint.bind(str(self.root / "herdr.sock"))
        self.env = dict(
            os.environ,
            PATH=f"{self.bin}:{os.environ['PATH']}",
            HERDR_ENV="1",
            HERDR_SOCKET_PATH=str(self.root / "herdr.sock"),
            HERDR_PANE_ID="w2:p3",
            TMUX="outer,123,0",
            TMUX_PANE="%9",
            MUX_CALLS=str(self.root / "calls"),
        )

    def run_probe(self, source):
        probe = self.root / "probe.ts"
        probe.write_text(f"import * as mux from {json.dumps(str(SURFACES))};\n" + source)
        result = subprocess.run(
            [shutil.which("bun"), str(probe)],
            env=self.env,
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_nested_herdr_uses_own_panes_and_atomic_input(self):
        result = self.run_probe("""
const available = mux.isMuxAvailable();
const pane = mux.createSurface("fixture");
mux.sendCommand(pane, "printf 'literal ; $ text'");
const screen = mux.readScreen(pane);
const asyncScreen = await mux.readScreenAsync(pane);
const done = await mux.pollForExit(pane, new AbortController().signal, {interval: 10});
mux.closeSurface(pane);
console.log(JSON.stringify({available, pane, screen, asyncScreen, done}));
""")
        self.assertTrue(result["available"])
        self.assertEqual(result["pane"], "w2:p7")
        self.assertEqual(result["done"]["reason"], "sentinel")
        self.assertIn("__SUBAGENT_DONE_0__", result["screen"])
        calls = [json.loads(line) for line in (self.root / "calls").read_text().splitlines()]
        self.assertTrue(all(name == "herdr" for name, _ in calls), calls)
        split = next(args for _, args in calls if args[:2] == ["pane", "split"])
        self.assertIn("w2:p3", split)
        self.assertIn("--no-focus", split)
        self.assertEqual(split[split.index("--cwd") + 1], str(self.root))
        self.assertIn(["herdr", ["pane", "run", "w2:p7", "printf 'literal ; $ text'"]], calls)

    def test_managed_herdr_run_completes_and_resume_reports_only_new_output(self):
        self.env["SESSION_FILE"] = str(self.root / "child.jsonl")
        managed = SURFACES.with_name("managed-run.ts")
        result = self.run_probe(
            f"import {{ManagedRuns}} from {json.dumps(str(managed))};\n"
            + """
import {readFileSync, existsSync} from 'node:fs';
const delivered = [];
const manager = new ManagedRuns({moduleSignal: () => new AbortController().signal,
 shellReadyDelayMs: () => 0, refresh() {}, tick() {}, present: result => result.summary,
 sendMessage: (message, options) => delivered.push({message, options})});
const candidate = {id:'fixture', name:'fixture', task:'offline', startTime:Date.now(),
 sessionFile:process.env.SESSION_FILE, statusState:{}, interactive:false};
const prepare = () => ({kind:'command', command:'offline fixture',
 launchScriptFile:process.env.SESSION_FILE + '.sh', scriptPreamble:''});
await manager.launch(candidate, {kind:'initial'}, prepare);
const owner = JSON.parse(readFileSync(process.env.SESSION_FILE + '.owner.json','utf8'));
const wait = async n => {
 const deadline = Date.now()+3000;
 while(delivered.length<n && Date.now()<deadline) await Bun.sleep(10);
 if(delivered.length!==n) throw new Error('Missing delivery');
};
await wait(1);
await manager.launch(candidate, {kind:'resume',sessionId:'fixture-child'}, prepare);
await wait(2);
console.log(JSON.stringify({delivered, owner,
 ownerRetained:existsSync(process.env.SESSION_FILE + '.owner.json')}));
"""
        )
        self.assertEqual([r["message"]["content"] for r in result["delivered"]], ["RUN_0", "RUN_2"])
        self.assertTrue(result["owner"]["mux"].startswith("herdr:"))
        self.assertEqual(result["owner"]["surface"], "w2:p7")
        self.assertFalse(result["ownerRetained"])
        for record in result["delivered"]:
            self.assertEqual(record["message"]["details"]["exitCode"], 0)
            self.assertEqual(record["options"], {"triggerTurn": True, "deliverAs": "steer"})

    def test_encoded_herdr_ids_are_accepted(self):
        self.env.update(HERDR_PANE_ID="w1V:pA", NEW_PANE="w1V:pB")
        pane = self.run_probe('console.log(JSON.stringify(mux.createSurface("fixture")));')
        self.assertEqual(pane, "w1V:pB")

    def test_replaced_server_socket_refuses_stale_owner_before_pane_operations(self):
        managed = SURFACES.with_name("managed-run.ts")
        result = self.run_probe(
            f"import {{ManagedRuns}} from {json.dumps(str(managed))};\n"
            + """
import {writeFileSync,unlinkSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
const session = process.cwd()+'/stale.jsonl';
writeFileSync(session, JSON.stringify({type:'session',id:'child',version:3})+'\\n');
const old = mux.muxIdentity();
writeFileSync(session+'.owner.json',JSON.stringify({version:1,token:'old',
 sessionFile:session,surface:'w2:p7',mux:old}));
unlinkSync(process.env.HERDR_SOCKET_PATH);
execFileSync('python3',['-c','import socket,sys; s=socket.socket(socket.AF_UNIX); s.bind(sys.argv[1])',process.env.HERDR_SOCKET_PATH]);
const manager = new ManagedRuns({moduleSignal:()=>new AbortController().signal,
 shellReadyDelayMs:()=>0,refresh(){},tick(){},present:()=>'',sendMessage(){}});
let error;
try {
 await manager.launch({id:'new',name:'new',task:'offline',startTime:Date.now(),
 sessionFile:session,statusState:{},interactive:false}, {kind:'resume',sessionId:'child'},
 ()=>({kind:'command',command:'fixture',launchScriptFile:session+'.sh',scriptPreamble:''}));
} catch(e) {error=String(e);}
console.log(JSON.stringify({old,current:mux.muxIdentity(),error}));
"""
        )
        self.assertNotEqual(result["old"], result["current"])
        self.assertIn("another or unknown", result["error"])
        self.assertFalse(
            (self.root / "calls").exists(), "stale ownership touched replacement panes"
        )

    def test_narrow_herdr_panes_split_down(self):
        self.env["NARROW_PANE"] = "1"
        self.run_probe('console.log(JSON.stringify(mux.createSurface("fixture")));')
        calls = [json.loads(line) for line in (self.root / "calls").read_text().splitlines()]
        split = next(args for _, args in calls if args[:2] == ["pane", "split"])
        self.assertEqual(split[split.index("--direction") + 1], "down")

    def test_missing_herdr_pane_reports_loss_without_outer_tmux_probe(self):
        self.env["MISSING_PANE"] = "1"
        result = self.run_probe("""
console.log(JSON.stringify(await mux.pollForExit("w2:p7", new AbortController().signal, {interval: 10})));
""")
        self.assertEqual(result["reason"], "error")
        self.assertIn("disappeared", result["errorMessage"])
        calls = (self.root / "calls").read_text()
        self.assertNotIn('"tmux"', calls)

    def test_incomplete_herdr_context_never_falls_back_to_outer_tmux(self):
        self.env.pop("HERDR_SOCKET_PATH")
        result = self.run_probe("console.log(JSON.stringify({available: mux.isMuxAvailable()}));")
        self.assertFalse(result["available"])


if __name__ == "__main__":
    unittest.main()
