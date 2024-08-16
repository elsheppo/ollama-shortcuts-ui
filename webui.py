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
from urllib.parse import unquote_plus

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
    conn.commit()
    conn.close()

def get_workflows():
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("SELECT * FROM workflows")
    workflows = [{"id": row[0], "name": row[1], "steps": json.loads(row[2])} for row in c.fetchall()]
    conn.close()
    return workflows

def save_workflow(workflow):
    conn = sqlite3.connect('ollama_workflows.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO workflows (id, name, steps) VALUES (?, ?, ?)",
              (workflow['id'], workflow['name'], json.dumps(workflow['steps'])))
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

def get_user_shortcuts():
    try:
        result = subprocess.run(['shortcuts', 'list'], capture_output=True, text=True)
        shortcuts = result.stdout.strip().split('\n')
        return [{"id": str(uuid.uuid4()), "name": s, "description": f"User shortcut"} for s in shortcuts if s]
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
async def run_shortcut(shortcut_name, input_text):
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
        temp_file.write(input_text)
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

async def run_workflow(workflow, input_text, status_queue):
    for i, step in enumerate(workflow['steps']):
        status_queue.put(json.dumps({"status": "running", "step": i + 1, "total": len(workflow['steps'])}))
        if isinstance(step, list):  # Parallel branch
            tasks = [run_shortcut(s['name'], input_text) for s in step]
            outputs = await asyncio.gather(*tasks)
            status_queue.put(json.dumps({"status": "output", "step": i + 1, "output": outputs}))
        else:
            output = await run_shortcut(step['name'], input_text)
            status_queue.put(json.dumps({"status": "output", "step": i + 1, "output": output}))
        input_text = output  # Use the output of the previous step as input for the next step
    status_queue.put(json.dumps({"status": "completed"}))

def workflow_runner(workflow, input_text, status_queue):
    asyncio.run(run_workflow(workflow, input_text, status_queue))

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ollama Workflow Master</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f4f4f4;
        }
        h1, h2 {
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: auto;
            overflow: hidden;
            padding: 0 20px;
        }
        .tab-content {
            display: none;
            background: #fff;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .tab-content.active {
            display: block;
        }
        .tabs {
            margin-bottom: 20px;
        }
        .tab-button {
            background: #333;
            color: #fff;
            border: none;
            padding: 10px 20px;
            cursor: pointer;
            margin-right: 5px;
        }
        .tab-button:hover {
            background: #444;
        }
        .workflow-step, .parallel-branch {
            background-color: #f0f0f0;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
        }
        .workflow-step button, .parallel-branch button {
            margin-left: 10px;
            background: #d9534f;
            color: #fff;
            border: none;
            padding: 5px 10px;
            cursor: pointer;
        }
        input[type="text"], select, textarea {
            width: 100%;
            padding: 8px;
            margin-bottom: 10px;
        }
        button {
            background: #5cb85c;
            color: #fff;
            border: none;
            padding: 10px 20px;
            cursor: pointer;
        }
        button:hover {
            background: #4cae4c;
        }
        #shortcut-list, #shortcut-details {
            margin-top: 20px;
        }
        #workflow-status, #shortcut-status {
            margin-top: 20px;
            padding: 10px;
            background-color: #e9ecef;
            border-radius: 5px;
        }
        .progress-bar {
            width: 100%;
            background-color: #e0e0e0;
            padding: 3px;
            border-radius: 3px;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, .2);
        }
        .progress-bar-fill {
            display: block;
            height: 22px;
            background-color: #659cef;
            border-radius: 3px;
            transition: width 500ms ease-in-out;
        }
        .step-output {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            padding: 10px;
            margin-top: 10px;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Ollama Workflow Master</h1>
        
        <div class="tabs">
            <button class="tab-button" data-tab="dashboard">Dashboard</button>
            <button class="tab-button" data-tab="workflows">Workflows</button>
            <button class="tab-button" data-tab="shortcuts">Shortcuts</button>
            <button class="tab-button" data-tab="formbuilder">Form Builder</button>
            <button class="tab-button" data-tab="settings">Settings</button>
        </div>

        <div id="dashboard" class="tab-content">
            <h2>Workflow Dashboard</h2>
            <div id="workflow-list"></div>
            <div id="workflow-status" style="display: none;">
                <h3>Workflow Status</h3>
                <div class="progress-bar">
                    <span class="progress-bar-fill" style="width: 0%;"></span>
                </div>
                <p id="status-text"></p>
                <div id="step-outputs"></div>
            </div>
        </div>

        <div id="workflows" class="tab-content">
            <h2>Workflow Composer</h2>
            <input type="text" id="workflow-name" placeholder="Workflow name">
            <textarea id="workflow-input" placeholder="Enter input text for the workflow"></textarea>
            <select id="shortcut-select">
                <option value="">Add step</option>
            </select>
            <div id="current-workflow"></div>
            <button id="add-parallel">Add Parallel Branch</button>
            <button id="save-workflow">Save Workflow</button>
            <button id="run-workflow">Run Workflow</button>
        </div>

        <div id="shortcuts" class="tab-content">
            <h2>Shortcut Library</h2>
            <div id="shortcut-list">
                <select id="shortcut-dropdown">
                    <option value="">Select a shortcut</option>
                </select>
            </div>
            <div id="shortcut-details">
                <h3 id="shortcut-name"></h3>
                <textarea id="shortcut-description" rows="4" cols="50"></textarea>
                <textarea id="shortcut-input" placeholder="Enter input text for the shortcut"></textarea>
                <button id="update-description">Update Description</button>
                <button id="run-shortcut">Run Shortcut</button>
            </div>
            <button id="refresh-shortcuts">Refresh Shortcuts</button>
            <div id="shortcut-status" style="display: none;">
                <h3>Shortcut Status</h3>
                <p id="shortcut-status-text"></p>
                <div id="shortcut-output" class="step-output"></div>
            </div>
        </div>

        <div id="formbuilder" class="tab-content">
            <h2>Input Form Builder</h2>
            <input type="text" id="new-field-name" placeholder="New field name">
            <button id="add-field">Add Field</button>
            <div id="form-fields"></div>
        </div>

        <div id="settings" class="tab-content">
            <h2>Settings</h2>
            <label for="ollama-api-url">Ollama API URL:</label>
            <input type="text" id="ollama-api-url" placeholder="http://localhost:11434">
            <button id="save-settings">Save Settings</button>
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
                    content.classList.remove('active');
                });
                document.getElementById(tabName).classList.add('active');
            });
        });

        // Workflow functionality
        let currentWorkflow = { name: '', steps: [] };

        function updateWorkflowDisplay() {
            const workflowDisplay = document.getElementById('current-workflow');
            workflowDisplay.innerHTML = '';
            currentWorkflow.steps.forEach((step, index) => {
                const stepElement = document.createElement('div');
                if (Array.isArray(step)) {
                    stepElement.className = 'parallel-branch';
                    step.forEach((parallelStep, parallelIndex) => {
                        const parallelStepElement = document.createElement('div');
                        parallelStepElement.className = 'workflow-step';
                        parallelStepElement.textContent = parallelStep.name;
                        const removeButton = document.createElement('button');
                        removeButton.textContent = 'Remove';
                        removeButton.onclick = () => {
                            step.splice(parallelIndex, 1);
                            if (step.length === 0) {
                                currentWorkflow.steps.splice(index, 1);
                            }
                            updateWorkflowDisplay();
                        };
                        parallelStepElement.appendChild(removeButton);
                        stepElement.appendChild(parallelStepElement);
                    });
                } else {
                    stepElement.className = 'workflow-step';
                    stepElement.textContent = step.name;
                    const removeButton = document.createElement('button');
                    removeButton.textContent = 'Remove';
                    removeButton.onclick = () => {
                        currentWorkflow.steps.splice(index, 1);
                        updateWorkflowDisplay();
                    };
                    stepElement.appendChild(removeButton);
                }
                workflowDisplay.appendChild(stepElement);
            });
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
                    currentWorkflow = { name: '', steps: [] };
                    document.getElementById('workflow-name').value = '';
                    updateWorkflowDisplay();
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

        document.getElementById('run-workflow').addEventListener('click', () => {
            const workflowName = document.getElementById('workflow-name').value;
            const inputText = document.getElementById('workflow-input').value;
            if (workflowName && inputText) {
                runWorkflow(currentWorkflow.id, inputText);
            } else {
                alert('Please enter a workflow name and input text');
            }
        });

        function loadWorkflows() {
            fetch('/workflows')
                .then(response => response.json())
                .then(data => {
                    const workflowList = document.getElementById('workflow-list');
                    workflowList.innerHTML = '';
                    data.forEach(workflow => {
                        const workflowElement = document.createElement('div');
                        workflowElement.innerHTML = `
                            <h3>${workflow.name}</h3>
                            <p>${JSON.stringify(workflow.steps)}</p>
                            <textarea id="workflow-input-${workflow.id}" placeholder="Enter input text for the workflow"></textarea>
                            <button onclick="runWorkflow('${workflow.id}', document.getElementById('workflow-input-${workflow.id}').value)">Run Workflow</button>
                        `;
                        workflowList.appendChild(workflowElement);
                    });
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to load workflows. Please try again.');
                });
        }

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
                loadShortcuts();  // Reload shortcuts to reflect the updated description
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
                runShortcut(shortcutName, inputText);
            } else {
                alert('Please select a shortcut and enter input text');
            }
        });

        function runWorkflow(workflowId, inputText) {
            const statusElement = document.getElementById('workflow-status');
            const progressBar = document.querySelector('.progress-bar-fill');
            const statusText = document.getElementById('status-text');
            const stepOutputs = document.getElementById('step-outputs');

            statusElement.style.display = 'block';
            progressBar.style.width = '0%';
            statusText.textContent = 'Initializing workflow...';
            stepOutputs.innerHTML = '';

            const eventSource = new EventSource(`/run-workflow/${workflowId}?input=${encodeURIComponent(inputText)}`);

            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.status === 'running') {
                    const progress = (data.step / data.total) * 100;
                    progressBar.style.width = `${progress}%`;
                    statusText.textContent = `Running step ${data.step} of ${data.total}`;
                } else if (data.status === 'output') {
                    const outputElement = document.createElement('div');
                    outputElement.className = 'step-output';
                    outputElement.innerHTML = `<strong>Step ${data.step} Output:</strong><br>${data.output}`;
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

        function runShortcut(shortcutName, inputText) {
            const statusElement = document.getElementById('shortcut-status');
            const statusText = document.getElementById('shortcut-status-text');
            const outputElement = document.getElementById('shortcut-output');

            statusElement.style.display = 'block';
            statusText.textContent = 'Running shortcut...';
            outputElement.textContent = '';

            fetch(`/run-shortcut/${encodeURIComponent(shortcutName)}?input=${encodeURIComponent(inputText)}`)
                .then(response => response.json())
                .then(data => {
                    statusText.textContent = 'Shortcut completed';
                    outputElement.textContent = data.result;
                })
                .catch(error => {
                    console.error('Error:', error);
                    statusText.textContent = 'Error running shortcut';
                    outputElement.textContent = 'An error occurred while running the shortcut.';
                });
        }

        // Form builder functionality
        let formFields = [];

        document.getElementById('add-field').addEventListener('click', () => {
            const fieldName = document.getElementById('new-field-name').value;
            if (fieldName) {
                formFields.push({ name: fieldName, value: '' });
                updateFormFields();
                document.getElementById('new-field-name').value = '';
            }
        });

        function updateFormFields() {
            const formFieldsContainer = document.getElementById('form-fields');
            formFieldsContainer.innerHTML = '';
            formFields.forEach((field, index) => {
                const fieldElement = document.createElement('div');
                fieldElement.innerHTML = `
                    <input type="text" value="${field.name}" readonly>
                    <input type="text" value="${field.value}" onchange="updateFieldValue(${index}, this.value)">
                    <button onclick="removeField(${index})">Remove</button>
                `;
                formFieldsContainer.appendChild(fieldElement);
            });
        }

        function updateFieldValue(index, value) {
            formFields[index].value = value;
        }

        function removeField(index) {
            formFields.splice(index, 1);
            updateFormFields();
        }

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

        // Initial load
        loadWorkflows();
        loadShortcuts();

        // Set dashboard as the initial active tab
        document.querySelector('[data-tab="dashboard"]').click();
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
        elif self.path == '/shortcuts':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_shortcuts()).encode())
        elif self.path.startswith('/run-workflow/'):
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()

            workflow_id = self.path.split('/')[2].split('?')[0]
            input_text = unquote_plus(self.path.split('=')[1])
            workflow = next((w for w in get_workflows() if w['id'] == workflow_id), None)
            if workflow:
                status_queue = Queue()
                threading.Thread(target=workflow_runner, args=(workflow, input_text, status_queue)).start()
                
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
            input_text = unquote_plus(self.path.split('=')[1])
            try:
                result = asyncio.run(run_shortcut(shortcut_name, input_text))
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

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, OllamaHandler)
    print(f'Server running on http://localhost:{port}')
    httpd.serve_forever()

if __name__ == '__main__':
    init_db()
    init_shortcuts()  # Initialize shortcuts on startup
    run_server()