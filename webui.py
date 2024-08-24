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

def init_db():
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    
    # Create tables if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS workflows
                 (id TEXT PRIMARY KEY, name TEXT, steps TEXT, 
                  form_definition TEXT, user_prompts TEXT,
                  import_format TEXT, version TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS shortcuts
                 (id TEXT PRIMARY KEY, name TEXT, description TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS knowledge_structures
                 (id TEXT PRIMARY KEY, name TEXT, content TEXT, parent_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_prompts
                 (id TEXT PRIMARY KEY, name TEXT, content TEXT)''')
    
    # Check if columns exist and add them if they don't
    c.execute("PRAGMA table_info(workflows)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'import_format' not in columns:
        c.execute("ALTER TABLE workflows ADD COLUMN import_format TEXT")
    if 'version' not in columns:
        c.execute("ALTER TABLE workflows ADD COLUMN version TEXT")
    if 'form_definition' not in columns:
        c.execute("ALTER TABLE workflows ADD COLUMN form_definition TEXT")
    if 'user_prompts' not in columns:
        c.execute("ALTER TABLE workflows ADD COLUMN user_prompts TEXT")
    
    conn.commit()
    conn.close()



def get_workflows():
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("SELECT id, name, steps, form_definition, import_format, version FROM workflows")
    workflows = [{"id": row[0], "name": row[1], "steps": json.loads(row[2]), 
                  "form_definition": json.loads(row[3]) if row[3] else None,
                  "import_format": row[4], "version": row[5]} for row in c.fetchall()]
    conn.close()
    return workflows

def save_workflow(workflow):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    
    c.execute('''INSERT OR REPLACE INTO workflows 
                 (id, name, steps, form_definition, import_format, version) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (workflow['id'], workflow['name'], json.dumps(workflow['steps']),
               json.dumps(workflow.get('form_definition')),
               workflow.get('import_format'),
               workflow.get('version')))
    
    conn.commit()
    conn.close()

def parse_imported_workflow(import_data):
    try:
        workflow = import_data['workflow']
        required_fields = ['id', 'name', 'steps']
        for field in required_fields:
            if field not in workflow:
                raise ValueError(f"Missing required field: {field}")
        
        # Ensure each step has the necessary fields
        for step in workflow['steps']:
            if 'id' not in step or 'name' not in step or 'type' not in step:
                raise ValueError(f"Step is missing required fields: {step}")
        
        return workflow
    except Exception as e:
        raise ValueError(f"Invalid workflow format: {str(e)}")

def get_shortcuts():
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("SELECT name, description FROM shortcuts")
    shortcuts = [{"name": row[0], "description": row[1]} for row in c.fetchall()]
    conn.close()
    return shortcuts

def save_shortcut(shortcut):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO shortcuts (name, description) VALUES (?, ?)",
              (shortcut['name'], shortcut['description']))
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
    if row:
        structure = {"id": row[0], "name": row[1], "content": row[2], "parent_id": row[3]}
        # Fetch child structures
        c.execute("SELECT * FROM knowledge_structures WHERE parent_id = ?", (structure_id,))
        children = [{"id": r[0], "name": r[1], "content": r[2], "parent_id": r[3]} for r in c.fetchall()]
        structure["children"] = children
        conn.close()
        return structure
    conn.close()
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

def update_shortcut_description(shortcut_name, description):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("UPDATE shortcuts SET description = ? WHERE name = ?", (description, shortcut_name))
    conn.commit()
    conn.close()

def save_user_prompt(prompt):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_prompts (id, name, content) VALUES (?, ?, ?)",
              (prompt['id'], prompt['name'], prompt['content']))
    conn.commit()
    conn.close()

def get_user_prompts():
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("SELECT * FROM user_prompts")
    prompts = [{"id": row[0], "name": row[1], "content": row[2]} for row in c.fetchall()]
    conn.close()
    return prompts

def get_user_prompt(prompt_id):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("SELECT * FROM user_prompts WHERE id = ?", (prompt_id,))
    prompt = c.fetchone()
    conn.close()
    return {"id": prompt[0], "name": prompt[1], "content": prompt[2]} if prompt else None

def delete_user_prompt(prompt_id):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("DELETE FROM user_prompts WHERE id = ?", (prompt_id,))
    conn.commit()
    conn.close()

def delete_workflow(workflow_id):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
    conn.commit()
    conn.close()

def get_ollama_models():
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
        if result.returncode == 0:
            models = result.stdout.strip().split('\n')
            return [model.split()[0] for model in models if model]
        else:
            logging.error(f"Failed to fetch Ollama models: {result.stderr}")
            return []
    except Exception as e:
        logging.error(f"Error fetching Ollama models: {str(e)}")
        return []

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
    output_context = {}
    branch_outputs = {}

    def replace_merge_tags(text, context):
        for key, value in context.items():
            text = text.replace(f"{{{{{key}}}}}", str(value))
        return text

    def count_total_steps(steps):
        total = 0
        for step in steps:
            if isinstance(step, dict) and step.get('type') == 'branch':
                total += sum(len(branch) for branch in step['branches'])
            else:
                total += 1
        return total

    total_steps = count_total_steps(workflow['steps'])
    current_step = 0

    for i, step in enumerate(workflow['steps']):
        if isinstance(step, dict) and step.get('type') == 'branch':
            status_queue.put(json.dumps({"status": "running", "step": current_step + 1, "total": total_steps, "message": f"Starting parallel branch with {len(step['branches'])} branches"}))
            
            branch_tasks = []
            for branch_index, branch in enumerate(step['branches']):
                branch_input = {**input_json, 'previous_output': output_context.get('previous_output', '')}
                branch_tasks.append(run_branch(branch, branch_input, status_queue, current_step, total_steps, branch_index))
            
            branch_results = await asyncio.gather(*branch_tasks)
            branch_outputs[f"branch_{i}"] = {f"branch_{j}": result for j, result in enumerate(branch_results)}
            
            current_step += sum(len(branch) for branch in step['branches'])
            status_queue.put(json.dumps({"status": "output", "step": current_step, "total": total_steps, "output": "Parallel branches completed"}))
        
        elif isinstance(step, dict) and step.get('type') == 'merge':
            current_step += 1
            status_queue.put(json.dumps({"status": "running", "step": current_step, "total": total_steps, "message": "Executing merge step"}))
            
            merge_input = {
                **input_json,
                'previous_output': output_context.get('previous_output', ''),
                'branch_outputs': branch_outputs[f"branch_{step['branchStepIndex']}"]
            }
            try:
                output = await run_shortcut(step['shortcutName'], merge_input)
                output_context['previous_output'] = output
                status_queue.put(json.dumps({"status": "output", "step": current_step, "total": total_steps, "output": output}))
            except Exception as e:
                status_queue.put(json.dumps({"status": "error", "step": current_step, "total": total_steps, "message": f"Error in merge step: {str(e)}"}))
                raise
        
        else:
            current_step += 1
            status_queue.put(json.dumps({"status": "running", "step": current_step, "total": total_steps, "message": f"Executing step: {step.get('name', 'Unnamed Step')}"}))
            
            # Combine form inputs and previous outputs
            context = {**input_json, **output_context}
            
            # Replace merge tags in system prompt
            if 'systemPrompt' in step:
                step['systemPrompt'] = replace_merge_tags(step['systemPrompt'], context)

            input_for_step = {
                **input_json,
                'user_input': output_context.get('previous_output', input_json.get('user_input', '')),
                'model': step.get('model', input_json.get('model', '')),
                'shortcut_name': step['shortcutName'],
                'system': step['systemPrompt']
            }

            try:
                output = await run_shortcut(step['shortcutName'], input_for_step)
                output_context['previous_output'] = output
                status_queue.put(json.dumps({"status": "output", "step": current_step, "total": total_steps, "output": output}))
            except Exception as e:
                status_queue.put(json.dumps({"status": "error", "step": current_step, "total": total_steps, "message": f"Error in step {step.get('name', 'Unnamed Step')}: {str(e)}"}))
                raise

    status_queue.put(json.dumps({"status": "completed", "total": total_steps}))
    
async def run_branch(branch_steps, input_json, status_queue, start_step, total_steps, branch_index):
    output_context = {}
    for i, step in enumerate(branch_steps):
        current_step = start_step + i + 1
        status_queue.put(json.dumps({
            "status": "running", 
            "step": current_step, 
            "total": total_steps, 
            "message": f"Executing branch {branch_index + 1}, step {i + 1}: {step.get('name', 'Unnamed Step')}"
        }))
        
        input_for_step = {**input_json, 'previous_output': output_context.get('previous_output', '')}
        try:
            output = await run_shortcut(step['shortcutName'], input_for_step)
            output_context['previous_output'] = output
            status_queue.put(json.dumps({
                "status": "output", 
                "step": current_step, 
                "total": total_steps, 
                "output": output,
                "message": f"Completed branch {branch_index + 1}, step {i + 1}"
            }))
        except Exception as e:
            status_queue.put(json.dumps({
                "status": "error", 
                "step": current_step, 
                "total": total_steps, 
                "message": f"Error in branch {branch_index + 1}, step {i + 1}: {str(e)}"
            }))
            raise
    return output_context['previous_output']

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
        .workflow-step {
            margin-left: 20px;
            border-left: 2px solid #4a5568;
            padding-left: 10px;
            position: relative;
        }
        .workflow-step::before {
            content: '';
            position: absolute;
            top: 0;
            left: -2px;
            width: 10px;
            height: 2px;
            background-color: #4a5568;
        }
        .parallel-branch {
            border: 2px solid #4a5568;
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 10px;
        }
        .parallel-branch::before {
            content: 'Parallel Branch';
            font-weight: bold;
            display: block;
            margin-bottom: 5px;
            color: #4a5568;
        }
        .merge-step {
            background-color: #faf089;
            border: 2px solid #d69e2e;
            border-radius: 8px;
            padding: 10px;
        }
        .merge-step::before {
            content: 'Merge';
            font-weight: bold;
            display: block;
            margin-bottom: 5px;
            color: #d69e2e;
        }
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
            <button class="tab-button bg-blue-500 text-white px-4 py-2 rounded" data-tab="user-prompts">User Prompts</button>
            <button class="tab-button bg-blue-500 text-white px-4 py-2 rounded" data-tab="settings">Settings</button>
            <button class="tab-button bg-blue-500 text-white px-4 py-2 rounded" data-tab="import-workflow">Import Workflow</button>
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
                <div id="step-list" class="space-y-2">
                    <!-- Steps will be dynamically inserted here -->
                </div>
                <div class="mt-4 space-x-2">
                    <button id="add-step" class="bg-blue-500 text-white px-4 py-2 rounded">Add Step</button>
                    <button id="add-branch" class="bg-green-500 text-white px-4 py-2 rounded">Add Branch</button>
                    <button id="add-merge" class="bg-yellow-500 text-white px-4 py-2 rounded">Add Merge</button>
                </div>
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

        <div id="user-prompts" class="tab-content">
            <h2 class="text-2xl font-bold mb-4">User Prompts</h2>
            <div id="user-prompt-list" class="mb-4 space-y-2"></div>
            <input type="text" id="new-prompt-name" class="w-full p-2 mb-2 border rounded" placeholder="New prompt name">
            <textarea id="new-prompt-content" rows="4" class="w-full p-2 mb-2 border rounded" placeholder="New prompt content"></textarea>
            <button id="add-user-prompt" class="bg-green-500 text-white px-4 py-2 rounded">Add User Prompt</button>
        </div>

        <div id="settings" class="tab-content">
            <h2 class="text-2xl font-bold mb-4">Settings</h2>
            <label for="ollama-api-url" class="block mb-2">Ollama API URL:</label>
            <input type="text" id="ollama-api-url" class="w-full p-2 mb-4 border rounded" placeholder="http://localhost:11434">
            <button id="save-settings" class="bg-blue-500 text-white px-4 py-2 rounded">Save Settings</button>
        </div>

        <div id="import-workflow" class="tab-content">
            <h2 class="text-2xl font-bold mb-4">Import Workflow</h2>
            <textarea id="import-data" rows="10" class="w-full p-2 mb-4 border rounded" placeholder="Paste your workflow import data here (JSON format)"></textarea>
            <button id="import-workflow-btn" class="bg-green-500 text-white px-4 py-2 rounded">Import Workflow</button>
        </div>
    </div>

    <script>
        const WorkflowStepTypes = {
            NORMAL: 'normal',
            BRANCH: 'branch',
            MERGE: 'merge'
        };

        let shortcuts = [];
        let userPrompts = [];

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

        function createStepElement(step, index, depth = 0) {
            const stepElement = document.createElement('div');
            stepElement.className = `workflow-step drag-item p-2 bg-gray-200 rounded flex flex-col justify-between items-stretch mb-2 ml-${depth * 4}`;
            
            if (step.type === WorkflowStepTypes.BRANCH) {
                stepElement.className += ' parallel-branch';
                stepElement.innerHTML = `
                    <div class="branch-header mb-2">Parallel Branch (${step.branches.length} branches)</div>
                    <div class="branch-container"></div>
                    <button class="add-branch-step bg-blue-500 text-white px-2 py-1 rounded mt-2">Add Step to Branch</button>
                `;
                const branchContainer = stepElement.querySelector('.branch-container');
                step.branches.forEach((branch, branchIndex) => {
                    const branchElement = document.createElement('div');
                    branchElement.className = 'branch mb-2 p-2 border border-gray-400 rounded';
                    branchElement.innerHTML = `
                        <div class="branch-label mb-2">Branch ${branchIndex + 1}</div>
                        <div class="branch-steps"></div>
                    `;
                    const branchSteps = branchElement.querySelector('.branch-steps');
                    branch.forEach((branchStep, stepIndex) => {
                        branchSteps.appendChild(createStepContent(branchStep, `${index}-${branchIndex}-${stepIndex}`, `Branch ${branchIndex + 1} Step ${stepIndex + 1}`));
                    });
                    branchContainer.appendChild(branchElement);
                });
                
                stepElement.querySelector('.add-branch-step').addEventListener('click', () => {
                    const branchIndex = prompt(`Which branch do you want to add a step to? (1-${step.branches.length})`);
                    if (branchIndex && branchIndex > 0 && branchIndex <= step.branches.length) {
                        step.branches[branchIndex - 1].push({
                            type: WorkflowStepTypes.NORMAL,
                            name: `New Step in Branch ${branchIndex}`,
                            shortcutName: '',
                            model: ''
                        });
                        updateWorkflowDisplay();
                    }
                });
            } else {
                stepElement.appendChild(createStepContent(step, index, step.type === WorkflowStepTypes.MERGE ? 'Merge Step' : 'Step'));
            }
            
            return stepElement;
        }

        function createStepContent(step, index, label) {
            const content = document.createElement('div');
            content.className = 'step-content';
            content.innerHTML = `
                <div class="flex justify-between items-center mb-2">
                    <span>${label}: ${step.name}</span>
                    <button class="remove-step bg-red-500 text-white px-2 py-1 rounded text-sm" data-index="${index}">Remove</button>
                </div>
                <div class="flex flex-col space-y-2">
                    <select class="shortcut-select p-1 border rounded" data-step-index="${index}">
                        <option value="">Select a shortcut</option>
                        <option value="OSUI_Step1" ${step.shortcutName === 'OSUI_Step1' ? 'selected' : ''}>OSUI_Step1</option>
                        <option value="OSUI_StepN" ${step.shortcutName === 'OSUI_StepN' ? 'selected' : ''}>OSUI_StepN</option>
                    </select>
                    <select class="model-select p-1 border rounded" data-step-index="${index}">
                        <option value="">Select a model</option>
                        <option value="gemma2:2b" ${step.model === 'gemma2:2b' ? 'selected' : ''}>Gemma 2B</option>
                        <option value="llama3.1:latest" ${step.model === 'llama3.1:latest' ? 'selected' : ''}>Llama 3.1</option>
                    </select>
                    <textarea class="system-prompt p-1 border rounded" data-step-index="${index}" placeholder="Enter system prompt">${step.systemPrompt || ''}</textarea>
                </div>
            `;

            content.querySelector('.shortcut-select').addEventListener('change', function() {
                updateStepData(index, 'shortcutName', this.value);
            });

            content.querySelector('.model-select').addEventListener('change', function() {
                updateStepData(index, 'model', this.value);
            });

            content.querySelector('.system-prompt').addEventListener('input', function() {
                updateStepData(index, 'systemPrompt', this.value);
            });

            content.querySelector('.remove-step').addEventListener('click', function() {
                removeStep(this.getAttribute('data-index'));
            });

            return content;
        }

        function getUserPromptOptions(selectedPromptId) {
            return `<option value="">No user prompt</option>` + 
                userPrompts.map(prompt => 
                    `<option value="${prompt.id}" ${prompt.id === selectedPromptId ? 'selected' : ''}>${prompt.name}</option>`
                ).join('');
        }

        function loadUserPrompts() {
            fetch('/user-prompts')
                .then(response => response.json())
                .then(data => {
                    userPrompts = data;  // Store the prompts globally
                    const promptList = document.getElementById('user-prompt-list');
                    promptList.innerHTML = '';
                    data.forEach(prompt => {
                        const promptElement = document.createElement('div');
                        promptElement.className = 'p-4 bg-white rounded shadow';
                        promptElement.innerHTML = `
                            <h4 class="font-bold">${prompt.name}</h4>
                            <p class="mt-2">${prompt.content}</p>
                            <button class="edit-prompt mt-2 bg-yellow-500 text-white px-2 py-1 rounded" data-id="${prompt.id}">Edit</button>
                            <button class="delete-prompt mt-2 bg-red-500 text-white px-2 py-1 rounded" data-id="${prompt.id}">Delete</button>
                        `;
                        promptList.appendChild(promptElement);
                    });
                    updateWorkflowDisplay();  // Add this line to refresh the workflow display
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to load user prompts. Please try again.');
                });
        }

        function removeStep(index) {
            const indices = index.split('-').map(Number);
            if (indices.length === 1) {
                currentWorkflow.steps.splice(indices[0], 1);
            } else {
                const [branchIndex, subBranchIndex, stepIndex] = indices;
                currentWorkflow.steps[branchIndex].branches[subBranchIndex].splice(stepIndex, 1);
                if (currentWorkflow.steps[branchIndex].branches[subBranchIndex].length === 0) {
                    currentWorkflow.steps[branchIndex].branches.splice(subBranchIndex, 1);
                }
                if (currentWorkflow.steps[branchIndex].branches.length === 0) {
                    currentWorkflow.steps.splice(branchIndex, 1);
                }
            }
            updateWorkflowDisplay();
        }

        function getShortcutOptions(selectedShortcutName) {
            if (!Array.isArray(shortcuts)) {
                console.error('Shortcuts is not an array:', shortcuts);
                return '';
            }
            return shortcuts.map(shortcut => 
                `<option value="${shortcut.name}" ${shortcut.name === selectedShortcutName ? 'selected' : ''}>${shortcut.name}</option>`
            ).join('');
        }

        function getOllamaModelOptions(selectedmodel) {
            return ollamaModels.map(model => 
                `<option value="${model}" ${model === selectedmodel ? 'selected' : ''}>${model}</option>`
            ).join('');
        }

        function updateWorkflowDisplay() {
            const stepList = document.getElementById('step-list');
            stepList.innerHTML = '';

            currentWorkflow.steps.forEach((step, index) => {
                stepList.appendChild(createStepElement(step, index));
            });

            // Add event listeners for shortcut, model, and user prompt selection changes
            stepList.querySelectorAll('.shortcut-select, .model-select, .user-prompt-select').forEach(select => {
                select.addEventListener('change', (e) => {
                    const stepIndex = e.target.getAttribute('data-step-index');
                    const property = e.target.classList.contains('shortcut-select') ? 'shortcutName' :
                                    e.target.classList.contains('model-select') ? 'model' : 'userPromptId';
                    updateStepData(stepIndex, property, e.target.value);
                });
            });

            // Initialize drag-and-drop functionality
            new Sortable(stepList, {
                animation: 150,
                ghostClass: 'sortable-ghost',
                onEnd: function(evt) {
                    const newIndex = evt.newIndex;
                    const oldIndex = evt.oldIndex;
                    const movedStep = currentWorkflow.steps.splice(oldIndex, 1)[0];
                    currentWorkflow.steps.splice(newIndex, 0, movedStep);
                    updateWorkflowDisplay();
                }
            });
        }

        function updateStepData(stepIndex, property, value) {
            const indices = typeof stepIndex === 'string' ? stepIndex.split('-').map(Number) : [stepIndex];
            let step = currentWorkflow.steps[indices[0]];
            if (indices.length > 1) { // It's a step within a branch
                step = step.branches[indices[1]][indices[2]];
            }
            step[property] = value;
        }

        function addNormalStep() {
            const stepName = prompt("Enter step name:");
            if (stepName) {
                currentWorkflow.steps.push({ 
                    type: WorkflowStepTypes.NORMAL, 
                    name: stepName,
                    shortcutName: '',
                    model: ''
                });
                updateWorkflowDisplay();
            }
        }

        function addBranchStep() {
            const branchCount = prompt("How many branches do you want to create?", "2");
            const count = parseInt(branchCount);
            if (isNaN(count) || count < 2) {
                alert("Please enter a valid number of branches (2 or more)");
                return;
            }
            
            const newBranch = {
                type: WorkflowStepTypes.BRANCH,
                branches: Array(count).fill().map(() => [])
            };
            
            currentWorkflow.steps.push(newBranch);
            updateWorkflowDisplay();
        }


        function addMergeStep() {
            const mergeName = prompt("Enter merge step name:");
            if (mergeName) {
                const lastBranchIndex = currentWorkflow.steps.map(step => step.type).lastIndexOf(WorkflowStepTypes.BRANCH);
                if (lastBranchIndex !== -1) {
                    currentWorkflow.steps.push({ 
                        type: WorkflowStepTypes.MERGE, 
                        name: mergeName, 
                        branchStepIndex: lastBranchIndex,
                        shortcutName: '',
                        model: ''
                    });
                    updateWorkflowDisplay();
                } else {
                    alert("You need to add a branch step before adding a merge step.");
                }
            }
        }

        function deleteWorkflow(workflowId) {
            if (confirm('Are you sure you want to delete this workflow?')) {
                fetch(`/delete-workflow/${workflowId}`, { method: 'DELETE' })
                    .then(response => response.json())
                    .then(data => {
                        alert(data.message);
                        loadWorkflows();  // Refresh the workflow list
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Failed to delete workflow. Please try again.');
                    });
            }
        }

        // Event listeners for the add step buttons
        document.getElementById('add-step').addEventListener('click', addNormalStep);
        document.getElementById('add-branch').addEventListener('click', addBranchStep);
        document.getElementById('add-merge').addEventListener('click', addMergeStep);

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
                        currentWorkflow.form_definition = currentWorkflow.form_definition || [];
                        document.getElementById('workflow-name').value = currentWorkflow.name || '';
                        updateWorkflowDisplay();
                        updateWorkflowForm();
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Failed to load workflow. Please try again.');
                    });
            } else {
                currentWorkflow = { id: '', name: 'New Workflow', steps: [], form_definition: [] };
                document.getElementById('workflow-name').value = '';
                updateWorkflowDisplay();
                updateWorkflowForm();
            }
        });

        function updateWorkflowForm() {
            const formContainer = document.getElementById('workflow-form');
            formContainer.innerHTML = '';

            if (currentWorkflow && currentWorkflow.form_definition) {
                currentWorkflow.form_definition.forEach((field, index) => {
                    if (field && typeof field === 'object') {
                        const fieldDiv = document.createElement('div');
                        fieldDiv.className = 'form-field';

                        const label = document.createElement('label');
                        label.textContent = field.label || `Field ${index + 1}`;
                        fieldDiv.appendChild(label);

                        let input;
                        switch (field.type) {
                            case 'textarea':
                                input = document.createElement('textarea');
                                break;
                            case 'select':
                                input = document.createElement('select');
                                if (Array.isArray(field.options)) {
                                    field.options.forEach(option => {
                                        const optionElement = document.createElement('option');
                                        optionElement.value = option;
                                        optionElement.textContent = option;
                                        input.appendChild(optionElement);
                                    });
                                }
                                break;
                            default:
                                input = document.createElement('input');
                                input.type = field.type || 'text';
                        }

                        input.name = field.name || `field_${index}`;
                        input.id = `form_${input.name}`;
                        fieldDiv.appendChild(input);

                        const removeButton = createRemoveButton(() => {
                            currentWorkflow.form_definition.splice(index, 1);
                            updateWorkflowForm();
                        });
                        fieldDiv.appendChild(removeButton);

                        formContainer.appendChild(fieldDiv);
                    }
                });
            }

            // Add new field button
            const addButton = document.createElement('button');
            addButton.textContent = 'Add Field';
            addButton.onclick = () => {
                if (!currentWorkflow.form_definition) {
                    currentWorkflow.form_definition = [];
                }
                currentWorkflow.form_definition.push({ type: 'text', label: '', name: '' });
                updateWorkflowForm();
            };
            formContainer.appendChild(addButton);
        }

        function runWorkflow(workflowId, inputJson) {
            console.log('Running workflow:', workflowId);
            console.log('Input JSON:', inputJson);

            const statusElement = document.getElementById('workflow-status');
            const progressBar = statusElement.querySelector('.progress-bar-fill');
            const statusText = statusElement.querySelector('.status-text');
            const stepOutputs = statusElement.querySelector('.step-outputs');

            statusElement.style.display = 'block';
            progressBar.style.width = '0%';
            statusText.textContent = 'Initializing workflow...';
            stepOutputs.innerHTML = '';

            // Collect all form data
            const formData = {};
            const formElement = document.getElementById(`workflow-form-${workflowId}`);
            if (formElement) {
                formElement.querySelectorAll('input, select, textarea').forEach(element => {
                    if (element.type === 'select-multiple') {
                        formData[element.name] = Array.from(element.selectedOptions).map(option => ({
                            id: option.value,
                            name: option.textContent
                        }));
                    } else {
                        formData[element.name] = element.value;
                    }
                });
            }

            // Combine all input data
            const completeInputJson = {
                ...inputJson,
                ...formData,
                model: document.querySelector('.model-select').value, // Ensure model is always included
                workflow_steps: currentWorkflow.steps
            };

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
                        <pre class="whitespace-pre-wrap">${data.output}</pre>
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

        // Event listener for running the workflow
        document.getElementById('run-workflow').addEventListener('click', () => {
            const workflowId = currentWorkflow.id;
            const inputJson = {
                workflow_steps: currentWorkflow.steps,
                user_input: document.getElementById('workflow-input').value
            };
            
            // Add form data if exists
            const formElement = document.getElementById('workflow-form');
            if (formElement) {
                const formData = new FormData(formElement);
                for (let [key, value] of formData.entries()) {
                    inputJson[key] = value;
                }
            }
            
            runWorkflow(workflowId, inputJson);
        });

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
                            <button class="run-workflow bg-blue-500 text-white px-4 py-2 rounded mr-2" data-id="${workflow.id}">Run Workflow</button>
                            <button class="delete-workflow bg-red-500 text-white px-4 py-2 rounded" data-id="${workflow.id}">Delete Workflow</button>
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

                    // Add event listeners after all elements have been added to the DOM
                    document.querySelectorAll('.delete-workflow').forEach(button => {
                        button.addEventListener('click', (e) => {
                            deleteWorkflow(e.target.getAttribute('data-id'));
                        });
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
                    case 'dropdown':
                        inputElement = document.createElement('select');
                        if (Array.isArray(field.options)) {
                            field.options.forEach(option => {
                                const optionElement = document.createElement('option');
                                optionElement.value = option;
                                optionElement.textContent = option;
                                if (field.type === 'dropdown' && option === field.default) {
                                    optionElement.selected = true;
                                }
                                inputElement.appendChild(optionElement);
                            });
                        }
                        break;
                    case 'knowledge-structure':
                        inputElement = document.createElement('select');
                        inputElement.multiple = true;
                        // Populate with knowledge structures
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
                        shortcuts = data;
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
                        updateWorkflowDisplay();
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
            const shortcutName = JSON.parse(document.getElementById('shortcut-dropdown').value).id;
            const description = document.getElementById('shortcut-description').value;
            fetch('/update-shortcut-description', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: shortcutName, description: description })
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

            // Get the selected user prompt
            const userPromptSelect = document.querySelector('.user-prompt-select');
            const selectedPromptId = userPromptSelect ? userPromptSelect.value : '';

            if (selectedPromptId) {
                const selectedPrompt = userPrompts.find(prompt => prompt.id === selectedPromptId);
                if (selectedPrompt) {
                    inputJson.user_prompt = selectedPrompt.content;
                }
            }

            fetch(`/run-shortcut/${encodeURIComponent(shortcutName)}?input=${encodeURIComponent(JSON.stringify(inputJson))}`)
                .then(response => response.json())
                .then(data => {
                    statusText.textContent = 'Shortcut completed';
                    outputElement.textContent = data.result;
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

        document.getElementById('workflow-select').addEventListener('change', (e) => {
            if (e.target.value) {
                fetch(`/get-workflow/${e.target.value}`)
                    .then(response => response.json())
                    .then(data => {
                        currentWorkflow = {
                            id: data.id || '',
                            name: data.name || 'Unnamed Workflow',
                            steps: data.steps || [],
                            form_definition: data.form_definition || []
                        };
                        document.getElementById('workflow-name').value = currentWorkflow.name;
                        updateWorkflowDisplay();
                        updateWorkflowForm();
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Failed to load workflow. Please try again.');
                    });
            } else {
                currentWorkflow = { id: '', name: 'New Workflow', steps: [], form_definition: [] };
                document.getElementById('workflow-name').value = currentWorkflow.name;
                updateWorkflowDisplay();
                updateWorkflowForm();
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
                    <select class="w-full p-2 mb-2 border rounded field-type-select">
                        <option value="text" ${field.type === 'text' ? 'selected' : ''}>Text</option>
                        <option value="number" ${field.type === 'number' ? 'selected' : ''}>Number</option>
                        <option value="textarea" ${field.type === 'textarea' ? 'selected' : ''}>Textarea</option>
                        <option value="select" ${field.type === 'select' ? 'selected' : ''}>Select</option>
                        <option value="dropdown" ${field.type === 'dropdown' ? 'selected' : ''}>Dropdown</option>
                        <option value="knowledge-structure" ${field.type === 'knowledge-structure' ? 'selected' : ''}>Knowledge Structure</option>
                    </select>
                    <input type="text" class="w-full p-2 mb-2 border rounded" value="${field.name}" placeholder="Field Name">
                    ${field.type === 'select' || field.type === 'dropdown' ? `<input type="text" class="w-full p-2 mb-2 border rounded options-input" value="${field.options ? field.options.join(',') : ''}" placeholder="Options (comma-separated)">` : ''}
                    ${field.type === 'dropdown' ? `<input type="text" class="w-full p-2 mb-2 border rounded" value="${field.default || ''}" placeholder="Default Value">` : ''}
                    <button class="remove-field bg-red-500 text-white px-2 py-1 rounded" data-index="${index}">Remove</button>
                `;
                formFields.appendChild(fieldElement);
            });
        }


        document.getElementById('form-fields').addEventListener('change', (e) => {
            if (e.target.classList.contains('field-type-select')) {
                const fieldElement = e.target.closest('div');
                const optionsInput = fieldElement.querySelector('.options-input');
                const defaultValueInput = fieldElement.querySelector('input[placeholder="Default Value"]');
                
                if (e.target.value === 'select' || e.target.value === 'dropdown') {
                    if (!optionsInput) {
                        const newOptionsInput = document.createElement('input');
                        newOptionsInput.type = 'text';
                        newOptionsInput.className = 'w-full p-2 mb-2 border rounded options-input';
                        newOptionsInput.placeholder = 'Options (comma-separated)';
                        e.target.insertAdjacentElement('afterend', newOptionsInput);
                    }
                    if (e.target.value === 'dropdown' && !defaultValueInput) {
                        const newDefaultValueInput = document.createElement('input');
                        newDefaultValueInput.type = 'text';
                        newDefaultValueInput.className = 'w-full p-2 mb-2 border rounded';
                        newDefaultValueInput.placeholder = 'Default Value';
                        fieldElement.insertBefore(newDefaultValueInput, fieldElement.lastElementChild);
                    }
                } else {
                    if (optionsInput) optionsInput.remove();
                    if (defaultValueInput) defaultValueInput.remove();
                }
            }
        });

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
                    const options = type === 'select' || type === 'dropdown' ? field.querySelector('input[placeholder="Options (comma-separated)"]').value.split(',').map(opt => opt.trim()) : undefined;
                    const defaultValue = type === 'dropdown' ? field.querySelector('input[placeholder="Default Value"]').value : undefined;
                    return { label, type, name, options, default: defaultValue };
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

        function getOllamaModelOptions() {
            return ollamaModels.map(model => `<option value="${model}">${model}</option>`).join('');
        }

        let ollamaModels = [];
        fetch('/ollama-models')
            .then(response => response.json())
            .then(data => {
                ollamaModels = data;
                updateWorkflowDisplay();
            })
            .catch(error => {
                console.error('Error fetching Ollama models:', error);
                ollamaModels = ['Error fetching models'];
                updateWorkflowDisplay();
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

        // User Prompts functionality
        function loadUserPrompts() {
            fetch('/user-prompts')
                .then(response => response.json())
                .then(data => {
                    const promptList = document.getElementById('user-prompt-list');
                    promptList.innerHTML = '';
                    data.forEach(prompt => {
                        const promptElement = document.createElement('div');
                        promptElement.className = 'p-4 bg-white rounded shadow';
                        promptElement.innerHTML = `
                            <h4 class="font-bold">${prompt.name}</h4>
                            <p class="mt-2">${prompt.content}</p>
                            <button class="edit-prompt mt-2 bg-yellow-500 text-white px-2 py-1 rounded" data-id="${prompt.id}">Edit</button>
                            <button class="delete-prompt mt-2 bg-red-500 text-white px-2 py-1 rounded" data-id="${prompt.id}">Delete</button>
                        `;
                        promptList.appendChild(promptElement);
                    });
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to load user prompts. Please try again.');
                });
        }

        document.getElementById('add-user-prompt').addEventListener('click', () => {
            const name = document.getElementById('new-prompt-name').value;
            const content = document.getElementById('new-prompt-content').value;
            if (name && content) {
                fetch('/save-user-prompt', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: null, name, content })
                })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    loadUserPrompts();  // This will refresh the user prompt list
                    updateWorkflowDisplay();  // This will update the workflow composer
                    document.getElementById('new-prompt-name').value = '';
                    document.getElementById('new-prompt-content').value = '';
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to add user prompt. Please try again.');
                });
            } else {
                alert('Please enter both name and content for the user prompt');
            }
        });

        document.getElementById('user-prompt-list').addEventListener('click', (e) => {
            if (e.target.classList.contains('edit-prompt')) {
                const promptId = e.target.getAttribute('data-id');
                // Implement edit functionality (you can use a modal or inline editing)
            } else if (e.target.classList.contains('delete-prompt')) {
                const promptId = e.target.getAttribute('data-id');
                if (confirm('Are you sure you want to delete this user prompt?')) {
                    fetch(`/delete-user-prompt/${promptId}`, { method: 'DELETE' })
                        .then(response => response.json())
                        .then(data => {
                            alert(data.message);
                            loadUserPrompts();  // This will refresh the user prompt list
                            updateWorkflowDisplay();  // This will update the workflow composer
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            alert('Failed to delete user prompt. Please try again.');
                        });
                }
            }
        });

        document.getElementById('import-workflow-btn').addEventListener('click', () => {
            const importData = document.getElementById('import-data').value;
            try {
                const parsedData = JSON.parse(importData);
                fetch('/import-workflow', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(parsedData)
                })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert('Error: ' + data.error);
                    } else {
                        alert(data.message);
                        loadWorkflows();  // Refresh the workflow list
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to import workflow. Please try again.');
                });
            } catch (error) {
                alert('Invalid JSON format. Please check your import data.');
            }
        });

        document.addEventListener('DOMContentLoaded', function() {
            function init() {
                loadShortcuts();
                loadWorkflows();
                loadKnowledgeStructures();
                loadUserPrompts();
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
        elif self.path == '/ollama-models':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            models = get_ollama_models()
            self.wfile.write(json.dumps(models).encode())
        elif self.path == '/user-prompts':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_user_prompts()).encode())
        elif self.path.startswith('/user-prompt/'):
            prompt_id = self.path.split('/')[-1]
            prompt = get_user_prompt(prompt_id)
            if prompt:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(prompt).encode())
            else:
                self.send_response(404)
                self.end_headers()
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
                    for field in data:
                        if field['type'] in ['select', 'dropdown']:
                            field['options'] = field['options'].split(',') if isinstance(field['options'], str) else field['options']
                            field['default'] = field.get('default', '')
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
                update_shortcut_description(data['name'], data['description'])
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
        elif self.path == '/save-user-prompt':
            try:
                save_user_prompt(data)
                self.wfile.write(json.dumps({"message": "User prompt saved successfully"}).encode())
            except Exception as e:
                logging.error(f"Error saving user prompt: {str(e)}")
                self.wfile.write(json.dumps({"error": "Failed to save user prompt"}).encode())
        elif self.path == '/import-workflow':
            try:
                imported_workflow = parse_imported_workflow(data)
                save_workflow(imported_workflow)
                self.wfile.write(json.dumps({"message": "Workflow imported successfully"}).encode())
            except Exception as e:
                logging.error(f"Error importing workflow: {str(e)}")
                self.wfile.write(json.dumps({"error": str(e)}).encode())
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
        elif self.path.startswith('/delete-user-prompt/'):
            prompt_id = self.path.split('/')[-1]
            try:
                delete_user_prompt(prompt_id)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"message": "User prompt deleted successfully"}).encode())
            except Exception as e:
                logging.error(f"Error deleting user prompt: {str(e)}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Failed to delete user prompt"}).encode())
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
