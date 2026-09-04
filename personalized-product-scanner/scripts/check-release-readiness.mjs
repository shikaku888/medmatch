import {existsSync, readFileSync} from 'node:fs';
import {resolve} from 'node:path';

const root = resolve(import.meta.dirname, '..');
const config = JSON.parse(readFileSync(resolve(root, 'capacitor.config.json'), 'utf8'));
const failures = [];
const scannerUrl = process.env.SCANNER_URL?.trim() || config.server?.url;

if (!config.appId || !/^[a-z][a-z0-9]*(\.[a-z0-9-]+)+$/.test(config.appId)) {
  failures.push('capacitor.appId must be a valid reverse-domain identifier');
}
if (!config.appName?.trim()) failures.push('capacitor.appName is required');
try {
  const parsedUrl = new URL(scannerUrl);
  const hasPlaceholderHost = parsedUrl.hostname.toUpperCase().includes('REPLACE-WITH-YOUR-DOMAIN');
  if (
    hasPlaceholderHost ||
    parsedUrl.protocol !== 'https:' ||
    !parsedUrl.hostname ||
    !parsedUrl.pathname.endsWith('/scanner/')
  ) {
    failures.push('scanner URL must be a real HTTPS URL ending in /scanner/');
  }
} catch {
  failures.push('scanner URL must be a real HTTPS URL ending in /scanner/');
}
if (config.server?.cleartext !== false) failures.push('capacitor.server.cleartext must remain false');
if (!existsSync(resolve(root, config.webDir || 'dist'))) {
  failures.push(`configured webDir does not exist: ${config.webDir}`);
}
if (!existsSync(resolve(root, 'README.md'))) failures.push('README.md is required for release review metadata');

if (failures.length) {
  console.error('Release readiness failed:');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(`Release readiness passed for ${config.appName} (${config.appId})`);
