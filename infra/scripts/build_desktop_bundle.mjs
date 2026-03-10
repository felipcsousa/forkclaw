import { rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const workspaceRoot = path.resolve(scriptDir, '../..');
const desktopRoot = path.join(workspaceRoot, 'apps', 'desktop');
const sidecarStageRoot = path.join(
  workspaceRoot,
  'apps',
  'desktop',
  'src-tauri',
  '.sidecar',
);

function run(command, args, { cwd = workspaceRoot } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      stdio: 'inherit',
      shell: process.platform === 'win32',
    });

    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${command} ${args.join(' ')} exited with code ${code ?? 'unknown'}`));
    });
  });
}

async function cleanupSidecarStage() {
  await rm(sidecarStageRoot, { recursive: true, force: true });
}

async function main() {
  await cleanupSidecarStage();

  try {
    await run('npm', ['run', 'package:sidecar', '--workspace', '@nanobot/backend']);
    await run('npm', ['run', 'tauri', '--', 'build'], { cwd: desktopRoot });
  } finally {
    await cleanupSidecarStage();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
