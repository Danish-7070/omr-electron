import React, { createContext, useContext, ReactNode } from 'react';
import * as XLSX from 'xlsx';

// Extend the Window interface to include electronAPI
declare global {
  interface Window {
    electronAPI?: any;
  }
}

interface ApiContextType {
  api: any;
}

const ApiContext = createContext<ApiContextType | undefined>(undefined);

// Create a mock API object that uses Electron IPC instead of HTTP
const createElectronAPI = () => {
  const electronAPI = window.electronAPI;
  
  if (!electronAPI) {
    throw new Error('Electron API not available. This app must run in Electron.');
  }

  return {
    // Exams
    get: async (endpoint: string) => {
      if (endpoint === '/exams') {
        return { data: await electronAPI.api.getExams() };
      } else if (endpoint.startsWith('/exams/')) {
        const examId = endpoint.split('/')[2];
        return { data: await electronAPI.api.getExam(examId) };
      } else if (endpoint.startsWith('/students/')) {
        const examId = endpoint.split('/')[2];
        return { data: await electronAPI.api.getStudents(examId) };
      } else if (endpoint.startsWith('/solutions/')) {
        const examId = endpoint.split('/')[2];
        return { data: await electronAPI.api.getSolution(examId) };
      } else if (endpoint.startsWith('/results/exam/')) {
        const examId = endpoint.split('/')[3];
        return { data: await electronAPI.api.getResults(examId) };
      } else if (endpoint === '/results/all') {
        return { data: await electronAPI.api.getAllResults() };
      } else if (endpoint.startsWith('/omr/') && endpoint.endsWith('/sheets')) {
        const examId = endpoint.split('/')[2];
        return { data: await electronAPI.api.generateOMRSheets(examId) };
      } else if (endpoint.startsWith('/omr/') && endpoint.endsWith('/download')) {
        const examId = endpoint.split('/')[2];
        return { data: await electronAPI.api.downloadOMRSheets(examId) };
      } else if (endpoint === '/settings') {
        return { data: await electronAPI.api.getSettings() };
      }
      throw new Error(`Unsupported GET endpoint: ${endpoint}`);
    },

    post: async (endpoint: string, data?: any, config?: any) => {
      if (endpoint === '/exams') {
        return { data: await electronAPI.api.createExam(data) };
      } else if (endpoint.startsWith('/students/') && endpoint.endsWith('/upload')) {
        const examId = endpoint.split('/')[2];
        
        // Handle FormData for file uploads
        if (data instanceof FormData) {
          const file = data.get('file') as File;
          if (file) {
            // Read Excel file and convert to student data
            const studentsData = await parseExcelFile(file);
            return { data: await electronAPI.api.uploadStudents(examId, studentsData) };
          }
        }
        throw new Error('Invalid student upload data');
      } else if (endpoint.startsWith('/solutions/') && endpoint.endsWith('/upload')) {
        const examId = endpoint.split('/')[2];
        
        if (data instanceof FormData) {
          const file = data.get('file') as File;
          if (file) {
            // For now, we'll need to handle PDF parsing in the frontend
            // or pass the file data to Python for processing
            throw new Error('PDF solution upload not yet implemented in bridge mode');
          }
        }
        throw new Error('Invalid solution upload data');
      } else if (endpoint.startsWith('/solutions/') && endpoint.endsWith('/manual')) {
        const examId = endpoint.split('/')[2];
        return { data: await electronAPI.api.uploadSolution(examId, data.solutions) };
      } else if (endpoint.startsWith('/scan/process')) {
        // Handle single image processing
        if (data instanceof FormData) {
          const examId = data.get('examId') as string;
          const studentId = data.get('studentId') as string;
          const image = data.get('image') as File;
          
          if (image) {
            const imageData = await fileToBase64(image);
            return { data: await electronAPI.api.processOMRImage(examId, imageData, studentId) };
          }
        }
        throw new Error('Invalid scan process data');
      } else if (endpoint.startsWith('/scan/batch-process')) {
        // Handle batch processing
        if (data instanceof FormData) {
          const examId = data.get('examId') as string;
          const images = data.getAll('images') as File[];
          
          if (images.length > 0) {
            const imagesData = await Promise.all(images.map(img => fileToBase64(img)));
            return { data: await electronAPI.api.batchProcessOMR(examId, imagesData) };
          }
        }
        throw new Error('Invalid batch process data');
      } else if (endpoint === '/results/save') {
        return { data: await electronAPI.api.saveResult(data) };
      } else if (endpoint === '/results/publish') {
        // Handle publishing results (save multiple results)
        const promises = data.results.map((result: any) => electronAPI.api.saveResult({
          examId: data.examId,
          studentId: result.studentId,
          studentName: result.studentName,
          examName: data.examName,
          score: result.score,
          totalMarks: result.totalMarks,
          percentage: result.percentage,
          passFailStatus: result.passFailStatus,
          correctAnswers: result.correctAnswers,
          incorrectAnswers: result.incorrectAnswers,
          blankAnswers: result.blankAnswers,
          multipleMarks: result.multipleMarks,
          responses: result.responses,
          studentInfo: result.studentInfo,
        }));
        await Promise.all(promises);
        return { data: { message: `Successfully published ${data.results.length} results` } };
      } else if (endpoint === '/results/download-all-pdf') {
        // For PDF generation, we'll need to implement this differently
        // For now, return a mock response
        return { data: new Blob(['Mock PDF data'], { type: 'application/pdf' }) };
      } else if (endpoint === '/settings') {
        return { data: await electronAPI.api.updateSettings(data) };
      }
      throw new Error(`Unsupported POST endpoint: ${endpoint}`);
    },

    put: async (endpoint: string, data?: any) => {
      if (endpoint === '/settings') {
        return { data: await electronAPI.api.updateSettings(data) };
      }
      throw new Error(`Unsupported PUT endpoint: ${endpoint}`);
    },

    delete: async (endpoint: string) => {
      throw new Error(`DELETE operations not yet implemented: ${endpoint}`);
    }
  };
};

// Helper function to convert File to base64
const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => {
      const result = reader.result as string;
      // Remove the data URL prefix to get just the base64 data
      const base64Data = result.split(',')[1];
      resolve(base64Data);
    };
    reader.onerror = error => reject(error);
  });
};

// Helper function to parse Excel file
const parseExcelFile = async (file: File): Promise<any[]> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const data = new Uint8Array(e.target?.result as ArrayBuffer);
        
        // We'll need to use a library like xlsx to parse Excel files
        const workbook = XLSX.read(data, { type: 'array' });
        const sheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[sheetName];
        const jsonData = XLSX.utils.sheet_to_json(worksheet);
        
        // Convert to expected format
        const students = jsonData.map((row: any) => ({
          name: row['Name'] || row['name'] || '',
          lockerNumber: row['Locker number'] || row['Locker Number'] || row['lockerNumber'] || '',
          rank: row['Rank'] || row['rank'] || ''
        })).filter(student => student.name && student.lockerNumber && student.rank);
        
        resolve(students);
      } catch (error) {
        reject(error);
      }
    };
    reader.onerror = error => reject(error);
    reader.readAsArrayBuffer(file);
  });
};

interface ApiProviderProps {
  children: ReactNode;
}

export const ApiProvider: React.FC<ApiProviderProps> = ({ children }) => {
  const api = createElectronAPI();

  return (
    <ApiContext.Provider value={{ api }}>
      {children}
    </ApiContext.Provider>
  );
};

export const useApi = () => {
  const context = useContext(ApiContext);
  if (context === undefined) {
    throw new Error('useApi must be used within an ApiProvider');
  }
  return context;
};