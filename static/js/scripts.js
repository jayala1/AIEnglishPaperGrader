const presets = {
  AP: {criteria:["grammar","vocabulary","coherence","structure"], weights:{grammar:25,vocabulary:25,coherence:25,structure:25}},
  IELTS: {criteria:["grammar","vocabulary","coherence","spelling"], weights:{grammar:30,vocabulary:25,coherence:25,spelling:20}},
  TOEFL: {criteria:["grammar","vocabulary","coherence"], weights:{grammar:35,vocabulary:30,coherence:35}}
};

const ollamaUrlInput = document.getElementById('ollama-url');
const ollamaModelSelect = document.getElementById('ollama-model');
const fetchModelsBtn = document.getElementById('fetch-models-btn');
const modelFetchErrorDiv = document.getElementById('model-fetch-error');
const analyzeErrorDiv = document.getElementById('analyze-error');
const spinner = document.getElementById('spinner');
const uploadForm = document.getElementById('upload-form');

// Data structure to hold analysis results for PDF generation
let currentAnalysisData = {
    original: '',
    annotated: '',
    grade: '',
    detailed_scores: {},
    strengths: '',
    weaknesses: '',
    suggestions: ''
};

// Preset Management Elements
const presetNameInput = document.getElementById('preset-name');
const savePresetBtn = document.getElementById('save-preset-btn');
const loadPresetSelect = document.getElementById('load-preset-select');
const deletePresetBtn = document.getElementById('delete-preset-btn');
const presetFeedbackDiv = document.getElementById('preset-feedback');


// --- Fetch Ollama Models ---
fetchModelsBtn.addEventListener('click', async () => {
  const url = ollamaUrlInput.value.trim();
  console.log("Fetch Models clicked. URL:", url); // Log URL

  if (!url) {
    alert('Please enter the Ollama server URL.');
    return;
  }
  ollamaModelSelect.disabled = true;
  ollamaModelSelect.innerHTML = '<option value="">Fetching...</option>';
  modelFetchErrorDiv.textContent = '';
  fetchModelsBtn.disabled = true;

  const formData = new FormData();
  formData.append('ollama_url', url);
  console.log("FormData prepared:", formData.get('ollama_url')); // Log FormData content

  try {
    const response = await fetch('/get_models', {
      method: 'POST',
      body: formData
    });
    console.log("Response status:", response.status); // Log response status

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `HTTP error ${response.status} - No JSON body` })); // Catch if .json() fails
      console.error('Error response from server:', errorData); // Log error data
      throw new Error(errorData.detail || `HTTP error ${response.status}`);
    }
    const result = await response.json();
    console.log("Successfully fetched models (raw result):", result); // Log raw result

    ollamaModelSelect.innerHTML = '';
    if (result.models && result.models.length > 0) {
      result.models.forEach(model => {
        console.log("Adding model to dropdown:", model); // Log each model being added
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        if (model.includes('llama3') || model.includes('mistral') || model.includes('phi3')) {
            option.selected = true;
        }
        ollamaModelSelect.appendChild(option);
      });
      ollamaModelSelect.disabled = false;
      if (!ollamaModelSelect.value && ollamaModelSelect.options.length > 0) {
          ollamaModelSelect.selectedIndex = 0;
      }
    } else {
      console.log("No models found in result:", result); // Log if no models array
      ollamaModelSelect.innerHTML = '<option value="">No models found</option>';
    }
  } catch (error) {
    console.error('Error fetching models (catch block):', error.message); // Log error in catch
    modelFetchErrorDiv.textContent = `Error: ${error.message}`;
    ollamaModelSelect.innerHTML = '<option value="">Error fetching</option>';
  } finally {
      fetchModelsBtn.disabled = false;
      console.log("Fetch models process finished."); // Log end of process
  }
});

// Trigger fetch models on initial load if URL is present (optional)
// if (ollamaUrlInput.value) {
//    fetchModelsBtn.click();
// }

// const presets = { ... }; // Assuming presets is defined above as per original file structure

const presetDropdown = document.getElementById('preset');
if (presetDropdown) {
  presetDropdown.onchange = () => {
    const pValue = presetDropdown.value;
    console.log("Rubric preset changed. Selected value:", pValue);

    // Check if presets variable is available
    if (typeof presets === 'undefined') {
      console.error("Error: 'presets' constant is not defined or accessible.");
      return;
    }
    console.log("Available presets object:", presets);


    const p = presets[pValue];
    console.log("Retrieved preset object:", p);

    if (!p) {
      console.log("No preset found for value:", pValue, ". Exiting preset change handler.");
      // If pValue is empty (like "-- Select preset --"), we might not want to do anything further.
      // Or, we might want to clear/reset fields. For now, just return if no specific preset.
      if (pValue === "") {
          // Optionally, reset fields to default or clear them
          // For example, uncheck all criteria and set weights to 0 or default
          document.querySelectorAll('input[name="criteria"]').forEach(cb => {
              cb.checked = false; // Default to unchecked
          });
          Object.keys(presets.AP.weights).forEach(k => { // Assuming AP has all possible weight keys
              let el = document.querySelector('input[name=weight_' + k + ']');
              if (el) el.value = 0; // Default to 0
          });
          console.log("Selected empty preset, fields potentially reset/cleared.");
      }
      updateWeightVisibility(); // Still call this to hide/show relevant weight inputs
      return;
    }

    console.log("Applying preset:", pValue);
    document.querySelectorAll('input[name="criteria"]').forEach(cb => {
      const isChecked = p.criteria.includes(cb.value);
      cb.checked = isChecked;
      console.log("Criteria checkbox:", cb.value, "set to checked:", isChecked);
    });

    Object.entries(p.weights).forEach(([k, v]) => {
      let el = document.querySelector('input[name=weight_' + k + ']');
      if (el) {
        el.value = v;
        console.log("Weight input:", 'weight_' + k, "set to value:", v);
      } else {
        console.warn("Weight input not found for:", 'weight_' + k);
      }
    });

    // Also ensure all weight fields NOT in this preset are set to 0 and hidden appropriately by updateWeightVisibility
    const allPossibleWeightKeys = ['grammar', 'vocabulary', 'coherence', 'spelling', 'structure'];
    allPossibleWeightKeys.forEach(key => {
        if (!p.weights.hasOwnProperty(key)) {
            let el = document.querySelector('input[name=weight_' + key + ']');
            if (el) {
                el.value = 0; // Set weight to 0 if not in preset
                console.log("Weight input (not in preset):", 'weight_' + key, "set to value: 0");
            }
        }
    });


    console.log("Before calling updateWeightVisibility for preset change.");
    updateWeightVisibility();
    console.log("After calling updateWeightVisibility for preset change.");
  };
} else {
  console.error("Error: Preset dropdown with ID 'preset' not found.");
}

function flattenTeacherComments() {
  document.querySelectorAll('.teacher-manual-annotation').forEach(span => {
    if(span.dataset.flattened) return;
    const comment = span.getAttribute('title');
    if (!comment) return;
    const inline = document.createElement('mark');
    inline.className = 'manual-comment-embed';
    inline.textContent = ` [Manual Annotation: ${comment}]`;
    span.parentNode.insertBefore(inline, span.nextSibling);
    span.dataset.flattened = "true";
  });
}

// --- Analyze Essay ---
uploadForm.addEventListener('submit', async e => {
  e.preventDefault();
  analyzeErrorDiv.textContent = ''; // Clear previous errors

  // Basic validation
  if (!ollamaModelSelect.value) {
      analyzeErrorDiv.textContent = 'Please fetch models and select one.';
      return;
  }

  const fileInput = e.target.querySelector('input[name="file"]');
  const textInput = e.target.querySelector('textarea[name="text_input"]');
  const file = fileInput.files[0];
  const textContent = textInput.value.trim();

  if (!file && !textContent) {
      analyzeErrorDiv.textContent = 'Please upload an essay file OR paste text directly.';
      spinner.style.display='none'; // Hide spinner if shown
      return;
  }
  if (file && textContent) {
      analyzeErrorDiv.textContent = 'Please provide either a file OR pasted text, not both.';
      spinner.style.display='none'; // Hide spinner if shown
      return;
  }

  const data = new FormData(e.target); // Gets all form fields including ollama_url and ollama_model

  // Consolidate criteria
  const criteriaChecked = [];
  e.target.querySelectorAll('input[name="criteria"]:checked').forEach(cb => criteriaChecked.push(cb.value));
  data.set('criteria', criteriaChecked.join(', '));

  // Ensure weights are included (FormData might not pick them up correctly if display:none)
  ['grammar','vocabulary','coherence','spelling','structure'].forEach(k=>{
    const el = e.target.querySelector(`input[name=weight_${k}]`);
    if(el) data.set('weight_'+k, el.value); // FormData should handle this, but being explicit is safer
  });


  spinner.style.display='inline-block';
  document.getElementById('original').textContent = ''; // Clear previous results
  document.getElementById('annotated').innerHTML = '';
  document.getElementById('grade').value = '';

  try {
    const resp = await fetch('/analyze', { method: 'POST', body: data });
     if (!resp.ok) {
        const errorData = await resp.json();
        throw new Error(`Analysis failed: ${errorData.detail || errorData.error || `HTTP ${resp.status}`}`);
     }
    const result = await resp.json();

    if (result.error) { // Handle application-level errors returned in JSON
        throw new Error(result.error);
    }

    document.getElementById('original').textContent = result.original;
    document.getElementById('annotated').innerHTML = result.annotated;
    document.getElementById('grade').value = result.grade;

    // Populate currentAnalysisData
    currentAnalysisData.original = result.original;
    currentAnalysisData.annotated = result.annotated;
    currentAnalysisData.grade = result.grade;
    currentAnalysisData.detailed_scores = result.detailed_scores || {}; // Ensure it's an object
    currentAnalysisData.strengths = result.strengths || 'Not provided';
    currentAnalysisData.weaknesses = result.weaknesses || 'Not provided';
    currentAnalysisData.suggestions = result.suggestions || 'Not provided';

    console.log("Updated currentAnalysisData:", currentAnalysisData); // For verification

  } catch (error) {
      console.error("Analysis Error:", error);
      analyzeErrorDiv.textContent = `Error: ${error.message}`;
  } finally {
      spinner.style.display='none';
  }
});

// --- Download PDF ---
function downloadPDF() {
  // Retrieve data from currentAnalysisData
  const {
    original,
    annotated, // This is the innerHTML of the annotated div, effectively annotated_html
    grade,
    detailed_scores,
    strengths,
    weaknesses,
    suggestions
  } = currentAnalysisData;

  // The 'annotated' variable from currentAnalysisData already contains the HTML content.
  // The 'grade' variable from currentAnalysisData contains the grade.
  // No need to re-fetch from DOM if currentAnalysisData is up-to-date.
  // const annotated_html_from_dom = document.getElementById('annotated').innerHTML;
  // const grade_from_dom = document.getElementById('grade').value;

  const formData = new FormData();
  formData.append('original_essay', original);
  formData.append('annotated_html', annotated); // Using data from currentAnalysisData
  formData.append('grade', grade); // Using data from currentAnalysisData
  formData.append('detailed_scores', JSON.stringify(detailed_scores));
  formData.append('strengths', strengths);
  formData.append('weaknesses', weaknesses);
  formData.append('suggestions', suggestions);

  // Optional: Log FormData entries for verification
  console.log("FormData for PDF download:");
  for(var pair of formData.entries()) {
    console.log(pair[0]+ ': '+ pair[1].substring(0,100) + (pair[1].length > 100 ? "..." : "")); // Log first 100 chars
  }

  fetch('/download', {
    method: 'POST',
    body: formData
  })
  .then(res => {
    if (!res.ok) {
      throw new Error(`Download failed: HTTP ${res.status}`);
    }
    return res.blob();
   })
  .then(blob => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'graded_essay.pdf';
    document.body.appendChild(a); // Required for Firefox
    a.click();
    a.remove(); // Clean up
    URL.revokeObjectURL(url);
  })
  .catch(error => {
      console.error("PDF Download Error:", error);
      alert(`Could not download PDF: ${error.message}`); // Inform user
   });
}

// --- UI Helper Functions ---
// Add logs to updateWeightVisibility and updateWeightTotal
function updateWeightVisibility() {
  console.log("updateWeightVisibility called.");
  document.querySelectorAll('input[name="criteria"]').forEach(cb => {
    const container = document.querySelector('.weight-input[data-criteria="' + cb.value + '"]');
    if (container) {
      const shouldDisplay = cb.checked ? 'block' : 'none';
      container.style.display = shouldDisplay;
      console.log("Weight container for", cb.value, "display set to:", shouldDisplay);
    } else {
      console.warn("Weight container not found for criteria:", cb.value);
    }
  });
  updateWeightTotal();
}

function updateWeightTotal() {
  console.log("updateWeightTotal called.");
  let total = 0;
  document.querySelectorAll('#weights-container input[type=number]').forEach(i => {
    if (i.closest('.weight-input').style.display !== 'none') {
      total += parseInt(i.value) || 0;
      console.log("Adding to total: input", i.name, "value:", i.value, "Current total:", total);
    }
  });
  const totalEl = document.getElementById('weight-total');
  totalEl.innerText = total;
  console.log("Final weight total:", total);
  if (total !== 100) {
    totalEl.style.color = 'red';
    totalEl.style.fontWeight = 'bold';
  } else {
    totalEl.style.color = 'inherit';
    totalEl.style.fontWeight = 'normal';
  }
}

document.querySelectorAll('input[name="criteria"]').forEach(cb => cb.onchange=updateWeightVisibility);
document.querySelectorAll('#weights-container input[type=number]').forEach(i => i.oninput=updateWeightTotal);

window.onload = function() {
    updateWeightVisibility();
    loadPresetList(); // Add this call
};

// --- Preset Management Functions ---
function savePreset() {
  const presetName = presetNameInput.value.trim();
  if (!presetName) {
    presetFeedbackDiv.textContent = 'Please enter a preset name.';
    presetFeedbackDiv.className = 'text-danger mt-1';
    return;
  }

  const criteriaChecked = [];
  document.querySelectorAll('input[name="criteria"]:checked').forEach(cb => criteriaChecked.push(cb.value));

  const settings = {
    ollamaUrl: ollamaUrlInput.value,
    ollamaModel: ollamaModelSelect.value,
    tone: document.getElementById('tone').value,
    strictness: document.getElementById('strictness').value,
    rubricPreset: document.getElementById('preset').value, // Rubric preset (AP, IELTS)
    gradeLevel: document.getElementById('grade_level').value,
    criteria: criteriaChecked,
    weight_grammar: document.querySelector('input[name="weight_grammar"]').value,
    weight_vocabulary: document.querySelector('input[name="weight_vocabulary"]').value,
    weight_coherence: document.querySelector('input[name="weight_coherence"]').value,
    weight_spelling: document.querySelector('input[name="weight_spelling"]').value,
    weight_structure: document.querySelector('input[name="weight_structure"]').value,
    instructions: document.querySelector('textarea[name="instructions"]').value
  };

  let presets = JSON.parse(localStorage.getItem('gradingPresets')) || {};
  presets[presetName] = settings;
  localStorage.setItem('gradingPresets', JSON.stringify(presets));

  presetFeedbackDiv.textContent = `Preset "${presetName}" saved!`;
  presetFeedbackDiv.className = 'text-success mt-1';
  loadPresetList();
  presetNameInput.value = '';
}

function loadPresetList() {
  let presets = JSON.parse(localStorage.getItem('gradingPresets')) || {};
  loadPresetSelect.innerHTML = '<option value="">-- Load Preset --</option>'; // Clear existing options

  for (const name in presets) {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    loadPresetSelect.appendChild(option);
  }
}

function applyPreset() {
  const selectedPresetName = loadPresetSelect.value;
  if (!selectedPresetName) return;

  let presets = JSON.parse(localStorage.getItem('gradingPresets')) || {};
  const settings = presets[selectedPresetName];

  if (!settings) {
    presetFeedbackDiv.textContent = `Preset "${selectedPresetName}" not found.`;
    presetFeedbackDiv.className = 'text-danger mt-1';
    return;
  }

  ollamaUrlInput.value = settings.ollamaUrl || 'http://localhost:11434'; // Default if not set

  // Set model value. If the model isn't in the list, this will select nothing,
  // or user can manually fetch.
  ollamaModelSelect.value = settings.ollamaModel || "";


  document.getElementById('tone').value = settings.tone;
  document.getElementById('strictness').value = settings.strictness;
  document.getElementById('preset').value = settings.rubricPreset;
  // Manually trigger change for rubric preset to update criteria/weights based on its own logic first
  document.getElementById('preset').dispatchEvent(new Event('change'));

  document.getElementById('grade_level').value = settings.gradeLevel;

  // Uncheck all criteria first
  document.querySelectorAll('input[name="criteria"]').forEach(cb => cb.checked = false);
  // Check saved criteria
  if (settings.criteria && Array.isArray(settings.criteria)) {
    settings.criteria.forEach(criterionValue => {
      const cb = document.querySelector(`input[name="criteria"][value="${criterionValue}"]`);
      if (cb) cb.checked = true;
    });
  }

  // Apply weights
  document.querySelector('input[name="weight_grammar"]').value = settings.weight_grammar || 0;
  document.querySelector('input[name="weight_vocabulary"]').value = settings.weight_vocabulary || 0;
  document.querySelector('input[name="weight_coherence"]').value = settings.weight_coherence || 0;
  document.querySelector('input[name="weight_spelling"]').value = settings.weight_spelling || 0;
  document.querySelector('input[name="weight_structure"]').value = settings.weight_structure || 0;

  document.querySelector('textarea[name="instructions"]').value = settings.instructions || '';

  updateWeightVisibility(); // This also calls updateWeightTotal()

  presetFeedbackDiv.textContent = `Preset "${selectedPresetName}" applied.`;
  presetFeedbackDiv.className = 'text-info mt-1';

  // Optional: If Ollama URL or model changed, inform user or auto-fetch.
  // For now, just setting values. User can click "Fetch Models" if needed.
  // if (settings.ollamaUrl !== ollamaUrlInput.value || settings.ollamaModel !== ollamaModelSelect.value) {
  //    fetchModelsBtn.click(); // Or provide a message
  // }
}

function deletePreset() {
  const selectedPresetName = loadPresetSelect.value;
  if (!selectedPresetName) {
    presetFeedbackDiv.textContent = 'Please select a preset to delete.';
    presetFeedbackDiv.className = 'text-danger mt-1';
    return;
  }

  let presets = JSON.parse(localStorage.getItem('gradingPresets')) || {};
  if (presets[selectedPresetName]) {
    delete presets[selectedPresetName];
    localStorage.setItem('gradingPresets', JSON.stringify(presets));
    presetFeedbackDiv.textContent = `Preset "${selectedPresetName}" deleted.`;
    presetFeedbackDiv.className = 'text-success mt-1';
    loadPresetList();
  } else {
    presetFeedbackDiv.textContent = `Preset "${selectedPresetName}" not found.`;
    presetFeedbackDiv.className = 'text-danger mt-1';
  }
}

// Event Listeners for Preset Management
savePresetBtn.addEventListener('click', savePreset);
loadPresetSelect.addEventListener('change', applyPreset);
deletePresetBtn.addEventListener('click', deletePreset);

// --- Annotation Menu Logic ---
let selectedRange=null;
function hideMenu(){document.getElementById('annotate-menu').style.display='none';}
function saveAnnotation(){
  const comment=document.getElementById('comment-input').value.trim();
  if(!selectedRange || !comment) return hideMenu(); // Also hide if comment is empty
  const span=document.createElement('span');
  span.className='teacher-manual-annotation';
  span.title=comment; // Store comment in title attribute
  span.style.cursor = 'help'; // Indicate hover provides info

  try {
    // This is the most robust way to wrap content, handling partial selections etc.
    span.appendChild(selectedRange.extractContents());
    selectedRange.insertNode(span);
  } catch (e) {
      console.error("Error applying annotation:", e);
      // Fallback or notification if needed
  } finally {
     hideMenu();
     selectedRange = null; // Clear selection after applying
     window.getSelection().removeAllRanges(); // Deselect text
  }
}

document.getElementById('annotated').addEventListener('mouseup',e=>{
  const sel=window.getSelection();
  if(!sel || sel.isCollapsed || !sel.rangeCount) return;

  // Check if the selection is actually within the 'annotated' div
  const container = document.getElementById('annotated');
  if (!container.contains(sel.anchorNode) || !container.contains(sel.focusNode)) {
      return; // Selection is outside the target div
  }

  selectedRange=sel.getRangeAt(0).cloneRange();
  const menu=document.getElementById('annotate-menu');

  // Set display to block to measure dimensions, but make it invisible initially for smoother appearance
  menu.style.visibility = 'hidden';
  menu.style.display='block';
  document.getElementById('comment-input').value='';
  // Don't focus yet, until position is calculated

  let menuHeight = menu.offsetHeight; // Get height after display:block
  let menuWidth = menu.offsetWidth; // Get width after display:block

  // Attempt to position menu above and slightly to the right of the cursor initially
  let top = e.pageY - menuHeight - 5; // 5px offset above (menu bottom is 5px above cursor)
  let left = e.pageX + 5;             // 5px offset to the right of the cursor

  // Boundary checks to keep menu within viewport
  const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
  const scrollY = window.pageYOffset || document.documentElement.scrollTop;
  const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight;

  // If menu goes off top, try to position it below the cursor
  if (top < scrollY) {
    top = e.pageY + 15; // Place below cursor (15px offset)
  }

  // If menu goes off right, adjust left to keep it in viewport
  if (left + menuWidth > scrollX + viewportWidth) {
    left = scrollX + viewportWidth - menuWidth - 5; // 5px padding from right edge
  }
  // If menu goes off left (e.g., if it was flipped to below and cursor is far left), adjust left
  if (left < scrollX) {
    left = scrollX + 5; // 5px padding from left edge
  }
  // If menu goes off bottom (especially if it was flipped below cursor), adjust top
  if (top + menuHeight > scrollY + viewportHeight) {
      top = scrollY + viewportHeight - menuHeight - 5; // 5px padding from bottom edge
  }
  // A final check if after all adjustments, it's still too high (e.g. very tall menu in short viewport)
  if (top < scrollY) {
      top = scrollY + 5; // 5px padding from top edge
  }

  menu.style.left=left+'px';
  menu.style.top=top+'px';
  menu.style.visibility = 'visible'; // Make it visible after positioning
  document.getElementById('comment-input').focus(); // Focus the input field now
});

// Hide menu if clicking elsewhere
document.addEventListener('mousedown', function(event) {
    const menu = document.getElementById('annotate-menu');
    const annotatedDiv = document.getElementById('annotated');
    // Hide if click is outside the menu AND outside the annotated div (unless it was the click that opened the menu)
    if (menu.style.display === 'block' && !menu.contains(event.target)) {
        // Check if the click was inside the annotated div to potentially start a new selection
        // If the click is outside the annotated div entirely, hide the menu.
        if (!annotatedDiv.contains(event.target)) {
             hideMenu();
        } else {
            // If click is inside annotated div but not on the menu,
            // potentially allow starting a new selection without explicitly hiding menu here.
            // The mouseup event on 'annotated' will handle showing the menu for a new selection.
            // However, if the selection becomes collapsed, we should hide it.
             setTimeout(() => { // Use timeout to allow selection to update
                 const sel = window.getSelection();
                 if (!sel || sel.isCollapsed) {
                     hideMenu();
                 }
             }, 0);
        }
    }
});
