import { summary } from './runner.js';
import contracts from './suite-contracts.js';
import strategy from './suite-strategy.js';
import transition from './suite-transition.js';
import persistence from './suite-persistence.js';
import firstperson from './suite-firstperson.js';
import audio from './suite-audio.js';
import input from './suite-input.js';

console.log('\x1b[1mTHE WAR BENEATH THE MAP — simulation acceptance tests\x1b[0m');
console.log('Each case traces to a requirement in docs/09-ACCEPTANCE-MATRIX.md\n');

contracts(); strategy(); transition(); persistence(); firstperson(); audio(); input();

process.exit(summary() ? 0 : 1);
