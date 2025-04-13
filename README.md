🚀 Features
Upload .txt essays for analysis

Customize tone, strictness, grade level, and rubric weights

Inline feedback comments from AI

Rubric-based scoring and overall grade

Teacher-mode annotation tools

Download annotated PDF report

🛠 Requirements
Python 3.9+

Ollama (running locally)

Ollama-compatible model (e.g., llama3.1:8b-instruct-q5_K_M)

WeasyPrint (for generating PDF reports)

🔧 Installation
Download to a folder
open terminal or cmd for that folder location
create python enviorment
pip install fastapi requests weasyprint uvicorn python-multipart

▶️ Run the App
uvicorn main6:app --reload
