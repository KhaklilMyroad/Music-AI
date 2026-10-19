// Minimal test runner: no dependencies, runs under plain `node`.
// Usage: node web/tests/run-all.js
let pass = 0, fail = 0, skip = 0;
const failures = [];
let group = '';

export function describe(name, fn) { group = name; console.log(`\n\x1b[1m${name}\x1b[0m`); fn(); }
export function it(name, fn) {
  try { fn(); pass++; console.log(`  \x1b[32m✓\x1b[0m ${name}`); }
  catch (e) { fail++; failures.push({ group, name, error: e }); console.log(`  \x1b[31m✗ ${name}\x1b[0m\n    ${e.message.split('\n').join('\n    ')}`); }
}
export function xit(name) { skip++; console.log(`  \x1b[33m- ${name} (skipped)\x1b[0m`); }

export function eq(actual, expected, msg) {
  const a = JSON.stringify(actual), b = JSON.stringify(expected);
  if (a !== b) throw new Error(`${msg || 'not equal'}\n  expected: ${b}\n  actual:   ${a}`);
}
export function ok(cond, msg) { if (!cond) throw new Error(msg || 'expected truthy'); }
export function notOk(cond, msg) { if (cond) throw new Error(msg || 'expected falsy'); }
export function close(a, b, tol, msg) { if (Math.abs(a - b) > (tol ?? 1e-6)) throw new Error(`${msg || 'not close'}: ${a} vs ${b} (tol ${tol})`); }
export function throws(fn, match, msg) {
  try { fn(); } catch (e) {
    if (match && !String(e.message).includes(match) && e.code !== match) throw new Error(`${msg || 'wrong error'}: expected "${match}", got "${e.message}"`);
    return e;
  }
  throw new Error(msg || `expected a throw${match ? ` matching "${match}"` : ''}`);
}
export function summary() {
  console.log(`\n${'─'.repeat(60)}`);
  console.log(`\x1b[1m${pass} passed\x1b[0m${fail ? `, \x1b[31m${fail} failed\x1b[0m` : ''}${skip ? `, ${skip} skipped` : ''}`);
  if (fail) { console.log('\nFailures:'); for (const f of failures) console.log(`  ${f.group} › ${f.name}\n    ${f.error.message.split('\n')[0]}`); }
  return fail === 0;
}
