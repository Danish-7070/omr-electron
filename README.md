# EFSoft OMR Software - Desktop Application

A complete cross-platform desktop application for Optical Mark Recognition (OMR) processing, built with Electron, React, and Python with direct IPC communication.

## Features

- **Cross-platform**: Runs on Windows, macOS, and Linux
- **Offline operation**: No internet connection or ports required
- **Local database**: Uses local SQLite for data storage
- **Advanced OMR processing**: Computer vision-based bubble detection
- **Complete workflow**: Exam creation, student management, scanning, and results
- **Export capabilities**: PDF and Excel report generation
- **Direct IPC**: No HTTP server required - direct communication between frontend and backend

## Architecture

- **Frontend**: React with TypeScript and Tailwind CSS
- **Backend**: Python bridge with OpenCV for image processing
- **Database**: Local SQLite database
- **Desktop wrapper**: Electron for cross-platform compatibility
- **Communication**: Direct IPC between Electron and Python bridge

## Development Setup

### Prerequisites

- Node.js 16+ and npm
- Python 3.8+ with pip

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd omr-desktop-app
```

2. Install Node.js dependencies:
```bash
npm install
```

3. Install Python dependencies:
```bash
cd pServer
pip install -r requirements.txt
cd ..
```

4. Start development:
```bash
npm run electron:dev
```

This will start:
- Python backend on http://localhost:3001
- React frontend on http://localhost:5173
- Electron app with direct Python bridge communication

## Building for Production

### Build Python Backend

```bash
npm run build:backend
```

This creates a standalone Python bridge executable using PyInstaller.

### Build Desktop Application

For all platforms:
```bash
npm run dist
```

For specific platforms:
```bash
npm run dist:win    # Windows
npm run dist:mac    # macOS
npm run dist:linux  # Linux
```

## Project Structure

```
├── electron/           # Electron main process
│   ├── main.js        # Main Electron process
│   ├── python-bridge.cjs # Python bridge communication
│   ├── preload.js     # Preload script
│   └── loading.html   # Loading screen
├── src/               # React frontend
│   ├── components/    # Reusable components
│   ├── pages/         # Application pages
│   ├── context/       # React context providers
│   └── main.tsx       # Entry point
├── pServer/           # Python backend
│   ├── bridge.py      # Python bridge for IPC
│   ├── main.py        # FastAPI application
│   ├── models/        # Pydantic models
│   ├── routers/       # API route handlers
│   └── requirements.txt
├── build-resources/   # Build configuration
└── scripts/           # Build scripts
```

## Key Features

### Exam Management
- Create and configure exams
- Upload student lists via Excel
- Generate OMR answer sheets
- Upload solution keys from PDF

### OMR Processing
- Advanced computer vision algorithms
- Bubble detection and validation
- Batch processing capabilities
- Real-time processing feedback

### Results & Reports
- Comprehensive result analysis
- PDF and Excel export
- Statistical summaries
- Filtering and search capabilities

## Database

The application uses a local SQLite database that is created automatically with the desktop app. Data is stored locally in the user's application data directory.

## Security

- All data processing happens locally
- No cloud dependencies
- Secure local database storage
- Code signing for trusted installation

## Troubleshooting

### Database Connection Issues
- Check if SQLite database file is accessible
- Verify write permissions in user data directory
- Ensure database file is not corrupted

### Python Backend Issues
- Ensure all Python dependencies are installed
- Check Python version compatibility (3.8+)
- Verify OpenCV installation

### Build Issues
- Ensure PyInstaller is installed
- Check platform-specific build requirements
- Verify all Python dependencies are bundled correctly

## License

Copyright © 2025 Muhammad Danish Sarfraz Khan. All Rights Reserved.

This software is proprietary and confidential. See LICENSE file for details.