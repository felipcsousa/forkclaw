import { readdir, rm, stat } from 'node:fs/promises';
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
const tauriRoot = path.join(desktopRoot, 'src-tauri');
const cargoTargetRoot = path.join(tauriRoot, 'target');
const maxTargetSizeGb = Number.parseFloat(process.env.NANOBOT_TAURI_TARGET_MAX_GB ?? '2.5');
const maxTargetSizeBytes =
  Number.isFinite(maxTargetSizeGb) && maxTargetSizeGb > 0
    ? Math.floor(maxTargetSizeGb * 1024 * 1024 * 1024)
    : Math.floor(2.5 * 1024 * 1024 * 1024);

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

async function getDirectorySize(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  let totalBytes = 0;

  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      totalBytes += await getDirectorySize(entryPath);
      continue;
    }
    if (entry.isFile()) {
      totalBytes += (await stat(entryPath)).size;
    }
  }

  return totalBytes;
}

function formatGb(bytes) {
  return (bytes / (1024 * 1024 * 1024)).toFixed(2);
}

async function cleanupCargoTargetIfNeeded() {
  const targetSize = await getDirectorySize(cargoTargetRoot).catch(() => 0);
  if (targetSize <= maxTargetSizeBytes) {
    return;
  }

  console.log(
    `[bundle] Cargo target is ${formatGb(targetSize)}GB (limit ${formatGb(
      maxTargetSizeBytes,
    )}GB). Running cargo clean to prevent unbounded growth.`,
  );
  await run('cargo', ['clean'], { cwd: tauriRoot });
}

async function main() {
  await cleanupSidecarStage();
  await cleanupCargoTargetIfNeeded();

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
