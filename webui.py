import json
import subprocess
import uuid
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
import sqlite3
import os
import logging
import asyncio
import threading
from queue import Queue
from urllib.parse import unquote_plus, parse_qs

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Database setup
def init_db():
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS workflows
                 (id TEXT PRIMARY KEY, name TEXT, steps TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS shortcuts
                 (id TEXT PRIMARY KEY, name TEXT, description TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS knowledge_structures
                 (id TEXT PRIMARY KEY, name TEXT, content TEXT, parent_id TEXT)''')
    
    # Add form_definition column if it doesn't exist
    c.execute("PRAGMA table_info(workflows)")
    columns = [column[1] for column in c.fetchall()]
    if 'form_definition' not in columns:
        c.execute("ALTER TABLE workflows ADD COLUMN form_definition TEXT")
    
    conn.commit()
    conn.close()

def get_workflows():
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("SELECT id, name, steps, form_definition FROM workflows")
    workflows = [{"id": row[0], "name": row[1], "steps": json.loads(row[2]), "form_definition": json.loads(row[3]) if row[3] else None} for row in c.fetchall()]
    conn.close()
    return workflows

def save_workflow(workflow):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO workflows (id, name, steps, form_definition) VALUES (?, ?, ?, ?)",
              (workflow['id'], workflow['name'], json.dumps(workflow['steps']), json.dumps(workflow.get('form_definition'))))
    conn.commit()
    conn.close()

def get_shortcuts():
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("SELECT * FROM shortcuts")
    shortcuts = [{"id": row[0], "name": row[1], "description": row[2]} for row in c.fetchall()]
    conn.close()
    return shortcuts

def save_shortcut(shortcut):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO shortcuts (id, name, description) VALUES (?, ?, ?)",
              (shortcut['id'], shortcut['name'], shortcut['description']))
    conn.commit()
    conn.close()

def get_knowledge_structures():
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("SELECT * FROM knowledge_structures")
    structures = [{"id": row[0], "name": row[1], "content": row[2], "parent_id": row[3]} for row in c.fetchall()]
    conn.close()
    return structures

def get_knowledge_structure(structure_id):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("SELECT * FROM knowledge_structures WHERE id = ?", (structure_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "name": row[1], "content": row[2], "parent_id": row[3]}
    return None

def save_knowledge_structure(structure):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    if 'id' not in structure or not structure['id']:
        structure['id'] = str(uuid.uuid4())
    c.execute("INSERT OR REPLACE INTO knowledge_structures (id, name, content, parent_id) VALUES (?, ?, ?, ?)",
              (structure['id'], structure['name'], structure['content'], structure.get('parent_id')))
    conn.commit()
    conn.close()

def get_user_shortcuts():
    try:
        result = subprocess.run(['shortcuts', 'list'], capture_output=True, text=True)
        shortcuts = result.stdout.strip().split('\n')
        return [{"id": str(uuid.uuid4()), "name": s, "description": "User shortcut"} for s in shortcuts if s]
    except subprocess.CalledProcessError as e:
        logging.error(f"Error retrieving shortcuts: {str(e)}")
        return []

def refresh_shortcuts():
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("DELETE FROM shortcuts")
    conn.commit()
    
    user_shortcuts = get_user_shortcuts()
    for shortcut in user_shortcuts:
        save_shortcut(shortcut)
    
    conn.close()
    return user_shortcuts

def update_shortcut_description(shortcut_id, description):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("UPDATE shortcuts SET description = ? WHERE id = ?", (description, shortcut_id))
    conn.commit()
    conn.close()

# Initialize shortcuts on startup
def init_shortcuts():
    if not get_shortcuts():
        refresh_shortcuts()

# Workflow and Shortcut execution
async def run_shortcut(shortcut_name, input_json):
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
        json.dump(input_json, temp_file)
        temp_file_path = temp_file.name

    try:
        process = await asyncio.create_subprocess_exec(
            'shortcuts', 'run', shortcut_name, '--input-path', temp_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise Exception(f"Shortcut {shortcut_name} failed: {stderr.decode()}")
        return stdout.decode()
    finally:
        os.unlink(temp_file_path)

async def run_workflow(workflow, input_json, status_queue):
    # Process knowledge structures
    if 'context' in input_json and isinstance(input_json['context'], list):
        processed_contexts = []
        for structure in input_json['context']:
            if 'id' in structure:
                # Fetch the full content of the knowledge structure
                full_structure = get_knowledge_structure(structure['id'])
                if full_structure and 'content' in full_structure:
                    processed_contexts.append(full_structure['content'])
                else:
                    logging.warning(f"Content not found for knowledge structure with id: {structure['id']}")
            elif 'content' in structure:
                processed_contexts.append(structure['content'])
            else:
                logging.warning(f"Invalid knowledge structure format: {structure}")
        input_json['context'] = processed_contexts

    for i, step in enumerate(workflow['steps']):
        status_queue.put(json.dumps({"status": "running", "step": i + 1, "total": len(workflow['steps'])}))
        if isinstance(step, list):  # Parallel branch
            tasks = [run_shortcut(s['name'], input_json) for s in step]
            outputs = await asyncio.gather(*tasks)
            status_queue.put(json.dumps({"status": "output", "step": i + 1, "output": outputs}))
        else:
            output = await run_shortcut(step['name'], input_json)
            status_queue.put(json.dumps({"status": "output", "step": i + 1, "output": output}))
        input_json['previous_output'] = output  # Pass output to next step
    status_queue.put(json.dumps({"status": "completed"}))

def workflow_runner(workflow, input_json, status_queue):
    try:
        asyncio.run(run_workflow(workflow, input_json, status_queue))
    except Exception as e:
        logging.error(f"Error in workflow execution: {str(e)}")
        status_queue.put(json.dumps({"status": "error", "message": str(e)}))

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ollama Shortcuts UI</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/sortablejs@1.14.0/Sortable.min.js"></script>
    <style>
        .drag-item { cursor: move; }
        .drag-item.sortable-ghost { opacity: 0.4; }
    </style>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto p-4">
        <h1 class="text-3xl font-bold mb-4">Ollama Workflow Master</h1>
        
        <div class="mb-4">
            <button class="tab-button bg-blue-500 text-white px-4 py-2 rounded" data-tab="dashboard">Dashboard</button>
            <button class="tab-button bg-blue-500 text-white px-4 py-2 rounded" data-tab="workflows">Workflows</button>
            <button class="tab-button bg-blue-500 text-white px-4 py-2 rounded" data-tab="shortcuts">Shortcuts</button>
            <button class="tab-button bg-blue-500 text-white px-4 py-2 rounded" data-tab="formbuilder">Form Builder</button>
            <button class="tab-button bg-blue-500 text-white px-4 py-2 rounded" data-tab="context">Context Manager</button>
            <button class="tab-button bg-blue-500 text-white px-4 py-2 rounded" data-tab="settings">Settings</button>
        </div>

        <div id="dashboard" class="tab-content">
            <h2 class="text-2xl font-bold mb-4">Workflow Dashboard</h2>
            <div id="workflow-list" class="space-y-4"></div>
            <div id="workflow-status" style="display: none;">
                <h3 class="text-xl font-bold mb-2">Workflow Status</h3>
                <div class="w-full bg-gray-200 rounded">
                    <div class="progress-bar-fill bg-blue-500 text-xs font-medium text-blue-100 text-center p-0.5 leading-none rounded" style="width: 0%"></div>
                </div>
                <p class="status-text mt-2"></p>
                <div class="step-outputs mt-4 space-y-4"></div>
            </div>
        </div>

        <div id="workflows" class="tab-content">
            <h2 class="text-2xl font-bold mb-4">Workflow Composer</h2>
            <select id="workflow-select" class="w-full p-2 mb-4 border rounded">
                <option value="">Select a workflow</option>
            </select>
            <input type="text" id="workflow-name" class="w-full p-2 mb-4 border rounded" placeholder="Workflow name">
            <div id="workflow-steps" class="mb-4 p-4 bg-white rounded shadow">
                <h3 class="text-xl font-bold mb-2">Workflow Steps</h3>
                <div id="step-list" class="space-y-2"></div>
            </div>
            <select id="shortcut-select" class="w-full p-2 mb-4 border rounded">
                <option value="">Add step</option>
            </select>
            <button id="add-parallel" class="bg-green-500 text-white px-4 py-2 rounded">Add Parallel Branch</button>
            <button id="save-workflow" class="bg-blue-500 text-white px-4 py-2 rounded">Save Workflow</button>
            <div id="workflow-form" class="mt-4"></div>
            <textarea id="workflow-input" class="w-full p-2 mt-4 border rounded" placeholder="Enter input for the workflow"></textarea>
            <button id="run-workflow" class="mt-4 bg-blue-500 text-white px-4 py-2 rounded">Run Workflow</button>
        </div>

        <div id="shortcuts" class="tab-content">
            <h2 class="text-2xl font-bold mb-4">Shortcut Library</h2>
            <div id="shortcut-list" class="mb-4">
                <select id="shortcut-dropdown" class="w-full p-2 mb-4 border rounded">
                    <option value="">Select a shortcut</option>
                </select>
            </div>
            <div id="shortcut-details" class="p-4 bg-white rounded shadow">
                <h3 id="shortcut-name" class="text-xl font-bold mb-2"></h3>
                <textarea id="shortcut-description" rows="4" class="w-full p-2 mb-4 border rounded" placeholder="Shortcut description"></textarea>
                <textarea id="shortcut-input" rows="4" class="w-full p-2 mb-4 border rounded" placeholder="Enter input JSON for the shortcut"></textarea>
                <button id="update-description" class="bg-green-500 text-white px-4 py-2 rounded">Update Description</button>
                <button id="run-shortcut" class="bg-blue-500 text-white px-4 py-2 rounded">Run Shortcut</button>
            </div>
            <button id="refresh-shortcuts" class="mt-4 bg-yellow-500 text-white px-4 py-2 rounded">Refresh Shortcuts</button>
            <div id="shortcut-status" class="mt-4 p-4 bg-white rounded shadow" style="display: none;">
                <h3 class="text-xl font-bold mb-2">Shortcut Status</h3>
                <p id="shortcut-status-text"></p>
                <div id="shortcut-output" class="mt-4 p-2 bg-gray-100 rounded"></div>
                <button id="copy-shortcut-output" class="mt-2 bg-gray-500 text-white px-4 py-2 rounded">Copy to Clipboard</button>
            </div>
        </div>

        <div id="formbuilder" class="tab-content">
            <h2 class="text-2xl font-bold mb-4">Form Builder</h2>
            <select id="form-workflow-select" class="w-full p-2 mb-4 border rounded">
                <option value="">Select a workflow</option>
            </select>
            <div id="form-fields" class="space-y-4"></div>
            <button id="add-form-field" class="mt-4 bg-green-500 text-white px-4 py-2 rounded">Add Field</button>
            <button id="save-form" class="mt-4 bg-blue-500 text-white px-4 py-2 rounded">Save Form</button>
        </div>

        <div id="context" class="tab-content">
            <h2 class="text-2xl font-bold mb-4">Context Manager</h2>
            <div id="knowledge-structure-list" class="mb-4 space-y-2"></div>
            <input type="text" id="new-structure-name" class="w-full p-2 mb-2 border rounded" placeholder="New structure name">
            <textarea id="new-structure-content" rows="4" class="w-full p-2 mb-2 border rounded" placeholder="New structure content"></textarea>
            <select id="parent-structure-select" class="w-full p-2 mb-2 border rounded">
                <option value="">Select parent structure (optional)</option>
            </select>
            <button id="add-knowledge-structure" class="bg-green-500 text-white px-4 py-2 rounded">Add Knowledge Structure</button>
        </div>

        <div id="settings" class="tab-content">
            <h2 class="text-2xl font-bold mb-4">Settings</h2>
            <label for="ollama-api-url" class="block mb-2">Ollama API URL:</label>
            <input type="text" id="ollama-api-url" class="w-full p-2 mb-4 border rounded" placeholder="http://localhost:11434">
            <button id="save-settings" class="bg-blue-500 text-white px-4 py-2 rounded">Save Settings</button>
        </div>
    </div>

    <script>
        // Tab functionality
        const tabButtons = document.querySelectorAll('.tab-button');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabName = button.getAttribute('data-tab');
                tabContents.forEach(content => {
                    content.style.display = 'none';
                });
                document.getElementById(tabName).style.display = 'block';
            });
        });

        // Workflow functionality
        let currentWorkflow = { id: '', name: '', steps: [], form_definition: null };

        function updateWorkflowDisplay() {
            const stepList = document.getElementById('step-list');
            stepList.innerHTML = '';
            currentWorkflow.steps.forEach((step, index) => {
                const stepElement = document.createElement('div');
                stepElement.className = 'drag-item p-2 bg-gray-200 rounded flex justify-between items-center';
                if (Array.isArray(step)) {
                    stepElement.textContent = `Parallel Branch ${index + 1}`;
                    const innerList = document.createElement('div');
                    innerList.className = 'ml-4 space-y-2';
                    step.forEach((parallelStep, parallelIndex) => {
                        const parallelStepElement = document.createElement('div');
                        parallelStepElement.className = 'drag-item p-2 bg-gray-100 rounded flex justify-between items-center';
                        parallelStepElement.textContent = parallelStep.name;
                        const removeButton = createRemoveButton(() => {
                            step.splice(parallelIndex, 1);
                            if (step.length === 0) {
                                currentWorkflow.steps.splice(index, 1);
                            }
                            updateWorkflowDisplay();
                        });
                        parallelStepElement.appendChild(removeButton);
                        innerList.appendChild(parallelStepElement);
                    });
                    stepElement.appendChild(innerList);
                } else {
                    stepElement.textContent = step.name;
                }
                const removeButton = createRemoveButton(() => {
                    currentWorkflow.steps.splice(index, 1);
                    updateWorkflowDisplay();
                });
                stepElement.appendChild(removeButton);
                stepList.appendChild(stepElement);
            });
            new Sortable(stepList, {
                animation: 150,
                ghostClass: 'sortable-ghost'
            });
        }

        function createRemoveButton(onClick) {
            const button = document.createElement('button');
            button.textContent = 'Remove';
            button.className = 'bg-red-500 text-white px-2 py-1 rounded text-sm';
            button.onclick = onClick;
            return button;
        }

        document.getElementById('workflow-select').addEventListener('change', (e) => {
            if (e.target.value) {
                fetch(`/get-workflow/${e.target.value}`)
                    .then(response => response.json())
                    .then(data => {
                        currentWorkflow = data;
                        document.getElementById('workflow-name').value = currentWorkflow.name;
                        updateWorkflowDisplay();
                        updateWorkflowForm();
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Failed to load workflow. Please try again.');
                    });
            } else {
                currentWorkflow = { id: '', name: '', steps: [], form_definition: null };
                document.getElementById('workflow-name').value = '';
                updateWorkflowDisplay();
                updateWorkflowForm();
            }
        });

        function updateWorkflowForm() {
            const formContainer = document.getElementById('workflow-form');
            formContainer.innerHTML = '';
            if (currentWorkflow.form_definition) {
                currentWorkflow.form_definition.forEach(field => {
                    const fieldElement = document.createElement('div');
                    fieldElement.className = 'mb-2';
                    let inputElement;
                    switch (field.type) {
                        case 'text':
                        case 'number':
                            inputElement = document.createElement('input');
                            inputElement.type = field.type;
                            break;
                        case 'textarea':
                            inputElement = document.createElement('textarea');
                            break;
                        case 'select':
                            inputElement = document.createElement('select');
                            field.options.forEach(option => {
                                const optionElement = document.createElement('option');
                                optionElement.value = option;
                                optionElement.textContent = option;
                                inputElement.appendChild(optionElement);
                            });
                            break;
                        case 'knowledge-structure':
                            inputElement = document.createElement('select');
                            inputElement.multiple = true;
                            fetchKnowledgeStructures().then(structures => {
                                structures.forEach(structure => {
                                    const optionElement = document.createElement('option');
                                    optionElement.value = structure.id;
                                    optionElement.textContent = structure.name;
                                    optionElement.dataset.content = structure.content; // Store content in data attribute
                                    inputElement.appendChild(optionElement);
                                });
                            });
                            break;
                    }
                    inputElement.name = field.name;
                    inputElement.className = 'w-full p-2 border rounded';
                    inputElement.placeholder = field.label;
                    fieldElement.appendChild(inputElement);
                    formContainer.appendChild(fieldElement);
                });
            }
        }

        document.getElementById('run-workflow').addEventListener('click', () => {
            const workflowId = currentWorkflow.id;
            const formData = new FormData(document.getElementById('workflow-form'));
            const inputJson = Object.fromEntries(formData);
            inputJson.user_input = document.getElementById('workflow-input').value;
            runWorkflow(workflowId, inputJson);
        });

        function runWorkflow(workflowId, inputJson) {
            console.log('Running workflow:', workflowId);
            console.log('Input JSON:', inputJson);

            const statusElement = document.getElementById('workflow-status');
            if (!statusElement) {
                console.error('Workflow status element not found');
                alert('Error: Workflow status element not found. Please refresh the page and try again.');
                return;
            }

            const progressBar = statusElement.querySelector('.progress-bar-fill');
            const statusText = statusElement.querySelector('.status-text');
            const stepOutputs = statusElement.querySelector('.step-outputs');

            if (!progressBar || !statusText || !stepOutputs) {
                console.error('One or more required elements not found in the workflow status');
                alert('Error: Some required elements are missing. Please refresh the page and try again.');
                return;
            }

            statusElement.style.display = 'block';
            progressBar.style.width = '0%';
            statusText.textContent = 'Initializing workflow...';
            stepOutputs.innerHTML = '';

            const eventSource = new EventSource(`/run-workflow/${workflowId}?input=${encodeURIComponent(JSON.stringify(inputJson))}`);

            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.status === 'running') {
                    const progress = (data.step / data.total) * 100;
                    progressBar.style.width = `${progress}%`;
                    statusText.textContent = `Running step ${data.step} of ${data.total}`;
                } else if (data.status === 'output') {
                    const outputElement = document.createElement('div');
                    outputElement.className = 'mb-4 p-4 bg-gray-100 rounded';
                    outputElement.innerHTML = `
                        <h4 class="font-bold mb-2">Step ${data.step} Output:</h4>
                        <div class="whitespace-pre-wrap">${typeof marked === 'function' ? marked(data.output) : data.output}</div>
                        <button class="copy-output mt-2 bg-gray-500 text-white px-2 py-1 rounded text-sm" data-output="${data.output}">Copy to Clipboard</button>
                    `;
                    stepOutputs.appendChild(outputElement);
                } else if (data.status === 'completed') {
                    progressBar.style.width = '100%';
                    statusText.textContent = 'Workflow completed successfully';
                    eventSource.close();
                }
            };

            eventSource.onerror = function(error) {
                console.error('EventSource failed:', error);
                statusText.textContent = 'Error running workflow';
                eventSource.close();
            };
        }

        document.getElementById('shortcut-select').addEventListener('change', (e) => {
            if (e.target.value) {
                const selectedShortcut = JSON.parse(e.target.value);
                currentWorkflow.steps.push(selectedShortcut);
                updateWorkflowDisplay();
                e.target.value = '';
            }
        });

        document.getElementById('add-parallel').addEventListener('click', () => {
            currentWorkflow.steps.push([]);
            updateWorkflowDisplay();
        });

        document.getElementById('save-workflow').addEventListener('click', () => {
            const workflowName = document.getElementById('workflow-name').value;
            if (workflowName) {
                currentWorkflow.name = workflowName;
                currentWorkflow.id = currentWorkflow.id || String(Date.now());
                fetch('/save-workflow', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(currentWorkflow)
                })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    loadWorkflows();
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to save workflow. Please try again.');
                });
            } else {
                alert('Please enter a workflow name');
            }
        });

        function loadWorkflows() {
            fetch('/workflows')
                .then(response => response.json())
                .then(data => {
                    const workflowList = document.getElementById('workflow-list');
                    const workflowSelect = document.getElementById('workflow-select');
                    const formWorkflowSelect = document.getElementById('form-workflow-select');
                    workflowList.innerHTML = '';
                    workflowSelect.innerHTML = '<option value="">Select a workflow</option>';
                    formWorkflowSelect.innerHTML = '<option value="">Select a workflow</option>';
                    data.forEach(workflow => {
                        const workflowElement = document.createElement('div');
                        workflowElement.className = 'p-4 bg-white rounded shadow mb-4';
                        workflowElement.innerHTML = `
                            <h3 class="text-xl font-bold mb-2">${workflow.name}</h3>
                            <p class="mb-2">${JSON.stringify(workflow.steps)}</p>
                            <div id="workflow-form-${workflow.id}" class="mb-4"></div>
                            <textarea id="workflow-input-${workflow.id}" class="w-full p-2 mb-2 border rounded" placeholder="Enter input for the workflow"></textarea>
                            <button class="run-workflow bg-blue-500 text-white px-4 py-2 rounded" data-id="${workflow.id}">Run Workflow</button>
                        `;
                        workflowList.appendChild(workflowElement);
                        
                        const option = document.createElement('option');
                        option.value = workflow.id;
                        option.textContent = workflow.name;
                        workflowSelect.appendChild(option.cloneNode(true));
                        formWorkflowSelect.appendChild(option);

                        if (workflow.form_definition) {
                            createDynamicForm(workflow.id, workflow.form_definition);
                        }
                    });
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to load workflows. Please try again.');
                });
        }

        function createDynamicForm(workflowId, formDefinition) {
            const formContainer = document.getElementById(`workflow-form-${workflowId}`);
            formContainer.innerHTML = '';
            formDefinition.forEach(field => {
                const fieldElement = document.createElement('div');
                fieldElement.className = 'mb-2';
                let inputElement;
                switch (field.type) {
                    case 'text':
                    case 'number':
                        inputElement = document.createElement('input');
                        inputElement.type = field.type;
                        break;
                    case 'textarea':
                        inputElement = document.createElement('textarea');
                        break;
                    case 'select':
                        inputElement = document.createElement('select');
                        field.options.forEach(option => {
                            const optionElement = document.createElement('option');
                            optionElement.value = option;
                            optionElement.textContent = option;
                            inputElement.appendChild(optionElement);
                        });
                        break;
                    case 'knowledge-structure':
                        inputElement = document.createElement('select');
                        inputElement.multiple = true;
                        // We need to populate this with actual knowledge structures
                        fetchKnowledgeStructures().then(structures => {
                            structures.forEach(structure => {
                                const optionElement = document.createElement('option');
                                optionElement.value = structure.id;
                                optionElement.textContent = structure.name;
                                inputElement.appendChild(optionElement);
                            });
                        });
                        break;
                }
                inputElement.name = field.name;
                inputElement.className = 'w-full p-2 border rounded';
                inputElement.placeholder = field.label;
                const labelElement = document.createElement('label');
                labelElement.textContent = field.label;
                labelElement.className = 'block mb-1 font-bold';
                fieldElement.appendChild(labelElement);
                fieldElement.appendChild(inputElement);
                formContainer.appendChild(fieldElement);
            });
        }

        function fetchKnowledgeStructures() {
            return fetch('/knowledge-structures')
                .then(response => response.json())
                .catch(error => {
                    console.error('Error fetching knowledge structures:', error);
                    return [];
                });
        }

        document.getElementById('workflow-list').addEventListener('click', (e) => {
            if (e.target.classList.contains('run-workflow')) {
                const workflowId = e.target.getAttribute('data-id');
                const formContainer = document.getElementById(`workflow-form-${workflowId}`);
                const inputJson = {};
                
                // Collect form data
                if (formContainer) {
                    formContainer.querySelectorAll('input, select, textarea').forEach(element => {
                        if (element.type === 'select-multiple') {
                            inputJson[element.name] = Array.from(element.selectedOptions).map(option => ({
                                id: option.value,
                                name: option.textContent
                            }));
                        } else {
                            inputJson[element.name] = element.value;
                        }
                    });
                }
                
                // Add the user input
                const userInputElement = document.getElementById(`workflow-input-${workflowId}`);
                if (userInputElement) {
                    inputJson.user_input = userInputElement.value;
                }
                
                runWorkflow(workflowId, inputJson);
            }
        });

        function loadShortcuts() {
            fetch('/shortcuts')
                .then(response => response.json())
                .then(data => {
                    const shortcutSelect = document.getElementById('shortcut-select');
                    const shortcutDropdown = document.getElementById('shortcut-dropdown');
                    shortcutSelect.innerHTML = '<option value="">Add step</option>';
                    shortcutDropdown.innerHTML = '<option value="">Select a shortcut</option>';
                    data.forEach(shortcut => {
                        const option = document.createElement('option');
                        option.value = JSON.stringify(shortcut);
                        option.textContent = shortcut.name;
                        shortcutSelect.appendChild(option.cloneNode(true));
                        shortcutDropdown.appendChild(option);
                    });
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to load shortcuts. Please try again.');
                });
        }

        document.getElementById('shortcut-dropdown').addEventListener('change', (e) => {
            if (e.target.value) {
                const selectedShortcut = JSON.parse(e.target.value);
                document.getElementById('shortcut-name').textContent = selectedShortcut.name;
                document.getElementById('shortcut-description').value = selectedShortcut.description;
            } else {
                document.getElementById('shortcut-name').textContent = '';
                document.getElementById('shortcut-description').value = '';
            }
        });

        document.getElementById('update-description').addEventListener('click', () => {
            const shortcutId = JSON.parse(document.getElementById('shortcut-dropdown').value).id;
            const description = document.getElementById('shortcut-description').value;
            fetch('/update-shortcut-description', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: shortcutId, description: description })
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                loadShortcuts();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to update shortcut description. Please try again.');
            });
        });

        document.getElementById('refresh-shortcuts').addEventListener('click', () => {
            fetch('/refresh-shortcuts', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                loadShortcuts();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to refresh shortcuts. Please try again.');
            });
        });

        document.getElementById('run-shortcut').addEventListener('click', () => {
            const shortcutName = document.getElementById('shortcut-name').textContent;
            const inputText = document.getElementById('shortcut-input').value;
            if (shortcutName && inputText) {
                const inputJson = { user_input: inputText };
                runShortcut(shortcutName, inputJson);
            } else {
                alert('Please select a shortcut and enter input text');
            }
        });

        function runWorkflow(workflowId, inputJson) {
            console.log('Running workflow:', workflowId);
            console.log('Input JSON:', inputJson);

            const statusElement = document.getElementById('workflow-status');
            if (!statusElement) {
                console.error('Workflow status element not found');
                alert('Error: Workflow status element not found. Please refresh the page and try again.');
                return;
            }

            const progressBar = statusElement.querySelector('.progress-bar-fill');
            const statusText = statusElement.querySelector('.status-text');
            const stepOutputs = statusElement.querySelector('.step-outputs');

            if (!progressBar || !statusText || !stepOutputs) {
                console.error('One or more required elements not found in the workflow status');
                alert('Error: Some required elements are missing. Please refresh the page and try again.');
                return;
            }

            statusElement.style.display = 'block';
            progressBar.style.width = '0%';
            statusText.textContent = 'Initializing workflow...';
            stepOutputs.innerHTML = '';

            const eventSource = new EventSource(`/run-workflow/${workflowId}?input=${encodeURIComponent(JSON.stringify(inputJson))}`);

            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.status === 'running') {
                    const progress = (data.step / data.total) * 100;
                    progressBar.style.width = `${progress}%`;
                    statusText.textContent = `Running step ${data.step} of ${data.total}`;
                } else if (data.status === 'output') {
                    const outputElement = document.createElement('div');
                    outputElement.className = 'mb-4 p-4 bg-gray-100 rounded';
                    
                    // Safely encode the output to prevent XSS
                    const encodedOutput = data.output
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;')
                        .replace(/'/g, '&#039;');

                    outputElement.innerHTML = `
                        <h4 class="font-bold mb-2">Step ${data.step} Output:</h4>
                        <pre class="whitespace-pre-wrap">${encodedOutput}</pre>
                        <button class="copy-output mt-2 bg-gray-500 text-white px-2 py-1 rounded text-sm" data-output="${encodedOutput}">Copy to Clipboard</button>
                    `;
                    stepOutputs.appendChild(outputElement);
                } else if (data.status === 'completed') {
                    progressBar.style.width = '100%';
                    statusText.textContent = 'Workflow completed successfully';
                    eventSource.close();
                }
            };

            eventSource.onerror = function(error) {
                console.error('EventSource failed:', error);
                statusText.textContent = 'Error running workflow';
                eventSource.close();
            };
        }

        function runShortcut(shortcutName, inputJson) {
            const statusElement = document.getElementById('shortcut-status');
            const statusText = document.getElementById('shortcut-status-text');
            const outputElement = document.getElementById('shortcut-output');

            statusElement.style.display = 'block';
            statusText.textContent = 'Running shortcut...';
            outputElement.innerHTML = '';

            fetch(`/run-shortcut/${encodeURIComponent(shortcutName)}?input=${encodeURIComponent(JSON.stringify(inputJson))}`)
                .then(response => response.json())
                .then(data => {
                    statusText.textContent = 'Shortcut completed';
                    outputElement.innerHTML = marked(data.result);
                    // Make sure the output is visible
                    outputElement.style.display = 'block';
                })
                .catch(error => {
                    console.error('Error:', error);
                    statusText.textContent = 'Error running shortcut';
                    outputElement.textContent = 'An error occurred while running the shortcut.';
                    outputElement.style.display = 'block';
                });
        }


        document.getElementById('copy-shortcut-output').addEventListener('click', () => {
            const output = document.getElementById('shortcut-output').textContent;
            navigator.clipboard.writeText(output).then(() => {
                alert('Output copied to clipboard');
            }).catch(err => {
                console.error('Failed to copy: ', err);
            });
        });

        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('copy-output')) {
                const output = e.target.getAttribute('data-output');
                navigator.clipboard.writeText(output).then(() => {
                    alert('Output copied to clipboard');
                }).catch(err => {
                    console.error('Failed to copy: ', err);
                });
            }
        });

        // Form Builder functionality
        let currentForm = [];

        document.getElementById('form-workflow-select').addEventListener('change', (e) => {
            if (e.target.value) {
                fetch(`/get-workflow/${e.target.value}`)
                    .then(response => response.json())
                    .then(data => {
                        currentForm = data.form_definition || [];
                        updateFormBuilder();
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Failed to load workflow form. Please try again.');
                    });
            } else {
                currentForm = [];
                updateFormBuilder();
            }
        });

        function updateFormBuilder() {
            const formFields = document.getElementById('form-fields');
            formFields.innerHTML = '';
            currentForm.forEach((field, index) => {
                const fieldElement = document.createElement('div');
                fieldElement.className = 'p-4 bg-white rounded shadow mb-4';
                fieldElement.innerHTML = `
                    <input type="text" class="w-full p-2 mb-2 border rounded" value="${field.label}" placeholder="Field Label">
                    <select class="w-full p-2 mb-2 border rounded">
                        <option value="text" ${field.type === 'text' ? 'selected' : ''}>Text</option>
                        <option value="number" ${field.type === 'number' ? 'selected' : ''}>Number</option>
                        <option value="textarea" ${field.type === 'textarea' ? 'selected' : ''}>Textarea</option>
                        <option value="select" ${field.type === 'select' ? 'selected' : ''}>Select</option>
                        <option value="knowledge-structure" ${field.type === 'knowledge-structure' ? 'selected' : ''}>Knowledge Structure</option>
                    </select>
                    <input type="text" class="w-full p-2 mb-2 border rounded" value="${field.name}" placeholder="Field Name">
                    ${field.type === 'select' ? `<input type="text" class="w-full p-2 mb-2 border rounded" value="${field.options.join(',')}" placeholder="Options (comma-separated)">` : ''}
                    <button class="remove-field bg-red-500 text-white px-2 py-1 rounded" data-index="${index}">Remove</button>
                `;
                formFields.appendChild(fieldElement);
            });
        }

        document.getElementById('add-form-field').addEventListener('click', () => {
            currentForm.push({ label: '', type: 'text', name: '' });
            updateFormBuilder();
        });

        document.getElementById('form-fields').addEventListener('click', (e) => {
            if (e.target.classList.contains('remove-field')) {
                const index = parseInt(e.target.getAttribute('data-index'));
                currentForm.splice(index, 1);
                updateFormBuilder();
            }
        });

        document.getElementById('save-form').addEventListener('click', () => {
            const workflowId = document.getElementById('form-workflow-select').value;
            if (workflowId) {
                const formFields = document.getElementById('form-fields').children;
                const updatedForm = Array.from(formFields).map(field => {
                    const label = field.querySelector('input[placeholder="Field Label"]').value;
                    const type = field.querySelector('select').value;
                    const name = field.querySelector('input[placeholder="Field Name"]').value;
                    const options = type === 'select' ? field.querySelector('input[placeholder="Options (comma-separated)"]').value.split(',') : undefined;
                    return { label, type, name, options };
                });
                fetch(`/save-form/${workflowId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updatedForm)
                })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    loadWorkflows();
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to save form. Please try again.');
                });
            } else {
                alert('Please select a workflow');
            }
        });

        // Context Manager functionality
        function loadKnowledgeStructures() {
            fetch('/knowledge-structures')
                .then(response => response.json())
                .then(data => {
                    const structureList = document.getElementById('knowledge-structure-list');
                    const parentSelect = document.getElementById('parent-structure-select');
                    structureList.innerHTML = '';
                    parentSelect.innerHTML = '<option value="">Select parent structure (optional)</option>';
                    data.forEach(structure => {
                        const structureElement = document.createElement('div');
                        structureElement.className = 'p-4 bg-white rounded shadow';
                        structureElement.innerHTML = `
                            <h4 class="font-bold">${structure.name}</h4>
                            <p class="mt-2">${structure.content}</p>
                            <button class="edit-structure mt-2 bg-yellow-500 text-white px-2 py-1 rounded" data-id="${structure.id}">Edit</button>
                            <button class="delete-structure mt-2 bg-red-500 text-white px-2 py-1 rounded" data-id="${structure.id}">Delete</button>
                        `;
                        structureList.appendChild(structureElement);

                        const option = document.createElement('option');
                        option.value = structure.id;
                        option.textContent = structure.name;
                        parentSelect.appendChild(option);
                    });
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to load knowledge structures. Please try again.');
                });
        }

        document.getElementById('add-knowledge-structure').addEventListener('click', () => {
            const name = document.getElementById('new-structure-name').value;
            const content = document.getElementById('new-structure-content').value;
            const parentId = document.getElementById('parent-structure-select').value;
            if (name && content) {
                fetch('/add-knowledge-structure', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, content, parent_id: parentId || null })
                })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    loadKnowledgeStructures();
                    document.getElementById('new-structure-name').value = '';
                    document.getElementById('new-structure-content').value = '';
                    document.getElementById('parent-structure-select').value = '';
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to add knowledge structure. Please try again.');
                });
            } else {
                alert('Please enter both name and content for the knowledge structure');
            }
        });

        document.getElementById('knowledge-structure-list').addEventListener('click', (e) => {
            if (e.target.classList.contains('edit-structure')) {
                const structureId = e.target.getAttribute('data-id');
                // Implement edit functionality
            } else if (e.target.classList.contains('delete-structure')) {
                const structureId = e.target.getAttribute('data-id');
                if (confirm('Are you sure you want to delete this knowledge structure?')) {
                    fetch(`/delete-knowledge-structure/${structureId}`, { method: 'DELETE' })
                        .then(response => response.json())
                        .then(data => {
                            alert(data.message);
                            loadKnowledgeStructures();
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            alert('Failed to delete knowledge structure. Please try again.');
                        });
                }
            }
        });

        // Settings functionality
        document.getElementById('save-settings').addEventListener('click', () => {
            const apiUrl = document.getElementById('ollama-api-url').value;
            fetch('/save-settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ollama_api_url: apiUrl })
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to save settings. Please try again.');
            });
        });

        document.addEventListener('DOMContentLoaded', function() {
            function init() {
                loadWorkflows();
                loadShortcuts();
                loadKnowledgeStructures();
                // Set dashboard as the initial active tab
                document.querySelector('[data-tab="dashboard"]').click();
            }

            init();
        });
    </script>
</body>
</html>
"""

class OllamaHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/workflows':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_workflows()).encode())
        elif self.path.startswith('/get-workflow/'):
            workflow_id = self.path.split('/')[-1]
            workflow = next((w for w in get_workflows() if w['id'] == workflow_id), None)
            if workflow:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(workflow).encode())
            else:
                self.send_response(404)
                self.end_headers()
        elif self.path == '/shortcuts':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_shortcuts()).encode())
        elif self.path == '/knowledge-structures':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_knowledge_structures()).encode())
        elif self.path.startswith('/run-workflow/'):
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()

            workflow_id = self.path.split('/')[2].split('?')[0]
            query = parse_qs(self.path.split('?')[1])
            input_json = json.loads(unquote_plus(query['input'][0]))
            workflow = next((w for w in get_workflows() if w['id'] == workflow_id), None)
            if workflow:
                status_queue = Queue()
                threading.Thread(target=workflow_runner, args=(workflow, input_json, status_queue)).start()
                
                while True:
                    try:
                        status = status_queue.get(timeout=1)
                        self.wfile.write(f"data: {status}\n\n".encode())
                        self.wfile.flush()
                        if json.loads(status)['status'] == 'completed':
                            break
                    except:
                        continue
            else:
                self.wfile.write(b"data: {\"error\": \"Workflow not found\"}\n\n")
                self.wfile.flush()
        elif self.path.startswith('/run-shortcut/'):
            shortcut_name = unquote_plus(self.path.split('/')[2].split('?')[0])
            query = parse_qs(self.path.split('?')[1])
            input_json = json.loads(unquote_plus(query['input'][0]))
            try:
                result = asyncio.run(run_shortcut(shortcut_name, input_json))
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"result": result}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML.encode())

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        logging.debug(f"Received POST request to {self.path}")
        logging.debug(f"POST data: {post_data}")

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        try:
            data = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            data = {}

        if self.path == '/save-workflow':
            try:
                save_workflow(data)
                self.wfile.write(json.dumps({"message": "Workflow saved successfully"}).encode())
            except Exception as e:
                logging.error(f"Error saving workflow: {str(e)}")
                self.wfile.write(json.dumps({"error": "Failed to save workflow"}).encode())
        elif self.path.startswith('/save-form/'):
            workflow_id = self.path.split('/')[-1]
            try:
                workflow = next((w for w in get_workflows() if w['id'] == workflow_id), None)
                if workflow:
                    workflow['form_definition'] = data
                    save_workflow(workflow)
                    self.wfile.write(json.dumps({"message": "Form saved successfully"}).encode())
                else:
                    self.wfile.write(json.dumps({"error": "Workflow not found"}).encode())
            except Exception as e:
                logging.error(f"Error saving form: {str(e)}")
                self.wfile.write(json.dumps({"error": "Failed to save form"}).encode())
        elif self.path == '/refresh-shortcuts':
            try:
                refreshed_shortcuts = refresh_shortcuts()
                self.wfile.write(json.dumps({"message": f"Shortcuts refreshed successfully. Found {len(refreshed_shortcuts)} shortcuts."}).encode())
            except Exception as e:
                logging.error(f"Error refreshing shortcuts: {str(e)}")
                self.wfile.write(json.dumps({"error": "Failed to refresh shortcuts"}).encode())
        elif self.path == '/update-shortcut-description':
            try:
                update_shortcut_description(data['id'], data['description'])
                self.wfile.write(json.dumps({"message": "Shortcut description updated successfully"}).encode())
            except Exception as e:
                logging.error(f"Error updating shortcut description: {str(e)}")
                self.wfile.write(json.dumps({"error": "Failed to update shortcut description"}).encode())
        elif self.path == '/add-knowledge-structure':
            try:
                save_knowledge_structure(data)
                self.wfile.write(json.dumps({"message": "Knowledge structure added successfully"}).encode())
            except Exception as e:
                logging.error(f"Error adding knowledge structure: {str(e)}")
                self.wfile.write(json.dumps({"error": "Failed to add knowledge structure"}).encode())
        elif self.path == '/save-settings':
            try:
                # Here you would implement logic to save settings
                # For this example, we'll just log the received settings
                logging.info(f"Received settings: {data}")
                self.wfile.write(json.dumps({"message": "Settings saved successfully"}).encode())
            except Exception as e:
                logging.error(f"Error saving settings: {str(e)}")
                self.wfile.write(json.dumps({"error": "Failed to save settings"}).encode())
        else:
            self.wfile.write(json.dumps({'error': 'Invalid endpoint'}).encode())

    def do_DELETE(self):
        if self.path.startswith('/delete-knowledge-structure/'):
            structure_id = self.path.split('/')[-1]
            try:
                conn = sqlite3.connect('ollama_workflows.db')
                c = conn.cursor()
                c.execute("DELETE FROM knowledge_structures WHERE id = ?", (structure_id,))
                conn.commit()
                conn.close()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"message": "Knowledge structure deleted successfully"}).encode())
            except Exception as e:
                logging.error(f"Error deleting knowledge structure: {str(e)}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Failed to delete knowledge structure"}).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Invalid endpoint'}).encode())

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, OllamaHandler)
    print(f'Server running on http://localhost:{port}')
    httpd.serve_forever()

if __name__ == '__main__':
    init_db()
    init_shortcuts()  # Initialize shortcuts on startup
    run_server()