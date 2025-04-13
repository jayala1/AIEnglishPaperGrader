from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import io
import re
from weasyprint import HTML as WPHTML

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.1:8b-instruct-q5_K_M"

def call_ollama(prompt):
    try:
        data = {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        r = requests.post(OLLAMA_URL, json=data, timeout=120)
        r.raise_for_status()
        return r.json().get('message', {}).get('content', '')
    except Exception as e:
        print("Ollama API error:", e)
        raise RuntimeError("Error contacting AI model")

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<title>English Paper Grader</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
mark { background-color: #ffff66; }
.teacher-annotation { background-color: #99d0ff; cursor: pointer; }
#annotate-menu {
  position: absolute; display: none; background: #fff; border: 1px solid #ccc; padding: 5px; z-index: 1000;
}
#annotated {
  white-space: pre-wrap; word-break: break-word; background:#f9f9f9;
  padding:1rem; border:1px solid #ddd; max-height:70vh; overflow-y:auto;
}
#original {
  white-space: pre-wrap; word-break: break-word; background:#f9f9f9;
  padding:1rem; border:1px solid #ddd; max-height:70vh; overflow-y:auto;
}
textarea { width: 100%; }
#spinner { display:none; }
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
      <div class="mb-3">
        <label class="form-label">Upload Essay</label>
        <input type="file" name="file" class="form-control" accept=".txt" required>
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
      <textarea id="comment-input" placeholder="Add comment..." style="width:150px; height:50px;"></textarea><br>
      <button onclick="saveAnnotation()" class="btn btn-sm btn-primary">Save</button>
      <button onclick="hideMenu()" class="btn btn-sm btn-secondary">Cancel</button>
    </div>
  </div>
</div>
</div>
<script>
const presets = {
  AP: {criteria:["grammar","vocabulary","coherence","structure"], weights:{grammar:25,vocabulary:25,coherence:25,structure:25}},
  IELTS: {criteria:["grammar","vocabulary","coherence","spelling"], weights:{grammar:30,vocabulary:25,coherence:25,spelling:20}},
  TOEFL: {criteria:["grammar","vocabulary","coherence"], weights:{grammar:35,vocabulary:30,coherence:35}}
};
document.getElementById('preset').onchange=()=>{
  const p=presets[document.getElementById('preset').value]; if(!p)return;
  document.querySelectorAll('input[name="criteria"]').forEach(cb=>cb.checked=p.criteria.includes(cb.value));
  Object.entries(p.weights).forEach(([k,v])=>{
    let el=document.querySelector('input[name=weight_'+k+']'); if(el)el.value=v;
  });
  updateWeightVisibility();
};

function flattenTeacherComments() {
  document.querySelectorAll('.teacher-annotation').forEach(span => {
    if(span.dataset.flattened) return;
    const comment = span.getAttribute('title');
    if (!comment) return;
    const inline = document.createElement('mark');
    inline.textContent = `[Teacher: ${comment}]`;
    span.parentNode.insertBefore(inline, span.nextSibling);
    span.dataset.flattened = "true";
  });
}

document.querySelector('#upload-form').addEventListener('submit', async e => {
  e.preventDefault();
  const data = new FormData(e.target);
  const criteriaChecked = [];
  e.target.querySelectorAll('input[name="criteria"]:checked').forEach(cb => criteriaChecked.push(cb.value));
  data.set('criteria', criteriaChecked.join(', '));
  data.set('tone', document.getElementById('tone').value);
  data.set('strictness', document.getElementById('strictness').value);
  data.set('grade_level', document.getElementById('grade_level').value);
  ['grammar','vocabulary','coherence','spelling','structure'].forEach(k=>{
    const el = e.target.querySelector(`input[name=weight_${k}]`);
    if(el) data.set('weight_'+k, el.value);
  });
  document.getElementById('spinner').style.display='inline-block';
  const resp = await fetch('/analyze', { method: 'POST', body: data });
  const result = await resp.json();
  document.getElementById('spinner').style.display='none';
  document.getElementById('original').textContent = result.original;
  document.getElementById('annotated').innerHTML = result.annotated;
  document.getElementById('grade').value = result.grade;
});

function downloadPDF() {
  const annotated = document.getElementById('annotated').innerHTML;
  const grade = document.getElementById('grade').value;
  const formData = new FormData();
  formData.append('annotated_html', annotated);
  formData.append('grade', grade);
  fetch('/download', {
    method: 'POST',
    body: formData
  })
  .then(res => res.blob())
  .then(blob => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'graded_essay.pdf';
    a.click();
    URL.revokeObjectURL(url);
  });
}

function updateWeightVisibility() {
  document.querySelectorAll('input[name="criteria"]').forEach(cb=>{
    const container = document.querySelector('.weight-input[data-criteria="'+cb.value+'"]');
    if(container){container.style.display=cb.checked?'block':'none';}
  });
  updateWeightTotal();
}
function updateWeightTotal() {
  let total=0;
  document.querySelectorAll('#weights-container input[type=number]').forEach(i=>{
    if(i.closest('.weight-input').style.display!=='none'){ total+=parseInt(i.value)||0; }
  });
  document.getElementById('weight-total').innerText=total;
}
document.querySelectorAll('input[name="criteria"]').forEach(cb => cb.onchange=updateWeightVisibility);
document.querySelectorAll('#weights-container input[type=number]').forEach(i => i.oninput=updateWeightTotal);
window.onload=updateWeightVisibility;

let selectedRange=null;
function hideMenu(){document.getElementById('annotate-menu').style.display='none';}
function saveAnnotation(){
  const comment=document.getElementById('comment-input').value.trim();
  if(!selectedRange)return hideMenu();
  const span=document.createElement('span');
  span.className='teacher-annotation';
  span.title=comment;
  span.appendChild(selectedRange.extractContents());
  selectedRange.insertNode(span);
  hideMenu();
}
document.getElementById('annotated').addEventListener('mouseup',e=>{
  const sel=window.getSelection();
  if(sel.isCollapsed)return;
  selectedRange=sel.getRangeAt(0).cloneRange();
  const menu=document.getElementById('annotate-menu');
  menu.style.display='block';
  document.getElementById('comment-input').value='';
  menu.style.left=e.pageX+'px';
  menu.style.top=e.pageY+'px';
});
</script>
</body>
</html>
"""

@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
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
    try:
        content = (await file.read()).decode("utf-8")
    except:
        raise HTTPException(status_code=400, detail="Invalid upload")

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
Please follow:
1. DO NOT rewrite or paraphrase the essay.
2. For every correction or suggestion, immediately add an inline comment enclosed exactly like this: [Comment: your correction here]
3. Do NOT provide any corrections outside of inline comments.
4. After annotations, output rubric scores (0-100) with each score on a new line in the format:
   Grammar: XX  
   Vocabulary: XX  
   Coherence: XX  
   Spelling: XX  
   Structure: XX
5. Then, output the overall weighted grade in the format: 
Grade: YY/100
6. Finally, include three sections exactly in this order (each on a new line with the header followed by the content):
   Strengths:
   Weaknesses:
   Suggestions for improvement:
Now, grade this essay:
{content}
"""

    try:
        ai_response = call_ollama(prompt)
    except:
        return JSONResponse({"error": "AI model unavailable"}, status_code=503)

    annotated = re.sub(
        r'(\[\s*[Cc]omment\s*:\s*.*?\])',
        r'<mark>\1</mark>',
        ai_response,
        flags=re.DOTALL
    )

    # Parse rubric scores
    scores = {}
    for crit in ["Grammar", "Vocabulary", "Coherence", "Spelling", "Structure"]:
        m = re.search(rf'\b{crit}\b\s*[:\-]?\s*(\d{{1,3}})', ai_response, re.I)
        scores[crit.lower()] = m.group(1) if m else "N/A"

    grade_match = re.search(r'\bGrade\b\s*[:\-]?\s*(\d{1,3})\s*/\s*100', ai_response, re.I)
    grade = grade_match.group(1) if grade_match else "N/A"

    return JSONResponse(content={
        "original": content,
        "annotated": annotated,
        "grade": grade
    })

@app.post("/download")
async def download_pdf(annotated_html: str = Form(...), grade: str = Form(...)):
    html_content = f"""
<html>
<head>
<style>
body {{ font-family: Georgia, serif; margin: 2em; }}
h1 {{ text-align: center; color: #336699; }}
h2 {{ margin-top:1em; }}
mark {{ background-color: #ffff66; }}
.teacher-annotation {{ background-color: #99d0ff; }}
div.essay {{ border:1px solid #ccc; padding:15px; border-radius:8px; }}
</style>
</head>
<body>
<h1>Graded Essay Report</h1>
<h2>Grade: {grade}/100</h2>
<div class="essay">{annotated_html}</div>
</body>
</html>
"""
    pdf_bytes = WPHTML(string=html_content).write_pdf()
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename=graded_essay.pdf"})
