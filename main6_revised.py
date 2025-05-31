# main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import requests
import io
import re
from weasyprint import HTML as WPHTML
import json # Added for JSONDecodeError

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Removed hardcoded OLLAMA_URL and OLLAMA_MODEL

# Modified call_ollama to accept url and model
def call_ollama(prompt, ollama_base_url, model_name):
    """Calls the Ollama chat API."""
    ollama_api_url = f"{ollama_base_url.rstrip('/')}/api/chat"
    try:
        data = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        print(f"--- Calling Ollama API ({model_name}) at {ollama_api_url} ---") # Console log
        r = requests.post(ollama_api_url, json=data, timeout=120)
        r.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        response_data = r.json()
        print("--- Ollama API Response Received ---") # Console log
        return response_data.get('message', {}).get('content', '')
    except requests.exceptions.ConnectionError as e:
        print(f"Ollama API Connection Error: {e}") # Console log specific error
        raise RuntimeError(f"Cannot connect to Ollama server at {ollama_base_url}. Is it running?")
    except requests.exceptions.Timeout as e:
        print(f"Ollama API Timeout Error: {e}") # Console log specific error
        raise RuntimeError("Request to Ollama server timed out.")
    except requests.exceptions.HTTPError as e:
        print(f"Ollama API HTTP Error: {e.response.status_code} - {e.response.text}") # Console log specific error
        # Try to parse error message from Ollama if possible
        error_detail = f"HTTP {e.response.status_code}"
        try:
            error_json = e.response.json()
            if 'error' in error_json:
                error_detail = error_json['error']
        except json.JSONDecodeError:
            pass # Keep the basic HTTP error if JSON parsing fails
        raise RuntimeError(f"Ollama API error: {error_detail}")
    except Exception as e:
        print(f"Ollama API Generic Error: {e}") # Console log other errors
        raise RuntimeError(f"An unexpected error occurred contacting the AI model: {e}")

# New endpoint to fetch models
@app.post("/get_models", response_class=JSONResponse)
async def get_models(ollama_url: str = Form(...)):
    """Fetches available models from the specified Ollama server."""
    tags_url = f"{ollama_url.rstrip('/')}/api/tags"
    print(f"--- Fetching models from {tags_url} ---") # Console log
    try:
        response = requests.get(tags_url, timeout=10) # Add timeout
        response.raise_for_status() # Check for HTTP errors
        data = response.json()
        models = sorted([m['name'] for m in data.get('models', [])]) # Sort models alphabetically
        print(f"--- Successfully fetched models: {models} ---") # Console log
        return {"models": models}
    except requests.exceptions.ConnectionError as e:
        print(f"Error fetching models (ConnectionError): {e}") # Console log specific error
        raise HTTPException(status_code=503, detail=f"Could not connect to Ollama server at {ollama_url}")
    except requests.exceptions.Timeout as e:
        print(f"Error fetching models (Timeout): {e}") # Console log specific error
        raise HTTPException(status_code=504, detail="Request to Ollama server timed out while fetching models.")
    except requests.exceptions.RequestException as e: # Catch other requests errors (like invalid URL, HTTPError)
        error_detail = f"Failed to fetch models from {ollama_url}"
        status_code = 500 # Default status code
        if e.response is not None:
            status_code = e.response.status_code
            error_detail += f" (HTTP {status_code})"
            # Try to get more specific error from Ollama response
            try:
                error_json = e.response.json()
                if 'error' in error_json:
                    error_detail = error_json['error'] # Use Ollama's error message
            except json.JSONDecodeError:
                 error_detail += f": {e.response.text[:100]}" # Include start of text if not JSON

        print(f"Error fetching models (RequestException): {e}") # Console log specific error
        raise HTTPException(status_code=status_code, detail=error_detail)
    except Exception as e: # Catch any other non-requests exceptions
         print(f"Unexpected error fetching models: {e}") # Console log
         raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.get("/", response_class=HTMLResponse)
def index():
    # Added Ollama URL input, Fetch Models button, and Model dropdown
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<title>English Paper Grader</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
mark {
  background-color: #e6e6fa; /* Light lavender for AI comments */
  padding: 0.1em 0.3em;      /* Padding around AI comments */
  border-radius: 3px;       /* Rounded corners for AI comments */
}
.teacher-manual-annotation {
  background-color: #add8e6; /* Light blue background */
  border-bottom: 2px dashed #00008b; /* Dark blue dashed underline */
  cursor: help;
  padding: 0.1em 0.2em;
  border-radius: 3px;
}
#annotate-menu {
  position: absolute;
  display: none;
  background-color: #f8f9fa; /* Softer background */
  border: 1px solid #ced4da; /* Subtle border */
  border-radius: 0.25rem; /* Bootstrap default border-radius */
  box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075); /* Bootstrap default shadow */
  padding: 0.5rem; /* More spacious padding */
  z-index: 1000;
}
#annotate-menu textarea#comment-input { /* Style the textarea within the menu */
  min-width: 180px; /* Flexible width */
  min-height: 60px; /* Flexible height */
  border: 1px solid #ced4da;
  border-radius: 0.25rem;
  padding: 0.375rem 0.75rem;
  margin-bottom: 0.5rem; /* Space before buttons */
  width: 100%; /* Make it take full width of its parent */
  box-sizing: border-box; /* Ensure padding and border don't increase overall size */
}
#annotate-menu button.btn-secondary {
  margin-left: 0.25rem; /* Space between buttons */
}
#annotated {
  white-space: pre-wrap; word-break: break-word; background:#f9f9f9;
  padding:1rem; border:1px solid #ddd; max-height:70vh; overflow-y:auto;
  line-height: 1.6; /* Increased line height for readability */
}
#original {
  white-space: pre-wrap; word-break: break-word; background:#f9f9f9;
  padding:1rem; border:1px solid #ddd; max-height:70vh; overflow-y:auto;
}
textarea { width: 100%; }
#spinner { display:none; }
.input-group-text { min-width: 120px; } /* Align labels */
</style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-light bg-light mb-2">
  <div class="container-fluid">
    <span class="navbar-brand mb-0 h1">English Paper Grader</span>
    <button onclick="downloadPDF()" class="btn btn-outline-primary">Download PDF</button>
  </div>
</nav>
<div class="container-fluid">
<div class="row">
  <!-- Left pane -->
  <div class="col-md-3 mb-3">
    <form id="upload-form" enctype="multipart/form-data" class="mb-3">

      <!-- Ollama Server Configuration -->
      <div class="card mb-3 p-2">
        <label class="form-label fw-bold">Ollama Server</label>
        <div class="input-group mb-2">
           <span class="input-group-text">URL</span>
           <input type="text" id="ollama-url" name="ollama_url" class="form-control" value="http://localhost:11434" placeholder="e.g., http://192.168.1.100:11434" required>
        </div>
         <div class="input-group mb-2">
            <span class="input-group-text">Model</span>
            <select id="ollama-model" name="ollama_model" class="form-select" required disabled>
              <option value="">-- Enter URL & Fetch --</option>
            </select>
         </div>
        <button type="button" id="fetch-models-btn" class="btn btn-secondary btn-sm w-100">Fetch Models</button>
         <div id="model-fetch-error" class="text-danger mt-1" style="font-size: 0.8em;"></div>
      </div>
      <!-- End Ollama Server Configuration -->

      <!-- Preset Management Card -->
      <div class="card mb-3 p-2">
        <label class="form-label fw-bold">Preset Management</label>
        <div class="input-group mb-2">
          <input type="text" id="preset-name" class="form-control" placeholder="Preset Name">
        </div>
        <button type="button" id="save-preset-btn" class="btn btn-success btn-sm w-100 mb-2">Save Current Settings as Preset</button>
        <div class="input-group mb-2">
          <select id="load-preset-select" class="form-select">
            <option value="">-- Load Preset --</option>
          </select>
        </div>
        <button type="button" id="delete-preset-btn" class="btn btn-danger btn-sm w-100 mb-2">Delete Selected Preset</button>
        <div id="preset-feedback" class="text-muted mt-1" style="font-size: 0.8em;"></div>
      </div>
      <!-- End Preset Management Card -->

      <div class="mb-3">
        <label class="form-label">Upload Essay (.txt file)</label>
        <input type="file" name="file" id="file-upload" class="form-control" accept=".txt">
      </div>
      <div class="text-center my-2"><strong>OR</strong></div>
      <div class="mb-3">
        <label class="form-label">Paste Essay Text</label>
        <textarea name="text_input" id="text-input" class="form-control" rows="10" placeholder="Paste your essay text directly here..."></textarea>
      </div>
      <div class="mb-3">
        <label class="form-label">AI Tone</label>
        <select id="tone" name="tone" class="form-select">
          <option value="formal">Formal</option>
          <option value="encouraging">Encouraging</option>
          <option value="detailed">Detailed</option>
          <option value="concise">Concise</option>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Strictness Level</label>
        <select id="strictness" name="strictness" class="form-select">
          <option value="lenient">Lenient</option>
          <option value="balanced" selected>Balanced</option>
          <option value="strict">Strict</option>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Rubric Preset</label>
        <select id="preset" class="form-select">
          <option value="">-- Select preset --</option>
          <option value="AP">AP English</option>
          <option value="IELTS">IELTS</option>
          <option value="TOEFL">TOEFL</option>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Grade Level</label>
        <select name="grade_level" id="grade_level" class="form-select">
          <option value="Elementary">Elementary</option>
          <option value="Middle School">Middle School</option>
          <option value="9th Grade">9th Grade</option>
          <option value="10th Grade">10th Grade</option>
          <option value="11th Grade">11th Grade</option>
          <option value="12th Grade">12th Grade</option>
          <option value="College Freshman">College Freshman</option>
          <option value="College Sophomore">College Sophomore</option>
        </select>
      </div>
      <div class="card mb-3 p-2">
        <label class="form-label">Focus criteria</label>
        <div class="form-check"><input class="form-check-input" type="checkbox" name="criteria" value="grammar" checked><label class="form-check-label">Grammar</label></div>
        <div class="form-check"><input class="form-check-input" type="checkbox" name="criteria" value="vocabulary" checked><label class="form-check-label">Vocabulary</label></div>
        <div class="form-check"><input class="form-check-input" type="checkbox" name="criteria" value="coherence" checked><label class="form-check-label">Coherence</label></div>
        <div class="form-check"><input class="form-check-input" type="checkbox" name="criteria" value="spelling" checked><label class="form-check-label">Spelling</label></div>
        <div class="form-check"><input class="form-check-input" type="checkbox" name="criteria" value="structure"><label class="form-check-label">Structure</label></div>
      </div>
      <div class="card mb-3 p-2">
        <label class="form-label">Rubric Weights (Total <span id="weight-total">100</span>%)</label>
        <div id="weights-container">
          <div class="weight-input" data-criteria="grammar">
            Grammar: <input type="number" name="weight_grammar" value="25" min="0" max="100" class="form-control">
          </div>
          <div class="weight-input" data-criteria="vocabulary">
            Vocabulary: <input type="number" name="weight_vocabulary" value="25" min="0" max="100" class="form-control">
          </div>
          <div class="weight-input" data-criteria="coherence">
            Coherence: <input type="number" name="weight_coherence" value="25" min="0" max="100" class="form-control">
          </div>
          <div class="weight-input" data-criteria="spelling">
            Spelling: <input type="number" name="weight_spelling" value="25" min="0" max="100" class="form-control">
          </div>
          <div class="weight-input" data-criteria="structure" style="display:none;">
            Structure: <input type="number" name="weight_structure" value="0" min="0" max="100" class="form-control">
          </div>
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label">Instructions</label>
        <textarea name="instructions" rows="4" class="form-control" placeholder="e.g., Focus on argument strength and tone"></textarea>
      </div>
      <button type="submit" class="btn btn-primary w-100 mb-2">Analyze</button>
      <div class="text-center">
        <div id="spinner" class="spinner-border text-primary" role="status"></div>
      </div>
       <div id="analyze-error" class="text-danger mt-1" style="font-size: 0.8em;"></div>
    </form>
    <h5>Original Essay</h5>
    <pre id="original"></pre>
  </div>
  <!-- Middle pane -->
  <div class="col-md-9 mb-3">
    <h5>AI Suggested Grade</h5>
    <input id="grade" type="text" class="form-control mb-2">
    <h5>Annotated Essay (Editable)</h5>
    <button onclick="flattenTeacherComments()" class="btn btn-outline-primary mb-2">Embed Teacher Comments Inline</button>
    <div id="annotated" contenteditable="true"></div>
    <div id="annotate-menu">
      <textarea id="comment-input" placeholder="Add comment..."></textarea>
      <div> <!-- Wrapper for buttons to sit below textarea -->
        <button onclick="saveAnnotation()" class="btn btn-sm btn-primary">Save</button>
        <button onclick="hideMenu()" class="btn btn-sm btn-secondary">Cancel</button>
      </div>
    </div>
  </div>
</div>
</div>
<script src="/static/js/scripts.js"></script>
</body>
</html>
"""

# Modify /analyze endpoint to accept ollama_url and ollama_model
@app.post("/analyze")
async def analyze(
    file: UploadFile = File(None), # Changed to None
    text_input: str = Form(None),  # Added
    ollama_url: str = Form(...),         # Added
    ollama_model: str = Form(...),       # Added
    criteria: str = Form(""),
    instructions: str = Form(""),
    tone: str = Form("formal"),
    strictness: str = Form("balanced"),
    grade_level: str = Form(""),
    weight_grammar: int = Form(25),
    weight_vocabulary: int = Form(25),
    weight_coherence: int = Form(25),
    weight_spelling: int = Form(25),
    weight_structure: int = Form(0)
):
    content = None
    if text_input:
        content = text_input
        print("--- Received text input from textarea ---") # Console log
    elif file:
        try:
            file_content_bytes = await file.read()
            content = file_content_bytes.decode("utf-8")
            print(f"--- Received file upload: {file.filename} ---") # Console log
        except Exception as e:
            print(f"Error reading uploaded file: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid file upload or encoding: {e}")
    else:
        # This case should ideally be caught by frontend validation, but good to have backend check
        print("Error: Neither file nor text_input provided.") # Console log
        raise HTTPException(status_code=400, detail="No essay content provided. Please upload a file or paste text.")

    if not content: # Should be redundant if logic above is correct, but as a safeguard
         print("Error: Content is empty after checks.") # Console log
         raise HTTPException(status_code=400, detail="Essay content is empty.")

    # Basic validation for weights (optional but good practice)
    total_weight = weight_grammar + weight_vocabulary + weight_coherence + weight_spelling + weight_structure
    if total_weight != 100:
         print(f"Warning: Rubric weights do not sum to 100 (Sum: {total_weight})") # Console log
         # Decide if you want to raise an error or just proceed
         # raise HTTPException(status_code=400, detail=f"Rubric weights must sum to 100, current sum is {total_weight}")


    rubric = f"""
Grading Rubric and Weights:
- Grammar (sentence structure, punctuation, subject-verb agreement): {weight_grammar}%
- Vocabulary (word choice, variety, appropriateness): {weight_vocabulary}%
- Coherence (logical flow, transitions, clarity): {weight_coherence}%
- Spelling (correct spelling): {weight_spelling}%
- Structure (organization: intro, body, conclusion): {weight_structure}%
"""
    prompt = f"""
You are an experienced English teacher grading a {grade_level} student's essay.
Your tone should be {tone}. Be {strictness}.
{rubric}
Focus on these criteria: {criteria}.
{instructions if instructions else ''}
Please follow these instructions VERY carefully:
1. DO NOT rewrite or paraphrase the essay content itself. Only add comments.
2. For every correction, suggestion, or observation you make about the text, you MUST immediately insert an inline comment enclosed exactly like this: [Comment: your comment here]. Place the comment directly after the text it refers to. Do not add comments anywhere else.
3. Do NOT provide any feedback, summaries, corrections, or suggestions outside of these specific inline [Comment: ...] annotations.
4. After processing the entire essay and adding all inline comments, output the rubric scores (scale 0-100) with each score on a new line in the exact format:
   Grammar: XX
   Vocabulary: XX
   Coherence: XX
   Spelling: XX
   Structure: XX
5. Immediately after the rubric scores, output the overall weighted grade on a new line in the exact format:
   Grade: YY/100
6. Finally, include three sections exactly in this order (each starting on a new line with the header followed by the content on the next line(s)):
   Strengths:
   [List strengths here]
   Weaknesses:
   [List weaknesses here]
   Suggestions for improvement:
   [List suggestions here]

Now, grade this essay strictly following all the rules above:
--- ESSAY START ---
{content}
--- ESSAY END ---
"""
    print("--- Preparing to call Ollama for analysis ---") # Console log
    try:
        # Pass ollama_url and ollama_model to the call function
        ai_response = call_ollama(prompt, ollama_url, ollama_model)
        if not ai_response: # Handle empty response from Ollama
             print("Error: Received empty response from Ollama.") # Console log
             raise RuntimeError("AI model returned an empty response.")

        print("--- AI Response Received, Processing... ---") # Console log
        # print(f"Raw AI Response:\n{ai_response}\n--- End Raw AI Response ---") # Optional: log raw response for debugging

    except RuntimeError as e:
         # Error already printed in call_ollama, just raise HTTP exception
         print(f"Error during Ollama call in /analyze: {e}") # Console log specific context
         raise HTTPException(status_code=503, detail=str(e)) # Send error detail to frontend
    except Exception as e:
         # Catch any other unexpected errors during the call
         print(f"Unexpected error calling Ollama in /analyze: {e}") # Console log
         raise HTTPException(status_code=500, detail=f"An unexpected error occurred during AI analysis: {e}")


    # --- Process AI Response ---
    # Isolate the annotated text part (everything before the first score line)
    # This helps prevent mark tags being added to the scores/summary sections
    score_keywords = ["Grammar:", "Vocabulary:", "Coherence:", "Spelling:", "Structure:", "Grade:"]
    end_of_annotation_index = -1
    for keyword in score_keywords:
        try:
            index = ai_response.index(keyword)
            if end_of_annotation_index == -1 or index < end_of_annotation_index:
                end_of_annotation_index = index
        except ValueError:
            continue # Keyword not found

    if end_of_annotation_index != -1:
        annotated_text_part = ai_response[:end_of_annotation_index]
        summary_part = ai_response[end_of_annotation_index:]
    else:
        # Fallback if scores aren't found (maybe the model didn't follow instructions)
        print("Warning: Could not reliably find score markers in AI response. Applying annotations to the whole response.") # Console log
        annotated_text_part = ai_response
        summary_part = "" # Assume no summary if markers are missing

    # Add <mark> tags ONLY to the annotated text part
    annotated_with_marks = re.sub(
        r'(\[Comment:\s*.*?\])', # Made regex slightly more specific
        r'<mark>\1</mark>',
        annotated_text_part,
        flags=re.IGNORECASE | re.DOTALL # Added IGNORECASE
    )
    # Combine the marked text with the rest of the response
    full_annotated_response = annotated_with_marks + summary_part

    # Parse rubric scores (search within the whole response)
    scores = {}
    for crit in ["Grammar", "Vocabulary", "Coherence", "Spelling", "Structure"]:
        # Regex: Look for the criterion name, optional colon, optional space, digits
        m = re.search(rf'^\s*{crit}\s*:\s*(\d{{1,3}})\s*$', ai_response, re.IGNORECASE | re.MULTILINE)
        scores[crit.lower()] = m.group(1) if m else "N/A"

    # Parse grade (search within the whole response)
    # Regex: Look for "Grade", optional colon, optional space, digits, slash, 100
    grade_match = re.search(r'^\s*Grade\s*:\s*(\d{1,3})\s*/\s*100\s*$', ai_response, re.IGNORECASE | re.MULTILINE)
    grade = grade_match.group(1) if grade_match else "N/A"

    print(f"--- Analysis Complete. Grade: {grade}, Scores: {scores} ---") # Console log

    # Return only the necessary parts to the frontend
    # The full_annotated_response now includes the marked comments AND the summary/scores
    return JSONResponse(content={
        "original": content,
        "annotated": full_annotated_response, # Send the combined content
        "grade": grade
        # You could optionally parse and return scores/strengths/weaknesses separately if needed by the frontend
        # "scores": scores,
    })


@app.post("/download")
async def download_pdf(annotated_html: str = Form(...), grade: str = Form(...)):
    # Basic cleaning: remove potentially harmful script tags just in case
    safe_html = re.sub(r'<script.*?>.*?</script>', '', annotated_html, flags=re.IGNORECASE | re.DOTALL)

    html_content = f"""
<html>
<head>
<meta charset="UTF-8">
<title>Graded Essay Report</title>
<style>
body {{ font-family: 'Times New Roman', Times, serif; margin: 2em; line-height: 1.5; }}
h1 {{ text-align: center; color: #2c3e50; border-bottom: 1px solid #bdc3c7; padding-bottom: 10px; }}
h2 {{ margin-top: 1.5em; color: #34495e; }}
.teacher-manual-annotation {{ /* Styles the original text that was annotated by teacher */
  background-color: #d6eaf8; /* Light blue background for the annotated text itself */
  border-bottom: 1px dotted #2980b9; /* Dotted underline for the annotated text */
  padding: 0.05em;
}}
mark {{ /* For AI comments */
  background-color: #fcf3cf; /* Light yellow for AI comments */
  color: #7d6608;
  padding: 0.1em 0.2em;
  border-radius: 3px;
}}
mark.manual-comment-embed {{ /* For the teacher's embedded comment text */
  background-color: #d1eafb;
  color: #154360;
  font-style: italic;
  padding: 0.1em 0.2em;
  border-radius: 3px;
  margin-left: 2px; /* Add some space after the original text */
}}
div.essay {{
    border: 1px solid #ccc;
    padding: 20px;
    border-radius: 5px;
    background-color: #fdfefe;
    margin-top: 1em;
    white-space: pre-wrap; /* Preserve whitespace and line breaks */
    word-wrap: break-word; /* Break long words */
}}
/* Ensure summary sections are formatted reasonably */
pre {{ white-space: pre-wrap; word-wrap: break-word; }}
</style>
</head>
<body>
<h1>Graded Essay Report</h1>
<h2>Overall Grade: {grade}/100</h2>
<h2>Annotated Essay & Feedback</h2>
<div class="essay">{safe_html}</div>
</body>
</html>
"""
    print("--- Generating PDF ---") # Console log
    try:
        pdf_bytes = WPHTML(string=html_content).write_pdf()
        print("--- PDF Generation Successful ---") # Console log
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                                 headers={"Content-Disposition": f"attachment; filename=graded_essay.pdf"})
    except Exception as e:
        print(f"Error generating PDF: {e}") # Console log error
        # Consider what to return here. Maybe an HTML error page or JSON error?
        # Returning JSON is often easier for frontend JS to handle.
        return JSONResponse(
            status_code=500,
            content={"detail": f"Failed to generate PDF: {e}"}
        )

# Add this at the end if you want to run directly with uvicorn
if __name__ == "__main__":
    import uvicorn
    print("--- Starting FastAPI Server ---")
    # Listen on all interfaces to be accessible from other devices on the network
    uvicorn.run(app, host="0.0.0.0", port=8000)
    print("--- FastAPI Server Stopped ---")
