const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const PythonBridge = require('./python-bridge.cjs');

const isDev = process.env.NODE_ENV === 'development';
const isPackaged = app.isPackaged;

let mainWindow;
let pythonBridge = null;

// Initialize Python Bridge
const initializePythonBridge = async () => {
  try {
    pythonBridge = new PythonBridge();
    await pythonBridge.initialize(isDev);
    console.log('Python bridge initialized successfully');
    return true;
  } catch (error) {
    console.error('Failed to initialize Python bridge:', error);
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
    show: false
  });

  // Show loading screen
  mainWindow.loadFile(path.join(__dirname, 'loading.html'));
  mainWindow.show();

  // Initialize Python bridge and then load the main app
  initializePythonBridge().then((success) => {
    if (success) {
      if (isDev) {
        mainWindow.loadURL('http://localhost:5173');
        mainWindow.webContents.openDevTools();
      } else {
        const indexPath = path.join(__dirname, '../dist/index.html');
        if (fs.existsSync(indexPath)) {
          mainWindow.loadFile(indexPath);
        } else {
          console.error('Production build not found at:', indexPath);
          dialog.showErrorBox(
            'Build Error',
            'Production build not found. Please run "npm run build" first.'
          );
        }
      }
    } else {
      dialog.showErrorBox(
        'Initialization Error',
        'Failed to initialize the application backend. Please try restarting the application.'
      );
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Cleanup processes
const cleanup = () => {
  console.log('Cleaning up processes...');
  
  if (pythonBridge) {
    pythonBridge.terminate();
    pythonBridge = null;
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

// IPC handlers for Python bridge communication
ipcMain.handle('python-call', async (event, method, params) => {
  if (!pythonBridge) {
    throw new Error('Python bridge not initialized');
  }

  try {
    switch (method) {
      case 'create_exam':
        return await pythonBridge.createExam(params);
      case 'get_exams':
        return await pythonBridge.getExams();
      case 'get_exam':
        return await pythonBridge.getExam(params.examId);
      case 'upload_students':
        return await pythonBridge.uploadStudents(params.examId, params.studentsData);
      case 'get_students':
        return await pythonBridge.getStudents(params.examId);
      case 'upload_solution':
        return await pythonBridge.uploadSolution(params.examId, params.solutionsData);
      case 'get_solution':
        return await pythonBridge.getSolution(params.examId);
      case 'process_omr_image':
        return await pythonBridge.processOMRImage(params.examId, params.imageData, params.studentId);
      case 'batch_process_omr':
        return await pythonBridge.batchProcessOMR(params.examId, params.imagesData);
      case 'save_result':
        return await pythonBridge.saveResult(params);
      case 'get_results':
        return await pythonBridge.getResults(params.examId);
      case 'get_all_results':
        return await pythonBridge.getAllResults();
      case 'generate_omr_sheets':
        return await pythonBridge.generateOMRSheets(params.examId);
      case 'download_omr_sheets':
        return await pythonBridge.downloadOMRSheets(params.examId);
      case 'get_settings':
        return await pythonBridge.getSettings();
      case 'update_settings':
        return await pythonBridge.updateSettings(params);
      default:
        throw new Error(`Unknown method: ${method}`);
    }
  } catch (error) {
    console.error(`Error calling Python method ${method}:`, error);
    throw error;
  }
});

// Other IPC handlers
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