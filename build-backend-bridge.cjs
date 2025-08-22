const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const pServerDir = path.join(__dirname, 'pServer');
const distDir = path.join(pServerDir, 'dist');

// Clean dist directory
if (fs.existsSync(distDir)) {
  fs.rmSync(distDir, { recursive: true, force: true });
}
fs.mkdirSync(distDir, { recursive: true });

// Create the bridge executable using PyInstaller
const pyinstallerCmd = `
  pyinstaller --onefile
  --distpath "${distDir}"
  --name bridge
  --add-data "${path.join(pServerDir, 'routers')};routers"
  --add-data "${path.join(pServerDir, 'models')};models"
  --add-data "${path.join(pServerDir, 'database.py')};."
  --hidden-import=asyncio
  --hidden-import=sqlite3
  --hidden-import=json
  --hidden-import=base64
  --hidden-import=pandas
  --hidden-import=openpyxl
  --hidden-import=cv2
  --hidden-import=numpy
  --hidden-import=PIL
  "${path.join(pServerDir, 'bridge.py')}"
`.replace(/\n/g, ' ');

try {
  console.log('Building Python bridge executable...');
  execSync(pyinstallerCmd, { stdio: 'inherit', cwd: __dirname });
  console.log('Python bridge executable built successfully in pServer/dist/bridge(.exe)');
} catch (error) {
  console.error('PyInstaller failed:', error);
  process.exit(1);
}