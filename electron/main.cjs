const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const net = require('net');

const isDev = process.env.NODE_ENV === 'development';
const isPackaged = app.isPackaged;

let mainWindow;
let pythonProcess = null;

// Paths for packaged application
const getResourcePath = (relativePath) => {
  if (isPackaged) {
    return path.join(process.resourcesPath, 'app', relativePath);
  }
  return path.join(__dirname, '..', relativePath);
};

const getPythonExecutablePath = () => {
  if (isPackaged) {
    const platform = process.platform;
    if (platform === 'win32') {
      return path.join(process.resourcesPath, 'python-backend', 'main.exe');
    } else if (platform === 'darwin') {
      return path.join(process.resourcesPath, 'python-backend', 'main');
    } else {
      return path.join(process.resourcesPath, 'python-backend', 'main');
    }
  }
  return 'python'; // Development mode
};

// Check if port is available
const isPortAvailable = (port) => {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(port, () => {
      server.once('close', () => resolve(true));
      server.close();
    });
    server.on('error', () => resolve(false));
  });
};

// Wait for service to be ready
const waitForService = (port, timeout = 30000) => {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    
    const checkConnection = () => {
      const socket = new net.Socket();
      
      socket.setTimeout(1000);
      socket.on('connect', () => {
        socket.destroy();
        resolve(true);
      });
      
      socket.on('timeout', () => {
        socket.destroy();
        checkAgain();
      });
      
      socket.on('error', () => {
        checkAgain();
      });
      
      socket.connect(port, 'localhost');
    };
    
    const checkAgain = () => {
      if (Date.now() - startTime > timeout) {
        reject(new Error(`Service on port ${port} did not start within ${timeout}ms`));
      } else {
        setTimeout(checkConnection, 1000);
      }
    };
    
    checkConnection();
  });
};

// Start Python backend
const startPythonBackend = async () => {
  console.log('Starting Python backend...');
  
  try {
    // Check if backend is already running
    const backendAvailable = await isPortAvailable(3001);
    if (!backendAvailable) {
      console.log('Backend is already running on port 3001');
      return true;
    }

    const pythonPath = getPythonExecutablePath();
    let pythonArgs = [];

    if (!isPackaged) {
      // Development mode
      pythonArgs = [path.join(__dirname, '..', 'pServer', 'main.py')];
    }

    // Set environment variables (SQLite path in user data for persistence)
    const dbPath = path.join(app.getPath('userData'), 'omr_database.db');
    const env = {
      ...process.env,
      DATABASE_PATH: dbPath,
      PORT: '3001',
      NODE_ENV: 'production'
    };

    pythonProcess = spawn(pythonPath, pythonArgs, {
      stdio: isDev ? 'inherit' : 'ignore',
      env: env,
      detached: false,
      cwd: isPackaged ? path.dirname(pythonPath) : path.join(__dirname, '..', 'pServer')
    });

    pythonProcess.on('error', (error) => {
      console.error('Python process error:', error);
      if (error.code === 'ENOENT') {
        console.log('Python backend executable not found.');
      }
    });

    pythonProcess.on('exit', (code) => {
      console.log(`Python backend process exited with code ${code}`);
      pythonProcess = null;
    });

    // Wait for backend to be ready
    await waitForService(3001, 30000);
    console.log('Python backend started successfully');
    return true;

  } catch (error) {
    console.error('Failed to start Python backend:', error);
    
    // Show error dialog to user
    if (mainWindow) {
      dialog.showErrorBox(
        'Backend Error', 
        'Failed to start the application backend. The application may not function properly.\n\n' +
        'Error: ' + error.message
      );
    }
    return false;
  }
};

// Create main window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.cjs')
    },
    titleBarStyle: 'default',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    show: false // Don't show until ready
  });

  // Show loading screen
  mainWindow.loadFile(path.join(__dirname, 'loading.html'));
  mainWindow.show();

  // Start services and then load the main app
  startServices().then(() => {
    const startUrl = isDev 
      ? 'http://localhost:5173' 
      : `file://${path.join(__dirname, '../dist/index.html')}`;
      
    mainWindow.loadURL(startUrl);
mainWindow.webContents.openDevTools();
    if (isDev) {
      mainWindow.webContents.openDevTools();
    }
  }).catch((error) => {
    console.error('Failed to start services:', error);
    dialog.showErrorBox(
      'Startup Error',
      'Failed to start application services. Please check the logs and try again.'
    );
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Start all services
const startServices = async () => {
  try {
    console.log('Starting application services...');
    
    // Start Python backend (SQLite is file-based, no separate server needed)
    await startPythonBackend();
    
    console.log('All services started successfully');
  } catch (error) {
    console.error('Failed to start services:', error);
    throw error;
  }
};

// Cleanup processes
const cleanup = () => {
  console.log('Cleaning up processes...');
  
  if (pythonProcess) {
    console.log('Terminating Python backend...');
    pythonProcess.kill('SIGTERM');
    pythonProcess = null;
  }
};

// App event handlers
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  cleanup();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  cleanup();
});

// Handle app termination
process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);
process.on('exit', cleanup);

// IPC handlers
ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

ipcMain.handle('get-app-path', (event, name) => {
  return app.getPath(name);
});

ipcMain.handle('show-error-dialog', (event, title, content) => {
  dialog.showErrorBox(title, content);
});

ipcMain.handle('show-info-dialog', async (event, title, content) => {
  const result = await dialog.showMessageBox(mainWindow, {
    type: 'info',
    title: title,
    message: content,
    buttons: ['OK']
  });
  return result;
});