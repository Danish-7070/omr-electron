const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // App info
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getAppPath: (name) => ipcRenderer.invoke('get-app-path', name),
  showErrorDialog: (title, content) => ipcRenderer.invoke('show-error-dialog', title, content),
  showInfoDialog: (title, content) => ipcRenderer.invoke('show-info-dialog', title, content),
  
  // Platform information
  platform: process.platform,
  isPackaged: process.env.NODE_ENV !== 'development',

  // Python bridge communication
  pythonCall: (method, params) => ipcRenderer.invoke('python-call', method, params),

  // Specific API methods for easier use
  api: {
    // Exams
    createExam: (examData) => ipcRenderer.invoke('python-call', 'create_exam', examData),
    getExams: () => ipcRenderer.invoke('python-call', 'get_exams', {}),
    getExam: (examId) => ipcRenderer.invoke('python-call', 'get_exam', { examId }),
    
    // Students
    uploadStudents: (examId, studentsData) => ipcRenderer.invoke('python-call', 'upload_students', { examId, studentsData }),
    getStudents: (examId) => ipcRenderer.invoke('python-call', 'get_students', { examId }),
    
    // Solutions
    uploadSolution: (examId, solutionsData) => ipcRenderer.invoke('python-call', 'upload_solution', { examId, solutionsData }),
    getSolution: (examId) => ipcRenderer.invoke('python-call', 'get_solution', { examId }),
    
    // OMR Processing
    processOMRImage: (examId, imageData, studentId) => ipcRenderer.invoke('python-call', 'process_omr_image', { examId, imageData, studentId }),
    batchProcessOMR: (examId, imagesData) => ipcRenderer.invoke('python-call', 'batch_process_omr', { examId, imagesData }),
    
    // Results
    saveResult: (resultData) => ipcRenderer.invoke('python-call', 'save_result', resultData),
    getResults: (examId) => ipcRenderer.invoke('python-call', 'get_results', { examId }),
    getAllResults: () => ipcRenderer.invoke('python-call', 'get_all_results', {}),
    
    // OMR Sheets
    generateOMRSheets: (examId) => ipcRenderer.invoke('python-call', 'generate_omr_sheets', { examId }),
    downloadOMRSheets: (examId) => ipcRenderer.invoke('python-call', 'download_omr_sheets', { examId }),
    
    // Settings
    getSettings: () => ipcRenderer.invoke('python-call', 'get_settings', {}),
    updateSettings: (settings) => ipcRenderer.invoke('python-call', 'update_settings', settings)
  }
});