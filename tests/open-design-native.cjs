// Exercise SQLite statement cleanup after another native addon loads.
// Run through stdin: the same test as a file entrypoint misses this regression.
const { createRequire } = require('node:module');
const load = createRequire(process.argv[2] + '/package.json');
const database = new (load('better-sqlite3'))(':memory:');
if (database.prepare('SELECT 42 AS value').get().value !== 42) {
  throw new Error('SQLite query returned an unexpected value');
}
database.close();
load('node-pty');
console.log('PASS: SQLite query and mixed-addon cleanup');
