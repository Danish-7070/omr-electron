from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import List
import pdfplumber
from models.solution import Solution, SolutionItem
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re

router = APIRouter()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ManualSolutionRequest(BaseModel):
    examId: str
    solutions: List[SolutionItem]

class SolutionItem(BaseModel):
    question: int
    answer: str

def get_database():
    from main import app
    return app.state.db_operations

def extract_answers_from_pdf(pdf_file) -> List[SolutionItem]:
    solutions = []
    current_question = None
    question_buffer = []  # Buffer to accumulate question-related text across pages
    processing_answer = False  # Flag to track if we're processing answer options
    previous_page_last_text = ""  # Track last text of previous page for continuity
    expected_options = set('abcde')  # Track collected options to ensure completeness

    try:
        with pdfplumber.open(pdf_file.file) as pdf:
            logger.info(f"Processing PDF with {len(pdf.pages)} pages")
            for page_num, page in enumerate(pdf.pages):
                logger.debug(f"Processing page {page_num + 1}")
                # Extract words with formatting information
                words = page.extract_words(extra_attrs=["fontname", "size"])
                if not words:
                    logger.warning(f"No text extracted from page {page_num + 1}")
                    continue

                i = 0
                # Prepend last text from previous page to handle split questions
                if previous_page_last_text and question_buffer:
                    question_buffer.append({
                        'text': previous_page_last_text,
                        'fontname': '',
                        'size': 0
                    })
                
                while i < len(words):
                    word = words[i]
                    text = word['text'].strip()

                    # Detect question number (e.g., "1.", "2.", or "Question 3")
                    if re.match(r'^\d+\.$', text) or text.lower().startswith('question'):
                        try:
                            # Save previous question if we have a valid answer
                            if current_question and question_buffer:
                                answer = identify_answer(question_buffer, expected_options)
                                if answer:
                                    existing_solution = next((s for s in solutions if s.question == current_question), None)
                                    if existing_solution:
                                        logger.warning(f"Duplicate answer for question {current_question}. Keeping first: {existing_solution.answer}")
                                    else:
                                        solutions.append(SolutionItem(question=current_question, answer=answer))
                                        logger.debug(f"Added solution: question={current_question}, answer={answer}")
                            
                            # Start new question
                            if re.match(r'^\d+\.$', text):
                                current_question = int(text.split('.')[0])
                            else:
                                number_text = ''
                                j = i
                                look_ahead_limit = min(i + 5, len(words))
                                while j < look_ahead_limit:
                                    number_text += words[j]['text'] + ' '
                                    j += 1
                                number_match = re.search(r'(\d+)', number_text.replace('Question', '').replace('of', '').replace('DPG', ''))
                                if number_match:
                                    current_question = int(number_match.group(1))
                                else:
                                    current_question = None
                                    logger.warning(f"Could not extract question number from: {number_text}")
                            question_buffer = []
                            processing_answer = False
                            expected_options = set()
                            logger.debug(f"Found question number: {current_question}")
                        except (ValueError, IndexError):
                            logger.warning(f"Invalid question number format: {text}")
                            current_question = None
                        i += 1
                        continue

                    # Accumulate text in buffer
                    if current_question:
                        question_buffer.append({
                            'text': text,
                            'fontname': word.get('fontname', ''),
                            'size': word.get('size', 0)
                        })
                        
                        # Detect start of answer options
                        if text.lower() in ('a.', 'b.', 'c.', 'd.', 'e.'):
                            processing_answer = True
                            expected_options.add(text[0].lower())

                    i += 1
                
                # Store the last text of the current page for continuity
                previous_page_last_text = words[-1]['text'].strip() if words else ""

            # Process the last question after the loop
            if current_question and question_buffer:
                answer = identify_answer(question_buffer, expected_options)
                if answer:
                    existing_solution = next((s for s in solutions if s.question == current_question), None)
                    if existing_solution:
                        logger.warning(f"Duplicate answer for question {current_question}. Keeping first: {existing_solution.answer}")
                    else:
                        solutions.append(SolutionItem(question=current_question, answer=answer))
                        logger.debug(f"Added solution: question={current_question}, answer={answer}")

    except Exception as e:
        logger.error(f"Failed to parse PDF: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")

    if not solutions:
        logger.warning("No solutions extracted from PDF")
        raise HTTPException(status_code=400, detail="No valid solutions found in PDF")

    # Sort solutions by question number
    solutions.sort(key=lambda x: x.question)

    # Log the extracted answer key
    logger.info("Extracted Answer Key:")
    for solution in solutions:
        logger.info(f"Question {solution.question}: {solution.answer}")

    # Check for missing questions
    expected_questions = set(range(1, len(solutions) + 1))
    actual_questions = set(solution.question for solution in solutions)
    missing_questions = expected_questions - actual_questions

    if missing_questions:
        logger.warning(f"Missing questions detected: {sorted(missing_questions)}")

    logger.info(f"Extracted {len(solutions)} solutions")
    return solutions

def identify_answer(question_buffer: List[dict], expected_options: set) -> str:
    """Identify the correct answer from the question buffer based on bold formatting."""
    collected_options = set()
    for i, item in enumerate(question_buffer):
        text = item['text'].lower()
        if text in ('a.', 'b.', 'c.', 'd.', 'e.'):
            collected_options.add(text[0])
            is_bold = 'bold' in item.get('fontname', '').lower()
            if not is_bold and i + 1 < len(question_buffer):
                next_item = question_buffer[i + 1]
                is_bold = 'bold' in next_item.get('fontname', '').lower()
            if is_bold and collected_options.issubset(expected_options):
                return text[0].upper()
    return None if not collected_options.issubset(expected_options) else None

@router.post("/{exam_id}/upload")
async def upload_solution(exam_id: str, file: UploadFile = File(...), db_ops=Depends(get_database)):
    try:
        if not file:
            logger.error("No file provided in request")
            raise HTTPException(status_code=400, detail="No file uploaded")
        if not file.filename:
            logger.error("File has no filename")
            raise HTTPException(status_code=400, detail="No filename provided")
        if not file.filename.lower().endswith('.pdf'):
            logger.error(f"Invalid file extension: {file.filename}")
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        logger.info(f"Uploading solution for exam_id: {exam_id}, file: {file.filename}, size: {file.size} bytes")

        exam_data = await db_ops.find_one('exams', {"examId": exam_id})
        if not exam_data:
            logger.error(f"Exam not found: {exam_id}")
            raise HTTPException(status_code=404, detail="Exam not found")

        solutions_data = extract_answers_from_pdf(file)
        logger.info(f"Expected {exam_data['numQuestions']} solutions, got {len(solutions_data)}")
        
        if len(solutions_data) != exam_data['numQuestions']:
            expected_questions = set(range(1, exam_data['numQuestions'] + 1))
            actual_questions = set(solution.question for solution in solutions_data)
            missing_questions = expected_questions - actual_questions
            extra_questions = actual_questions - expected_questions
            
            error_msg = f"Expected {exam_data['numQuestions']} solutions, got {len(solutions_data)}"
            if missing_questions:
                error_msg += f". Missing questions: {sorted(missing_questions)}"
            if extra_questions:
                error_msg += f". Extra questions: {sorted(extra_questions)}"
                
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        await db_ops.delete_one('solutions', {"examId": exam_id})
        logger.info(f"Deleted existing solutions for exam_id: {exam_id}")

        solutions_dict = [solution.dict() for solution in solutions_data]

        new_solution = Solution(
            examId=exam_id,
            solutions=solutions_dict
        )
        await db_ops.insert_one('solutions', new_solution.dict())
        logger.info(f"Saved new solution for exam_id: {exam_id}")

        await db_ops.update_one(
            'exams',
            {"examId": exam_id},
            {"solutionUploaded": True}
        )
        logger.info(f"Updated exam {exam_id} with solutionUploaded: True")

        return {
            "message": "Solution uploaded successfully",
            "solutionCount": len(solutions_data)
        }

    except HTTPException as e:
        logger.error(f"HTTP error during solution upload: {e.detail}")
        raise e
    except Exception as error:
        logger.error(f"Solution upload error: {str(error)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload solution: {str(error)}")

@router.post("/{exam_id}/manual")
async def manual_solution(exam_id: str, request: ManualSolutionRequest, db_ops=Depends(get_database)):
    try:
        if request.examId != exam_id:
            logger.error(f"Exam ID mismatch: path {exam_id}, body {request.examId}")
            raise HTTPException(status_code=400, detail="Exam ID mismatch")

        logger.info(f"Saving manual solution for exam_id: {exam_id}, solutions count: {len(request.solutions)}")

        exam_data = await db_ops.find_one('exams', {"examId": exam_id})
        if not exam_data:
            logger.error(f"Exam not found: {exam_id}")
            raise HTTPException(status_code=404, detail="Exam not found")

        solutions_data = request.solutions
        logger.info(f"Expected {exam_data['numQuestions']} solutions, got {len(solutions_data)}")
        
        if len(solutions_data) != exam_data['numQuestions']:
            expected_questions = set(range(1, exam_data['numQuestions'] + 1))
            actual_questions = set(solution.question for solution in solutions_data)
            missing_questions = expected_questions - actual_questions
            extra_questions = actual_questions - expected_questions
            
            error_msg = f"Expected {exam_data['numQuestions']} solutions, got {len(solutions_data)}"
            if missing_questions:
                error_msg += f". Missing questions: {sorted(missing_questions)}"
            if extra_questions:
                error_msg += f". Extra questions: {sorted(extra_questions)}"
                
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        # Sort solutions by question number
        solutions_data.sort(key=lambda x: x.question)

        await db_ops.delete_one('solutions', {"examId": exam_id})
        logger.info(f"Deleted existing solutions for exam_id: {exam_id}")

        solutions_dict = [solution.dict() for solution in solutions_data]

        new_solution = Solution(
            examId=exam_id,
            solutions=solutions_dict
        )
        await db_ops.insert_one('solutions', new_solution.dict())
        logger.info(f"Saved new solution for exam_id: {exam_id}")

        await db_ops.update_one(
            'exams',
            {"examId": exam_id},
            {"solutionUploaded": True}
        )
        logger.info(f"Updated exam {exam_id} with solutionUploaded: True")

        return {
            "message": "Solution saved successfully",
            "solutionCount": len(solutions_data)
        }

    except HTTPException as e:
        logger.error(f"HTTP error during manual solution save: {e.detail}")
        raise e
    except Exception as error:
        logger.error(f"Manual solution save error: {str(error)}")
        raise HTTPException(status_code=500, detail=f"Failed to save solution: {str(error)}")

@router.get("/{exam_id}")
async def get_solution(exam_id: str, db_ops=Depends(get_database)):
    try:
        solution_doc = await db_ops.find_one('solutions', {"examId": exam_id})
        if not solution_doc:
            logger.error(f"Solution not found for exam_id: {exam_id}")
            raise HTTPException(status_code=404, detail="Solution not found")

        logger.info(f"Retrieved solution for exam_id: {exam_id}")
        return solution_doc

    except Exception as error:
        logger.error(f"Get solution error: {str(error)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch solution: {str(error)}")