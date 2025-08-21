from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class SolutionItem(BaseModel):
    question: int
    answer: str = Field(..., pattern="^[A-E]$")

class Solution(BaseModel):
    examId: str
    solutions: List[SolutionItem]
    uploadedAt: datetime = Field(default_factory=datetime.now)