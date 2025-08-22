#!/usr/bin/env python3
"""
Python Bridge for Electron App
Handles direct communication with Electron main process via stdin/stdout
"""

import sys
import json
import asyncio
import logging
import traceback
from datetime import datetime
import base64
import io
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import our modules
from database import database, db_operations
from models.exam import ExamCreate, ExamUpdate
from models.student import StudentCreate
from models.solution import Solution, SolutionItem
from models.result import ResultCreate
from models.scan import process_omr_image
import pandas as pd

class PythonBridge:
    def __init__(self):
        self.db_initialized = False
        
    async def initialize_database(self):
        """Initialize the database connection"""
        if not self.db_initialized:
            try:
                # Get database path from environment or use default
                db_path = os.getenv("DATABASE_PATH", "omr_database.db")
                database.db_path = db_path
                await database.connect()
                self.db_initialized = True
                logger.info(f"Database initialized at {db_path}")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise

    async def create_exam(self, params):
        """Create a new exam"""
        try:
            await self.initialize_database()
            
            # Generate examId if not provided
            if not params.get('examId'):
                params['examId'] = f"EXAM_{int(datetime.utcnow().timestamp())}_{hash(params['name']) % 10000}"
            
            # Prepare exam data
            exam_data = {
                'examId': params['examId'],
                'name': params['name'],
                'dateTime': params['dateTime'],
                'time': params['time'],
                'numQuestions': params['numQuestions'],
                'marksPerMcq': params.get('marksPerMcq', 1),
                'passingPercentage': params.get('passingPercentage', 60),
                'wing': params['wing'],
                'course': params['course'],
                'module': params['module'],
                'sponsorDS': params['sponsorDS'],
                'instructions': params.get('instructions', 'Fill bubbles neatly with a black/blue pen, mark only one option per question—any extra, unclear, or incorrect marking will be considered wrong.'),
                'settings': params.get('settings', {}),
                'studentsUploaded': False,
                'solutionUploaded': False,
                'createdAt': datetime.utcnow(),
                'createdBy': 'System'
            }
            
            await db_operations.insert_one('exams', exam_data)
            
            return {
                'examId': params['examId'],
                'message': 'Exam created successfully'
            }
        except Exception as e:
            logger.error(f"Error creating exam: {e}")
            raise

    async def get_exams(self, params):
        """Get all exams"""
        try:
            await self.initialize_database()
            exams = await db_operations.find_many('exams', sort_by="createdAt", sort_order="DESC")
            return exams
        except Exception as e:
            logger.error(f"Error getting exams: {e}")
            raise

    async def get_exam(self, params):
        """Get a specific exam"""
        try:
            await self.initialize_database()
            exam = await db_operations.find_one('exams', {"examId": params['examId']})
            if not exam:
                raise ValueError("Exam not found")
            return exam
        except Exception as e:
            logger.error(f"Error getting exam: {e}")
            raise

    async def upload_students(self, params):
        """Upload students for an exam"""
        try:
            await self.initialize_database()
            
            exam_id = params['examId']
            students_data = params['studentsData']
            
            # Verify exam exists
            exam = await db_operations.find_one('exams', {"examId": exam_id})
            if not exam:
                raise ValueError("Exam not found")
            
            # Clear existing students for this exam
            await db_operations.delete_many('students', {"examId": exam_id})
            
            # Process and save students
            students = []
            for i, student_data in enumerate(students_data):
                student = {
                    "examId": exam_id,
                    "name": str(student_data['name']).strip(),
                    "lockerNumber": str(student_data['lockerNumber']).strip(),
                    "rank": str(student_data['rank']).strip(),
                    "copyNumber": str(i + 1).zfill(3),
                    "createdAt": datetime.utcnow()
                }
                students.append(student)
            
            # Insert students
            for student in students:
                await db_operations.insert_one('students', student)
            
            # Update exam to mark students as uploaded
            await db_operations.update_one(
                'exams',
                {"examId": exam_id},
                {"studentsUploaded": True}
            )
            
            return {
                "message": "Students uploaded successfully",
                "count": len(students),
                "students": [
                    {
                        "name": s["name"],
                        "lockerNumber": s["lockerNumber"],
                        "rank": s["rank"],
                        "copyNumber": s["copyNumber"]
                    }
                    for s in students
                ]
            }
        except Exception as e:
            logger.error(f"Error uploading students: {e}")
            raise

    async def get_students(self, params):
        """Get students for an exam"""
        try:
            await self.initialize_database()
            students = await db_operations.find_many('students', {"examId": params['examId']}, sort_by="copyNumber", sort_order="ASC")
            return students
        except Exception as e:
            logger.error(f"Error getting students: {e}")
            raise

    async def upload_solution(self, params):
        """Upload solution for an exam"""
        try:
            await self.initialize_database()
            
            exam_id = params['examId']
            solutions_data = params['solutionsData']
            
            # Verify exam exists
            exam = await db_operations.find_one('exams', {"examId": exam_id})
            if not exam:
                raise ValueError("Exam not found")
            
            # Delete existing solution
            await db_operations.delete_one('solutions', {"examId": exam_id})
            
            # Create new solution
            solution_data = {
                'examId': exam_id,
                'solutions': solutions_data,
                'uploadedAt': datetime.utcnow()
            }
            
            await db_operations.insert_one('solutions', solution_data)
            
            # Update exam to mark solution as uploaded
            await db_operations.update_one(
                'exams',
                {"examId": exam_id},
                {"solutionUploaded": True}
            )
            
            return {
                "message": "Solution uploaded successfully",
                "solutionCount": len(solutions_data)
            }
        except Exception as e:
            logger.error(f"Error uploading solution: {e}")
            raise

    async def get_solution(self, params):
        """Get solution for an exam"""
        try:
            await self.initialize_database()
            solution = await db_operations.find_one('solutions', {"examId": params['examId']})
            if not solution:
                raise ValueError("Solution not found")
            return solution
        except Exception as e:
            logger.error(f"Error getting solution: {e}")
            raise

    async def process_omr_image(self, params):
        """Process a single OMR image"""
        try:
            await self.initialize_database()
            
            exam_id = params['examId']
            image_data = base64.b64decode(params['imageData'])
            student_id = params['studentId']
            
            # Get exam details
            exam = await db_operations.find_one('exams', {"examId": exam_id})
            if not exam:
                raise ValueError("Exam not found")
            
            # Get solution
            solution = await db_operations.find_one('solutions', {"examId": exam_id})
            if not solution:
                raise ValueError("Solution not found")
            
            # Extract answer key
            answer_key = [sol['answer'] for sol in sorted(solution['solutions'], key=lambda x: x['question'])]
            
            # Process the OMR image
            result = process_omr_image(
                image_data=image_data,
                answer_key=answer_key,
                num_questions=exam['numQuestions'],
                student_id=student_id
            )
            
            # Calculate additional metrics
            total_marks = exam['numQuestions'] * exam['marksPerMcq']
            score = result['score'] * exam['marksPerMcq']
            percentage = (score / total_marks * 100) if total_marks > 0 else 0
            
            return {
                "success": True,
                "examId": exam_id,
                "studentId": student_id,
                "response": {
                    "studentId": student_id,
                    "score": score,
                    "totalMarks": total_marks,
                    "percentage": percentage,
                    "accuracy": result["accuracy"],
                    "responses": result["responses"],
                    "correctAnswers": result["correct_answers"],
                    "incorrectAnswers": result["incorrect_answers"],
                    "blankAnswers": result["blank_answers"],
                    "multipleMarks": result["multiple_marks"],
                    "invalidAnswers": result["invalid_answers"],
                    "processingMetadata": result["processing_metadata"],
                    "detailedResponses": result["detailed_responses"]
                }
            }
        except Exception as e:
            logger.error(f"Error processing OMR image: {e}")
            raise

    async def batch_process_omr(self, params):
        """Process multiple OMR images"""
        try:
            await self.initialize_database()
            
            exam_id = params['examId']
            images_data = params['imagesData']
            
            # Get exam details
            exam = await db_operations.find_one('exams', {"examId": exam_id})
            if not exam:
                raise ValueError("Exam not found")
            
            # Get solution
            solution = await db_operations.find_one('solutions', {"examId": exam_id})
            if not solution:
                raise ValueError("Solution not found")
            
            # Extract answer key
            answer_key = [sol['answer'] for sol in sorted(solution['solutions'], key=lambda x: x['question'])]
            
            results = []
            for i, image_data_b64 in enumerate(images_data):
                try:
                    student_id = f"STUDENT_{str(i+1).zfill(3)}"
                    image_data = base64.b64decode(image_data_b64)
                    
                    # Process the OMR image
                    processing_result = process_omr_image(
                        image_data=image_data,
                        answer_key=answer_key,
                        num_questions=exam['numQuestions'],
                        student_id=student_id
                    )
                    
                    # Calculate metrics
                    total_marks = exam['numQuestions'] * exam['marksPerMcq']
                    score = processing_result['score'] * exam['marksPerMcq']
                    percentage = (score / total_marks * 100) if total_marks > 0 else 0
                    
                    result_data = {
                        "studentId": student_id,
                        "filename": f"image_{i+1}",
                        "score": score,
                        "totalMarks": total_marks,
                        "percentage": percentage,
                        "accuracy": processing_result["accuracy"],
                        "responses": processing_result["responses"],
                        "correctAnswers": processing_result["correct_answers"],
                        "incorrectAnswers": processing_result["incorrect_answers"],
                        "blankAnswers": processing_result["blank_answers"],
                        "multipleMarks": processing_result["multiple_marks"],
                        "invalidAnswers": processing_result["invalid_answers"],
                        "processingMetadata": processing_result["processing_metadata"],
                        "success": True
                    }
                    
                    results.append(result_data)
                    
                except Exception as e:
                    logger.error(f"Failed to process image {i+1}: {str(e)}")
                    results.append({
                        "studentId": f"STUDENT_{str(i+1).zfill(3)}",
                        "filename": f"image_{i+1}",
                        "success": False,
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "examId": exam_id,
                "totalImages": len(images_data),
                "processedSuccessfully": len([r for r in results if r.get("success", False)]),
                "results": results
            }
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            raise

    async def save_result(self, params):
        """Save a result to the database"""
        try:
            await self.initialize_database()
            
            result_data = params.copy()
            result_data["processedAt"] = datetime.utcnow()
            
            # Check if result already exists
            existing_result = await db_operations.find_one('results', {
                "examId": result_data["examId"],
                "studentId": result_data["studentId"]
            })
            
            if existing_result:
                # Update existing result
                await db_operations.update_one(
                    'results',
                    {"examId": result_data["examId"], "studentId": result_data["studentId"]},
                    result_data
                )
            else:
                # Create new result
                await db_operations.insert_one('results', result_data)
            
            return {"message": "Result saved successfully"}
        except Exception as e:
            logger.error(f"Error saving result: {e}")
            raise

    async def get_results(self, params):
        """Get results for an exam"""
        try:
            await self.initialize_database()
            results = await db_operations.find_many('results', {"examId": params['examId']}, sort_by="processedAt", sort_order="DESC")
            return results
        except Exception as e:
            logger.error(f"Error getting results: {e}")
            raise

    async def get_all_results(self, params):
        """Get all results"""
        try:
            await self.initialize_database()
            results = await db_operations.find_many('results', sort_by="processedAt", sort_order="DESC")
            return results
        except Exception as e:
            logger.error(f"Error getting all results: {e}")
            raise

    async def generate_omr_sheets(self, params):
        """Generate OMR sheets for an exam"""
        try:
            await self.initialize_database()
            
            exam_id = params['examId']
            
            # Get exam details
            exam = await db_operations.find_one('exams', {"examId": exam_id})
            if not exam:
                raise ValueError("Exam not found")
            
            # Get students
            students = await db_operations.find_many('students', {"examId": exam_id}, sort_by="copyNumber", sort_order="ASC")
            
            if not students:
                raise ValueError("No students found for this exam")
            
            sheets = []
            for student in students:
                sheet = self.generate_omr_sheet(exam, student)
                sheets.append(sheet)
            
            return {
                "examName": exam["name"],
                "totalSheets": len(sheets),
                "sheets": [
                    {
                        "studentName": sheet["studentName"],
                        "copyNumber": sheet["copyNumber"],
                        "previewData": sheet["previewData"]
                    }
                    for sheet in sheets
                ]
            }
        except Exception as e:
            logger.error(f"Error generating OMR sheets: {e}")
            raise

    def generate_omr_sheet(self, exam, student):
        """Generate a single OMR sheet"""
        try:
            total_marks = exam["numQuestions"] * exam["marksPerMcq"]
            
            return {
                "studentName": student["name"],
                "copyNumber": student["copyNumber"],
                "previewData": {
                    "header": {
                        "dateTime": exam["dateTime"],
                        "time": exam["time"],
                        "examSecret": "EXAM SECRET",
                        "copyNumber": student["copyNumber"]
                    },
                    "body": {
                        "centerLine": "SA & MW",
                        "examDetails": {
                            "wing": exam["wing"],
                            "course": exam["course"],
                            "module": exam["module"],
                            "sponsorDS": exam["sponsorDS"],
                            "numMcqs": exam["numQuestions"],
                            "marksPerMcq": exam["marksPerMcq"],
                            "totalMarks": total_marks,
                            "passingPercentage": exam["passingPercentage"]
                        },
                        "studentInfo": {
                            "lockerNumber": student["lockerNumber"],
                            "rank": student["name"],
                            "name": student["name"]
                        },
                        "instructions": exam.get("instructions", "Fill bubbles neatly with a black/blue pen, mark only one option per question—any extra, unclear, or incorrect marking will be considered wrong.")
                    },
                    "mcqSection": {
                        "questions": [
                            {
                                "number": i + 1,
                                "options": ["A", "B", "C", "D", "E"]
                            }
                            for i in range(exam["numQuestions"])
                        ]
                    },
                    "footer": {
                        "studentSignature": "",
                        "result": "",
                        "invigilatorSignature": ""
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error generating OMR sheet: {e}")
            raise

    async def download_omr_sheets(self, params):
        """Download OMR sheets as ZIP"""
        try:
            # For now, return the sheets data
            # In a full implementation, this would generate PDFs and create a ZIP
            sheets_data = await self.generate_omr_sheets(params)
            return {
                "message": "OMR sheets ready for download",
                "data": sheets_data
            }
        except Exception as e:
            logger.error(f"Error downloading OMR sheets: {e}")
            raise

    async def get_settings(self, params):
        """Get application settings"""
        try:
            # Return default settings
            return {
                "scanner": {
                    "resolution": 300,
                    "colorMode": "grayscale",
                    "autoFeed": True,
                    "duplex": False
                },
                "processing": {
                    "confidenceThreshold": 0.7,
                    "autoProcessing": True,
                    "batchSize": 50
                },
                "exam": {
                    "defaultQuestions": 100,
                    "passingScore": 60,
                    "allowPartialCredit": False
                },
                "database": {
                    "connectionString": "sqlite:///omr_database.db",
                    "connected": True
                }
            }
        except Exception as e:
            logger.error(f"Error getting settings: {e}")
            raise

    async def update_settings(self, params):
        """Update application settings"""
        try:
            # For now, just return the updated settings
            # In a full implementation, this would save to a config file
            return params
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            raise

    async def handle_message(self, message):
        """Handle incoming message from Electron"""
        try:
            data = json.loads(message.strip())
            method = data.get('method')
            params = data.get('params', {})
            message_id = data.get('id')
            
            # Call the appropriate method
            if hasattr(self, method):
                result = await getattr(self, method)(params)
                response = {
                    'id': message_id,
                    'result': result
                }
                print(f"RESPONSE:{json.dumps(response)}", flush=True)
            else:
                error_response = {
                    'id': message_id,
                    'message': f'Unknown method: {method}'
                }
                print(f"ERROR:{json.dumps(error_response)}", flush=True)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            logger.error(traceback.format_exc())
            error_response = {
                'id': data.get('id') if 'data' in locals() else 0,
                'message': str(e)
            }
            print(f"ERROR:{json.dumps(error_response)}", flush=True)

    async def run(self):
        """Main run loop"""
        logger.info("Python bridge started")
        
        try:
            while True:
                line = sys.stdin.readline()
                if not line:
                    break
                await self.handle_message(line)
        except KeyboardInterrupt:
            logger.info("Python bridge stopped")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            logger.error(traceback.format_exc())

if __name__ == "__main__":
    bridge = PythonBridge()
    asyncio.run(bridge.run())