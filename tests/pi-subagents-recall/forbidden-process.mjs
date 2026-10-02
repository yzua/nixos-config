// Any accidental execution from production code fails, rather than opening a pane.
const forbidden = () => { throw new Error("Offline harness forbids process execution"); };
export const execFile = forbidden;
export const execFileSync = forbidden;
export const exec = forbidden;
export const execSync = forbidden;
export const spawn = forbidden;
export const spawnSync = forbidden;
export const fork = forbidden;
