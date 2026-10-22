import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
const script = new URL('./auth-mode.sh', import.meta.url).pathname;
for (const [name, env, expected] of [
  ['no credentials requires an API key', {}, 'api-key'],
  ['a configured signing secret enables authenticated sessions', { NEXTAUTH_SECRET: 'synthetic-fixture' }, 'oauth'],
  ['ambient administration requires explicit opt-in', { ONECLI_ALLOW_UNAUTHENTICATED_LOCAL: 'true' }, 'local'],
  ['a merely truthy local flag does not disable authentication', { ONECLI_ALLOW_UNAUTHENTICATED_LOCAL: '1' }, 'api-key'],
]) test(name, () => {
  const actual = execFileSync('sh', [script], { encoding: 'utf8', env: { NEXTAUTH_SECRET: '', ONECLI_ALLOW_UNAUTHENTICATED_LOCAL: 'false', ...env } }).trim();
  assert.equal(actual, expected);
});
