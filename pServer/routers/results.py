from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import List, Optional
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from openpyxl import Workbook
from models.result import ResultCreate, ResultResponse
from datetime import datetime

router = APIRouter()

def get_database():
    from main import app
    return app.state.db_operations

@router.post("/save")
async def save_result(result: ResultCreate, db_ops=Depends(get_database)):
    try:
        # Validate input data
        result_data = result.dict()
        result_data["processedAt"] = datetime.utcnow()

        # Check if result already exists
        existing_result = await db_ops.find_one('results', {
            "examId": result.examId,
            "studentId": result.studentId
        })

        if existing_result:
            # Update existing result
            await db_ops.update_one(
                'results',
                {"examId": result.examId, "studentId": result.studentId},
                result_data
            )
        else:
            # Create new result
            await db_ops.insert_one('results', result_data)

        return {"message": "Result saved successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Invalid input data: {str(ve)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save result: {str(e)}")

@router.get("/all", response_model=List[dict])
async def get_all_results(db_ops=Depends(get_database)):
    try:
        results = await db_ops.find_many('results', sort_by="processedAt", sort_order="DESC")
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch results")

@router.post("/publish")
async def publish_results(request_data: dict, db_ops=Depends(get_database)):
    try:
        exam_id = request_data.get("examId")
        exam_name = request_data.get("examName")
        results = request_data.get("results", [])

        for result in results:
            result_data = {
                "examId": exam_id,
                "examName": exam_name,
                "studentId": result.get("studentId"),
                "studentName": result.get("studentName"),
                "responses": result.get("responses", []),
                "score": result.get("score", 0),
                "totalMarks": result.get("totalMarks", 0),
                "percentage": result.get("percentage", 0.0),
                "passFailStatus": result.get("passFailStatus", "Fail"),
                "correctAnswers": result.get("correctAnswers", 0),
                "incorrectAnswers": result.get("incorrectAnswers", 0),
                "blankAnswers": result.get("blankAnswers", 0),
                "multipleMarks": result.get("multipleMarks", 0),
                "sponsorDS": result.get("sponsorDS"),
                "course": result.get("course"),
                "wing": result.get("wing"),
                "module": result.get("module"),
                "studentInfo": result.get("studentInfo"),
                "processedAt": datetime.utcnow()
            }

            existing_result = await db_ops.find_one('results', {
                "examId": exam_id,
                "studentId": result.get("studentId")
            })

            if existing_result:
                await db_ops.update_one(
                    'results',
                    {"examId": exam_id, "studentId": result.get("studentId")},
                    result_data
                )
            else:
                await db_ops.insert_one('results', result_data)

        return {"message": f"Successfully published {len(results)} results"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish results: {str(e)}")

@router.post("/download-all-pdf")
async def download_all_pdf(request_data: dict):
    try:
        results = request_data.get("results", [])
        filters = request_data.get("filters", {})

        # Create PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Title
        p.setFont("Helvetica-Bold", 20)
        p.drawCentredString(width/2, height-50, "OMR Results Report")
        p.setFont("Helvetica", 14)
        p.drawCentredString(width/2, height-80, f"Generated: {datetime.now().strftime('%Y-%m-%d')}")

        # Statistics
        total_students = len(results)
        passed_students = len([r for r in results if r.get('passFailStatus') == 'Pass'])
        failed_students = total_students - passed_students
        avg_percentage = sum(r.get('percentage', 0) for r in results) / total_students if total_students > 0 else 0

        y_pos = height - 150
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y_pos, "Summary Statistics")
        p.setFont("Helvetica", 12)
        y_pos -= 20
        p.drawString(50, y_pos, f"Total Students: {total_students}")
        y_pos -= 15
        p.drawString(50, y_pos, f"Passed: {passed_students} ({(passed_students/total_students*100):.1f}%)")
        y_pos -= 15
        p.drawString(50, y_pos, f"Failed: {failed_students} ({(failed_students/total_students*100):.1f}%)")
        y_pos -= 15
        p.drawString(50, y_pos, f"Average Score: {avg_percentage:.1f}%")

        # Results table
        y_pos -= 40
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y_pos, "Individual Results")
        
        # Table headers
        y_pos -= 30
        p.setFont("Helvetica", 7)  # Reduced font size for headers
        p.drawString(50, y_pos, "Student Name")
        p.drawString(150, y_pos, "ID")  # Adjusted x-coordinate
        p.drawString(230, y_pos, "Locker")  # Adjusted x-coordinate
        p.drawString(280, y_pos, "Rank")  # Adjusted x-coordinate
        p.drawString(340, y_pos, "Exam")  # Adjusted x-coordinate
        p.drawString(420, y_pos, "Score")  # Adjusted x-coordinate
        p.drawString(470, y_pos, "%")  # Adjusted x-coordinate
        p.drawString(500, y_pos, "Result")  # Adjusted x-coordinate

        # Table rows
        y_pos -= 20
        p.setFont("Helvetica", 6)  # Reduced font size for rows
        for result in results[:40]:  # Limit to 40 results per page
            if y_pos < 100:  # Start new page if needed
                p.showPage()
                y_pos = height - 50
                # Redraw headers on new page
                p.setFont("Helvetica", 7)
                p.drawString(50, y_pos, "Student Name")
                p.drawString(150, y_pos, "ID")
                p.drawString(230, y_pos, "Locker")
                p.drawString(280, y_pos, "Rank")
                p.drawString(340, y_pos, "Exam")
                p.drawString(420, y_pos, "Score")
                p.drawString(470, y_pos, "%")
                p.drawString(500, y_pos, "Result")
                y_pos -= 20
                p.setFont("Helvetica", 6)

            # Remove truncation to allow full text
            student_name = str(result.get('studentName', ''))
            student_id = str(result.get('studentId', ''))
            locker = str(result.get('studentInfo', {}).get('lockerNumber', ''))
            rank = str(result.get('studentInfo', {}).get('rank', ''))
            exam_name = str(result.get('examName', ''))

            p.drawString(50, y_pos, student_name)
            p.drawString(150, y_pos, student_id)
            p.drawString(230, y_pos, locker)
            p.drawString(280, y_pos, rank)
            p.drawString(340, y_pos, exam_name)
            p.drawString(420, y_pos, f"{result.get('score', 0)}/{result.get('totalMarks', 0)}")
            p.drawString(470, y_pos, f"{result.get('percentage', 0):.1f}%")
            
            # Color code the result
            if result.get('passFailStatus') == 'Pass':
                p.setFillColorRGB(0, 0.5, 0)  # Green
            else:
                p.setFillColorRGB(1, 0, 0)  # Red
            p.drawString(500, y_pos, str(result.get('passFailStatus', '')))
            p.setFillColorRGB(0, 0, 0)  # Reset to black
            
            y_pos -= 15

        p.save()
        buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(buffer.read()),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=OMR_Results_Report.pdf"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate PDF")

@router.post("/download-all-pdf")
async def download_all_pdf(request_data: dict):
    try:
        results = request_data.get("results", [])
        filters = request_data.get("filters", {})

        # Create PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Title
        p.setFont("Helvetica-Bold", 20)
        p.drawCentredString(width/2, height-50, "OMR Results Report")
        p.setFont("Helvetica", 14)
        p.drawCentredString(width/2, height-80, f"Generated: {datetime.now().strftime('%Y-%m-%d')}")

        # Statistics
        total_students = len(results)
        passed_students = len([r for r in results if r.get('passFailStatus') == 'Pass'])
        failed_students = total_students - passed_students
        avg_percentage = sum(r.get('percentage', 0) for r in results) / total_students if total_students > 0 else 0

        y_pos = height - 150
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y_pos, "Summary Statistics")
        p.setFont("Helvetica", 12)
        y_pos -= 20
        p.drawString(50, y_pos, f"Total Students: {total_students}")
        y_pos -= 15
        p.drawString(50, y_pos, f"Passed: {passed_students} ({(passed_students/total_students*100):.1f}%)")
        y_pos -= 15
        p.drawString(50, y_pos, f"Failed: {failed_students} ({(failed_students/total_students*100):.1f}%)")
        y_pos -= 15
        p.drawString(50, y_pos, f"Average Score: {avg_percentage:.1f}%")

        # Results table
        y_pos -= 40
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y_pos, "Individual Results")
        
        # Table headers
        y_pos -= 30
        p.setFont("Helvetica", 7)  # Reduced font size for headers
        p.drawString(50, y_pos, "Student Name")
        p.drawString(130, y_pos, "ID")  # Adjusted x-coordinate
        p.drawString(210, y_pos, "Locker")  # Adjusted x-coordinate
        p.drawString(260, y_pos, "Rank")  # Adjusted x-coordinate
        p.drawString(310, y_pos, "Exam")  # Adjusted x-coordinate
        p.drawString(390, y_pos, "Score")  # Adjusted x-coordinate
        p.drawString(440, y_pos, "%")  # Adjusted x-coordinate
        p.drawString(470, y_pos, "Result")  # Adjusted x-coordinate

        # Table rows
        y_pos -= 20
        p.setFont("Helvetica", 6)  # Reduced font size for rows
        for result in results[:40]:  # Limit to 40 results per page
            if y_pos < 100:  # Start new page if needed
                p.showPage()
                y_pos = height - 50
                # Redraw headers on new page
                p.setFont("Helvetica", 7)
                p.drawString(50, y_pos, "Student Name")
                p.drawString(130, y_pos, "ID")
                p.drawString(210, y_pos, "Locker")
                p.drawString(260, y_pos, "Rank")
                p.drawString(310, y_pos, "Exam")
                p.drawString(390, y_pos, "Score")
                p.drawString(440, y_pos, "%")
                p.drawString(470, y_pos, "Result")
                y_pos -= 20
                p.setFont("Helvetica", 6)

            # Truncate long text
            student_name = str(result.get('studentName', ''))[:12]  # Limit to 12 chars
            student_id = str(result.get('studentId', ''))[:12]  # Limit to 12 chars
            locker = str(result.get('studentInfo', {}).get('lockerNumber', ''))[:8]
            rank = str(result.get('studentInfo', {}).get('rank', ''))[:8]
            exam_name = str(result.get('examName', ''))[:10]

            p.drawString(50, y_pos, student_name)
            p.drawString(130, y_pos, student_id)
            p.drawString(210, y_pos, locker)
            p.drawString(260, y_pos, rank)
            p.drawString(310, y_pos, exam_name)
            p.drawString(390, y_pos, f"{result.get('score', 0)}/{result.get('totalMarks', 0)}")
            p.drawString(440, y_pos, f"{result.get('percentage', 0):.1f}%")
            
            # Color code the result
            if result.get('passFailStatus') == 'Pass':
                p.setFillColorRGB(0, 0.5, 0)  # Green
            else:
                p.setFillColorRGB(1, 0, 0)  # Red
            p.drawString(470, y_pos, str(result.get('passFailStatus', '')))
            p.setFillColorRGB(0, 0, 0)  # Reset to black
            
            y_pos -= 15

        p.save()
        buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(buffer.read()),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=OMR_Results_Report.pdf"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate PDF")

@router.get("/exam/{exam_id}")
async def get_exam_results(
    exam_id: str,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "processedAt",
    order: str = "desc",
    db_ops=Depends(get_database)
):
    try:
        # Verify exam exists
        exam = await db_ops.find_one('exams', {"examId": exam_id})
        if not exam:
            raise HTTPException(status_code=404, detail="Exam not found")

        sort_order_str = "DESC" if order == "desc" else "ASC"
        skip_count = (page - 1) * limit

        responses = await db_ops.find_many(
            'results', 
            {"examId": exam_id}, 
            sort_by=sort_by, 
            sort_order=sort_order_str, 
            limit=limit, 
            skip=skip_count
        )

        total = await db_ops.count_documents('results', {"examId": exam_id})

        # Calculate aggregate statistics
        stats = await calculate_exam_stats(exam_id, db_ops)

        return {
            "responses": responses,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            },
            "statistics": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch results")

async def calculate_exam_stats(exam_id: str, db_ops):
    responses = await db_ops.find_many('results', {"examId": exam_id})
    
    exam = await db_ops.find_one('exams', {"examId": exam_id})

    if not responses:
        return {
            "totalStudents": 0,
            "averageScore": 0,
            "highestScore": 0,
            "lowestScore": 0,
            "passingRate": 0,
            "scoreDistribution": [],
            "questionAnalysis": []
        }

    scores = [r["score"] for r in responses]
    total_students = len(responses)
    average_score = sum(scores) / total_students if total_students > 0 else 0
    highest_score = max(scores) if scores else 0
    lowest_score = min(scores) if scores else 0
    
    passing_score = exam.get("settings", {}).get("passingScore", 60)
    passing_count = len([s for s in scores if (s / exam["numQuestions"]) * 100 >= passing_score])
    passing_rate = (passing_count / total_students) * 100 if total_students > 0 else 0

    # Score distribution
    ranges = [
        {"min": 0, "max": 20, "label": "0-20%"},
        {"min": 21, "max": 40, "label": "21-40%"},
        {"min": 41, "max": 60, "label": "41-60%"},
        {"min": 61, "max": 80, "label": "61-80%"},
        {"min": 81, "max": 100, "label": "81-100%"}
    ]

    score_distribution = []
    for range_item in ranges:
        count = len([s for s in scores if range_item["min"] <= (s / exam["numQuestions"]) * 100 <= range_item["max"]])
        score_distribution.append({
            "range": range_item["label"],
            "count": count,
            "percentage": (count / total_students) * 100 if total_students > 0 else 0
        })

    return {
        "totalStudents": total_students,
        "averageScore": round(average_score, 2),
        "highestScore": highest_score,
        "lowestScore": lowest_score,
        "passingRate": round(passing_rate, 2),
        "scoreDistribution": score_distribution,
        "questionAnalysis": []
    }
