import sqlite3
import asyncio
import aiosqlite
from contextlib import asynccontextmanager
from typing import Dict, List, Any, Optional
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SQLiteDatabase:
    def __init__(self, db_path: str = "omr_database.db"):
        self.db_path = db_path
        self.connection = None
    
    async def connect(self):
        """Initialize database connection and create tables"""
        try:
            self.connection = await aiosqlite.connect(self.db_path)
            await self.create_tables()
            logger.info(f"SQLite database connected successfully at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to SQLite database: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            logger.info("SQLite database connection closed")
    
    async def create_tables(self):
        """Create all necessary tables"""
        tables = [
            # Exams table
            """
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                examId TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                wing TEXT NOT NULL,
                course TEXT NOT NULL,
                module TEXT NOT NULL,
                sponsorDS TEXT NOT NULL,
                dateTime TEXT NOT NULL,
                time TEXT NOT NULL,
                numQuestions INTEGER NOT NULL,
                marksPerMcq INTEGER DEFAULT 1,
                passingPercentage INTEGER DEFAULT 60,
                instructions TEXT,
                settings TEXT DEFAULT '{}',
                studentsUploaded BOOLEAN DEFAULT FALSE,
                solutionUploaded BOOLEAN DEFAULT FALSE,
                createdAt TEXT NOT NULL,
                createdBy TEXT DEFAULT 'System'
            )
            """,
            
            # Students table
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                examId TEXT NOT NULL,
                name TEXT NOT NULL,
                lockerNumber TEXT NOT NULL,
                rank TEXT NOT NULL,
                copyNumber TEXT NOT NULL,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (examId) REFERENCES exams (examId)
            )
            """,
            
            # Solutions table
            """
            CREATE TABLE IF NOT EXISTS solutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                examId TEXT NOT NULL,
                solutions TEXT NOT NULL,
                uploadedAt TEXT NOT NULL,
                FOREIGN KEY (examId) REFERENCES exams (examId)
            )
            """,
            
            # Results table
            """
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                examId TEXT NOT NULL,
                studentId TEXT NOT NULL,
                studentName TEXT,
                examName TEXT NOT NULL,
                responses TEXT NOT NULL,
                score INTEGER NOT NULL,
                totalMarks INTEGER NOT NULL,
                percentage REAL NOT NULL,
                passFailStatus TEXT NOT NULL,
                correctAnswers INTEGER NOT NULL,
                incorrectAnswers INTEGER NOT NULL,
                blankAnswers INTEGER NOT NULL,
                multipleMarks INTEGER NOT NULL,
                sponsorDS TEXT,
                course TEXT,
                wing TEXT,
                module TEXT,
                studentInfo TEXT,
                processedAt TEXT NOT NULL,
                FOREIGN KEY (examId) REFERENCES exams (examId)
            )
            """,
            
            # Reports table
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                examId TEXT NOT NULL,
                reportType TEXT NOT NULL,
                data TEXT NOT NULL,
                generatedBy TEXT NOT NULL,
                generatedAt TEXT NOT NULL,
                FOREIGN KEY (examId) REFERENCES exams (examId)
            )
            """,
            
            # Responses table
            """
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                examId TEXT NOT NULL,
                studentId TEXT NOT NULL,
                responses TEXT NOT NULL,
                score INTEGER NOT NULL,
                accuracy REAL NOT NULL,
                correctAnswers INTEGER NOT NULL,
                incorrectAnswers INTEGER NOT NULL,
                blankAnswers INTEGER NOT NULL,
                multipleMarks INTEGER NOT NULL,
                processingMetadata TEXT NOT NULL,
                processedAt TEXT NOT NULL,
                FOREIGN KEY (examId) REFERENCES exams (examId)
            )
            """
        ]
        
        for table_sql in tables:
            await self.connection.execute(table_sql)
        
        await self.connection.commit()
        logger.info("All tables created successfully")

# Database helper functions for CRUD operations
class DatabaseOperations:
    def __init__(self, db: SQLiteDatabase):
        self.db = db
    
    # Generic CRUD operations
    async def insert_one(self, table: str, data: Dict[str, Any]) -> int:
        """Insert a single record and return the row ID"""
        # Convert complex objects to JSON strings
        processed_data = {}
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                processed_data[key] = json.dumps(value)
            elif isinstance(value, datetime):
                processed_data[key] = value.isoformat()
            else:
                processed_data[key] = value
        
        columns = ', '.join(processed_data.keys())
        placeholders = ', '.join(['?' for _ in processed_data])
        values = list(processed_data.values())
        
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        cursor = await self.db.connection.execute(query, values)
        await self.db.connection.commit()
        return cursor.lastrowid
    
    async def find_one(self, table: str, filter_dict: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Find a single record"""
        query = f"SELECT * FROM {table}"
        values = []
        
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(f"{key} = ?")
                values.append(value)
            query += f" WHERE {' AND '.join(conditions)}"
        
        query += " LIMIT 1"
        
        cursor = await self.db.connection.execute(query, values)
        row = await cursor.fetchone()
        
        if row:
            columns = [description[0] for description in cursor.description]
            result = dict(zip(columns, row))
            return self._process_result(result)
        return None
    
    async def find_many(self, table: str, filter_dict: Dict[str, Any] = None, 
                       sort_by: str = None, sort_order: str = "ASC", 
                       limit: int = None, skip: int = None) -> List[Dict[str, Any]]:
        """Find multiple records"""
        query = f"SELECT * FROM {table}"
        values = []
        
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(f"{key} = ?")
                values.append(value)
            query += f" WHERE {' AND '.join(conditions)}"
        
        if sort_by:
            query += f" ORDER BY {sort_by} {sort_order}"
        
        if limit:
            query += f" LIMIT {limit}"
            if skip:
                query += f" OFFSET {skip}"
        
        cursor = await self.db.connection.execute(query, values)
        rows = await cursor.fetchall()
        
        if rows:
            columns = [description[0] for description in cursor.description]
            results = [dict(zip(columns, row)) for row in rows]
            return [self._process_result(result) for result in results]
        return []
    
    async def update_one(self, table: str, filter_dict: Dict[str, Any], 
                        update_data: Dict[str, Any]) -> int:
        """Update a single record and return the number of affected rows"""
        # Process update data
        processed_data = {}
        for key, value in update_data.items():
            if isinstance(value, (dict, list)):
                processed_data[key] = json.dumps(value)
            elif isinstance(value, datetime):
                processed_data[key] = value.isoformat()
            else:
                processed_data[key] = value
        
        set_clauses = []
        values = []
        
        for key, value in processed_data.items():
            set_clauses.append(f"{key} = ?")
            values.append(value)
        
        conditions = []
        for key, value in filter_dict.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        
        query = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {' AND '.join(conditions)}"
        
        cursor = await self.db.connection.execute(query, values)
        await self.db.connection.commit()
        return cursor.rowcount
    
    async def delete_one(self, table: str, filter_dict: Dict[str, Any]) -> int:
        """Delete a single record and return the number of affected rows"""
        conditions = []
        values = []
        
        for key, value in filter_dict.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        
        query = f"DELETE FROM {table} WHERE {' AND '.join(conditions)}"
        
        cursor = await self.db.connection.execute(query, values)
        await self.db.connection.commit()
        return cursor.rowcount
    
    async def delete_many(self, table: str, filter_dict: Dict[str, Any]) -> int:
        """Delete multiple records and return the number of affected rows"""
        conditions = []
        values = []
        
        for key, value in filter_dict.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        
        query = f"DELETE FROM {table} WHERE {' AND '.join(conditions)}"
        
        cursor = await self.db.connection.execute(query, values)
        await self.db.connection.commit()
        return cursor.rowcount
    
    async def count_documents(self, table: str, filter_dict: Dict[str, Any] = None) -> int:
        """Count documents in a table"""
        query = f"SELECT COUNT(*) FROM {table}"
        values = []
        
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(f"{key} = ?")
                values.append(value)
            query += f" WHERE {' AND '.join(conditions)}"
        
        cursor = await self.db.connection.execute(query, values)
        result = await cursor.fetchone()
        return result[0] if result else 0
    
    def _process_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process result to convert JSON strings back to objects and add _id field"""
        processed = {}
        
        for key, value in result.items():
            if key == 'id':
                processed['_id'] = str(value)  # Convert to string to match MongoDB format
                processed[key] = value
            elif key in ['settings', 'solutions', 'responses', 'studentInfo', 'processingMetadata', 'data']:
                try:
                    processed[key] = json.loads(value) if value else {}
                except (json.JSONDecodeError, TypeError):
                    processed[key] = value
            elif key in ['studentsUploaded', 'solutionUploaded']:
                processed[key] = bool(value)
            else:
                processed[key] = value
        
        return processed

# Global database instance
database = SQLiteDatabase()
db_operations = DatabaseOperations(database)