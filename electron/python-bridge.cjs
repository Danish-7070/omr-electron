const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class PythonBridge {
  constructor() {
    this.pythonProcess = null;
    this.isReady = false;
    this.messageQueue = [];
    this.callbacks = new Map();
    this.messageId = 0;
  }

  async initialize(isDev = false) {
    return new Promise((resolve, reject) => {
      try {
        const pythonPath = this.getPythonExecutablePath(isDev);
        
        // Set up database path in user data directory
        const { app } = require('electron');
        const dbPath = path.join(app.getPath('userData'), 'omr_database.db');
        
        const env = {
          ...process.env,
          DATABASE_PATH: dbPath,
          PYTHONPATH: isDev ? path.join(__dirname, '..', 'pServer') : path.dirname(pythonPath)
        };

        this.pythonProcess = spawn(pythonPath, [], {
          stdio: ['pipe', 'pipe', 'pipe'],
          env: env,
          cwd: isDev ? path.join(__dirname, '..', 'pServer') : path.dirname(pythonPath)
        });

        this.pythonProcess.stdout.on('data', (data) => {
          this.handlePythonMessage(data.toString());
        });

        this.pythonProcess.stderr.on('data', (data) => {
          console.error('Python stderr:', data.toString());
        });

        this.pythonProcess.on('error', (error) => {
          console.error('Python process error:', error);
          reject(error);
        });

        this.pythonProcess.on('exit', (code) => {
          console.log(`Python process exited with code ${code}`);
          this.isReady = false;
        });

        // Wait for Python process to be ready
        setTimeout(() => {
          this.isReady = true;
          this.processMessageQueue();
          resolve();
        }, 2000);

      } catch (error) {
        reject(error);
      }
    });
  }

  getPythonExecutablePath(isDev) {
    if (isDev) {
      return 'python';
    }
    
    const platform = process.platform;
    const { app } = require('electron');
    const resourcesPath = process.resourcesPath;
    
    if (platform === 'win32') {
      return path.join(resourcesPath, 'python-backend', 'bridge.exe');
    } else if (platform === 'darwin') {
      return path.join(resourcesPath, 'python-backend', 'bridge');
    } else {
      return path.join(resourcesPath, 'python-backend', 'bridge');
    }
  }

  handlePythonMessage(data) {
    try {
      const lines = data.trim().split('\n');
      for (const line of lines) {
        if (line.startsWith('RESPONSE:')) {
          const response = JSON.parse(line.substring(9));
          const callback = this.callbacks.get(response.id);
          if (callback) {
            callback(null, response.result);
            this.callbacks.delete(response.id);
          }
        } else if (line.startsWith('ERROR:')) {
          const error = JSON.parse(line.substring(6));
          const callback = this.callbacks.get(error.id);
          if (callback) {
            callback(new Error(error.message), null);
            this.callbacks.delete(error.id);
          }
        }
      }
    } catch (error) {
      console.error('Error parsing Python message:', error);
    }
  }

  processMessageQueue() {
    while (this.messageQueue.length > 0) {
      const { method, params, callback } = this.messageQueue.shift();
      this.callPython(method, params, callback);
    }
  }

  callPython(method, params = {}, callback) {
    if (!this.isReady) {
      this.messageQueue.push({ method, params, callback });
      return;
    }

    const messageId = ++this.messageId;
    this.callbacks.set(messageId, callback);

    const message = {
      id: messageId,
      method: method,
      params: params
    };

    try {
      this.pythonProcess.stdin.write(JSON.stringify(message) + '\n');
    } catch (error) {
      callback(error, null);
      this.callbacks.delete(messageId);
    }
  }

  // API Methods
  async createExam(examData) {
    return new Promise((resolve, reject) => {
      this.callPython('create_exam', examData, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async getExams() {
    return new Promise((resolve, reject) => {
      this.callPython('get_exams', {}, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async getExam(examId) {
    return new Promise((resolve, reject) => {
      this.callPython('get_exam', { examId }, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async uploadStudents(examId, studentsData) {
    return new Promise((resolve, reject) => {
      this.callPython('upload_students', { examId, studentsData }, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async getStudents(examId) {
    return new Promise((resolve, reject) => {
      this.callPython('get_students', { examId }, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async uploadSolution(examId, solutionsData) {
    return new Promise((resolve, reject) => {
      this.callPython('upload_solution', { examId, solutionsData }, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async getSolution(examId) {
    return new Promise((resolve, reject) => {
      this.callPython('get_solution', { examId }, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async processOMRImage(examId, imageData, studentId) {
    return new Promise((resolve, reject) => {
      this.callPython('process_omr_image', { examId, imageData, studentId }, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async batchProcessOMR(examId, imagesData) {
    return new Promise((resolve, reject) => {
      this.callPython('batch_process_omr', { examId, imagesData }, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async saveResult(resultData) {
    return new Promise((resolve, reject) => {
      this.callPython('save_result', resultData, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async getResults(examId) {
    return new Promise((resolve, reject) => {
      this.callPython('get_results', { examId }, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async getAllResults() {
    return new Promise((resolve, reject) => {
      this.callPython('get_all_results', {}, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async generateOMRSheets(examId) {
    return new Promise((resolve, reject) => {
      this.callPython('generate_omr_sheets', { examId }, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async downloadOMRSheets(examId) {
    return new Promise((resolve, reject) => {
      this.callPython('download_omr_sheets', { examId }, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async getSettings() {
    return new Promise((resolve, reject) => {
      this.callPython('get_settings', {}, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  async updateSettings(settings) {
    return new Promise((resolve, reject) => {
      this.callPython('update_settings', settings, (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  terminate() {
    if (this.pythonProcess) {
      this.pythonProcess.kill('SIGTERM');
      this.pythonProcess = null;
    }
    this.isReady = false;
    this.callbacks.clear();
    this.messageQueue = [];
  }
}

module.exports = PythonBridge;