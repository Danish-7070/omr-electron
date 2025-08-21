const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const pServerDir = path.join(__dirname, 'pServer');
const distDir = path.join(pServerDir, 'dist');

if (fs.existsSync(distDir)) {
  fs.rmSync(distDir, { recursive: true, force: true });
}
fs.mkdirSync(distDir, { recursive: true });

// Run PyInstaller to create a single executable.
// Adjust --add-data as needed for your folders/files.
// This assumes building on the target platform (e.g., Windows for .exe).
const pyinstallerCmd = `
  pyinstaller --onefile
  --distpath "${distDir}"
  --name main
  --add-data "${path.join(pServerDir, 'routers')};routers"
  --add-data "${path.join(pServerDir, 'models')};models"
  --add-data "${path.join(pServerDir, 'database.py')};."
  "${path.join(pServerDir, 'main.py')}"
`.replace(/\n/g, ' ');

try {
  execSync(pyinstallerCmd, { stdio: 'inherit', cwd: __dirname });
  console.log('Python backend bundled successfully into pServer/dist/main(.exe)');
} catch (error) {
  console.error('PyInstaller failed:', error);
  process.exit(1);
}