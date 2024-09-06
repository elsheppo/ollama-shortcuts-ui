Paste this workflow into Claude 3.5 Sonnet and tell it about the workflow you want to design. Sometimes it may have an issue where it structures system prompts incorrectly with multi-line text. You can correct it by telling it to put the system prompt on a single line with no line breaks.

The workflow you get with this will be a linear workflow (no branching / merging) that you can run in OSUI.

----

# Executable Ontology: OSUI Workflow Import Design

## Fundamental Definitions

1. OSUI (Ollama Shortcuts UI):
   - Definition: A user interface system designed to create, manage, and execute AI-driven workflows using the Ollama framework.
   - Purpose: To provide a user-friendly environment for leveraging AI models in task automation and decision-making processes.
   - Key Feature: Ability to import custom workflows in a specific JSON format.

2. Workflow:
   - Definition: A sequence of interconnected steps designed to accomplish a specific task or goal using AI models and predefined shortcuts.
   - Structure: Composed of metadata, form definitions, and a series of executable steps.

3. Ollama:
   - Definition: An open-source framework for running and managing large language models locally.
   - Relevance: Provides the underlying AI capabilities that OSUI leverages in its workflows.

## Purpose of This Ontology
To serve as a comprehensive, self-contained guide for creating importable OSUI workflows on any given topic, ensuring full adherence to all technical requirements, best practices, and leaving no room for ambiguity or external knowledge requirements.

## Domain Knowledge

### OSUI System Architecture
1. Component Hierarchy:
   - OSUI (top-level interface)
     - Workflow Manager
       - Individual Workflows
         - Steps (atomic units of workflow execution)

2. Data Flow:
   - User Input → Form Definition → Workflow Steps → AI Models → Output

3. Execution Engine:
   - Interprets JSON workflow definitions
   - Manages step sequencing
   - Interfaces with Ollama for AI model execution

4. Import Mechanism:
   - Accepts JSON-formatted workflow definitions
   - Validates structure and content against predefined schemas
   - Integrates new workflows into the OSUI environment

### Workflow Components (Expanded)
1. Metadata:
   - id: 
     - Type: String
     - Format: Typically "topic-purpose-XXX" where XXX is a unique identifier
     - Purpose: Uniquely identifies the workflow within the OSUI system
   - name:
     - Type: String
     - Max Length: Recommended 50 characters
     - Purpose: Human-readable identifier for the workflow
   - version:
     - Type: String
     - Format: Semantic versioning (e.g., "1.0.0")
     - Purpose: Tracks iterations and updates to the workflow
   - import_format:
     - Type: String
     - Allowed Value: "json" (lowercase)
     - Purpose: Specifies the format of the workflow definition
   - description:
     - Type: String
     - Recommended Length: 50-200 characters
     - Purpose: Provides a brief explanation of the workflow's function and use case

2. Form Definition:
   - Structure: Array of input field objects
   - Purpose: Defines user inputs required for workflow execution
   - Field Types:
     a. text:
        - Properties: label, name, placeholder (optional)
        - Use Case: Short, single-line text inputs
     b. textarea:
        - Properties: label, name, placeholder (optional)
        - Use Case: Longer, multi-line text inputs
     c. select:
        - Properties: label, name, options (array of strings)
        - Use Case: Single selection from predefined options
     d. number:
        - Properties: label, name, min (optional), max (optional)
        - Use Case: Numeric inputs, optionally within a specified range

3. Steps:
   - Structure: Array of step objects
   - Type:
     a. normal:
        - Purpose: Standard sequential execution
        - Properties: id, name, type, shortcutName, model, systemPrompt
   - Common Properties:
     - id:
       - Type: String
       - Format: Typically "stepX" where X is a number
     - name:
       - Type: String
       - Purpose: Descriptive name of the step's function
     - type:
       - Type: String
       - Allowed Value: "normal"
     - shortcutName:
       - Type: String
       - Allowed Values: "OSUI_Step1" (first step only), "OSUI_StepN" (all subsequent steps)
     - model:
       - Type: String
       - Allowed Values: "gemma2:2b", "llama3.1:latest"
     - systemPrompt:
       - Type: String
       - Purpose: Instructions for the AI model
       - Constraints: Must not contain merge tags or variables

### Technical Constraints and Best Practices
1. JSON Structure:
   - Must be valid JSON format
   - All required fields must be present
   - Field names are case-sensitive

2. Shortcut Naming Convention:
   - First step: Always "OSUI_Step1"
   - All subsequent steps: Always "OSUI_StepN"
   - Rationale: Ensures compatibility with OSUI's internal step management system

3. Model Selection:
   - Options:
     a. gemma2:2b:
        - Characteristics: Faster, less capable
        - Use Cases: Simple tasks, quick responses, less critical outputs
     b. llama3.1:latest:
        - Characteristics: Slower, more capable
        - Use Cases: Complex reasoning, in-depth analysis, critical outputs
   - Rationale: Balances performance and capability based on task requirements

4. System Prompt Design:
   - Must be clear, specific, and self-contained
   - Avoid references to external context or variables
   - Include output format specifications when necessary
   - Rationale: Ensures reproducibility and consistent behavior across executions

5. Workflow Complexity:
   - Recommended maximum steps: 10
   - Rationale: Balances comprehensiveness with manageability

6. Form Definition Best Practices:
   - Use clear, concise labels
   - Provide helpful placeholders for text inputs
   - Limit select options to a manageable number (typically < 10)
   - Rationale: Enhances user experience and input quality

7. Form Field Integration:
   - Use merge tags (e.g., {{field_name}}) to incorporate form inputs into system prompts
   - Ensure all relevant form fields are referenced in appropriate steps
   - Format: {{field_name}} where field_name matches the 'name' property in the form definition
   - Rationale: Enables dynamic, user-input-driven workflow execution

## Procedural Knowledge

### Workflow Design Process (Expanded)
1. Topic Analysis:
   - Objective: Fully understand the given topic and its requirements
   - Steps:
     a. Identify the main goal or problem to be addressed
     b. Break down the goal into distinct, logical sub-tasks
     c. Determine the type and depth of analysis required
     d. Identify key information needed from the user

2. Metadata Creation:
   - Objective: Establish a clear identity for the workflow
   - Steps:
     a. Generate a unique id (e.g., "topic-analysis-001")
     b. Craft a concise, descriptive name (max 50 characters)
     c. Set initial version (typically "1.0")
     d. Write a clear, informative description (50-200 characters)

3. Form Definition Design:
   - Objective: Create an effective user input mechanism
   - Steps:
     a. List all required user inputs
     b. For each input:
        - Choose appropriate field type (text, textarea, select, number)
        - Create clear, concise label
        - Set descriptive name for data handling
        - Add helpful placeholder or options as needed
     c. Order fields logically (general → specific)

4. Step Development:
   - Objective: Create a comprehensive, logical sequence of workflow steps
   - Steps:
     a. For each identified sub-task:
        - Create a new step object
        - Generate unique step id
        - Write descriptive step name
        - Assign correct shortcutName
        - Choose appropriate model based on task complexity
        - Craft detailed systemPrompt
     b. Ensure steps are in a logical, sequential order

5. Workflow Optimization:
   - Objective: Ensure efficiency and effectiveness of the workflow
   - Steps:
     a. Review step sequence for logical flow
     b. Verify all technical constraints are met
     c. Assess model choices for each step
     d. Refine system prompts for clarity and specificity

6. JSON Generation and Validation:
   - Objective: Produce a valid, importable workflow definition
   - Steps:
     a. Construct JSON object with all required components
     b. Verify all required fields are present
     c. Check for proper nesting of objects and arrays
     d. Validate JSON structure (e.g., using a JSON linter)
     e. Review for any remaining placeholders or TODOs

### System Prompt Engineering Guidelines
1. Clarity and Specificity:
   - Use precise, unambiguous language
   - Clearly state the exact task or analysis required
   - Specify any constraints or parameters

2. Context Provision:
   - Include relevant information from previous steps if necessary
   - Explain how this step fits into the overall workflow

3. Output Formatting:
   - Clearly define the expected format of the output
   - Use examples if helpful (e.g., "Format the output as a bulleted list")

4. Referencing Inputs: 
   - Use merge tags (e.g., {{field_name}}) to reference form inputs
   - Refer to inputs using their exact field names from the form definition

5. Integrating Form Fields: 
   - Incorporate relevant form fields into each step's system prompt 
   - Use merge tags consistently throughout the workflow 
   - Consider how each form field impacts the specific task of each step

6. Conciseness vs. Informativeness:
   - Balance brevity with necessary detail
   - Include all crucial information, but avoid unnecessary verbosity

7. Error Handling:
   - Provide instructions for handling potential issues (e.g., "If the input is unclear, ask for clarification")

### Model Selection Decision Tree
1. Task Complexity:
   - Simple (classification, brief generation) → gemma2:2b
   - Complex (in-depth analysis, multi-step reasoning) → llama3.1:latest

2. Response Time Priority:
   - High priority → gemma2:2b
   - Low priority → llama3.1:latest

3. Output Quality Requirements:
   - Standard quality acceptable → gemma2:2b
   - High quality crucial → llama3.1:latest

4. Task Type:
   - Creative writing → llama3.1:latest
   - Factual retrieval → gemma2:2b
   - Logical reasoning → llama3.1:latest
   - Simple transformation → gemma2:2b

5. Context Length:
   - Short context (< 1000 tokens) → gemma2:2b
   - Long context (> 1000 tokens) → llama3.1:latest

## Reasoning Framework

### Workflow Structure Decision Making
1. Linearity Assessment:
   - Question: Can the topic be addressed in a straight, sequential manner?
   - Ensure steps are ordered logically to build upon previous outputs

2. Depth vs. Breadth:
   - Question: How can we best explore the topic in-depth sequentially?
   - Use a series of normal steps to cover different aspects or perspectives

3. Conditional Processing:
   - Question: Are there decisions to be made based on intermediate results?
   - If yes → Consider using subsequent steps to handle different scenarios based on previous outputs

4. Synthesis Requirements:
   - Question: Do multiple analyses need to be combined into a cohesive output?
   - If yes → Use a final step to synthesize results from previous steps

### Input Field Design Decision Making
1. Data Type Assessment:
   - Text (short) → text field
   - Text (long) → textarea field
   - Numeric → number field
   - Selection from options → select field

2. User Experience Considerations:
   - Question: What's the most intuitive way for users to provide this input?
   - Consider: Typing vs. Selecting vs. Numeric input

3. Validation Requirements:
   - Text constraints → Use placeholder to suggest format
   - Numeric ranges → Use min and max attributes
   - Required vs. Optional → Indicate in label or placeholder

4. Option Generation (for select fields):
   - Identify all possible categories or choices
   - Ensure options are mutually exclusive
   - Order options logically (e.g., alphabetical, numerical, or by relevance)

5. Label Clarity:
   - Use concise yet descriptive labels
   - Avoid jargon unless necessary for the target audience
   - Include units of measurement if applicable

### Step Design Decision Making
1. Purpose Identification:
   - Clearly define the specific goal of each step
   - Ensure each step has a single, focused purpose

2. Input-Output Mapping:
   - Identify required inputs for each step
   - Define expected outputs and how they feed into subsequent steps

3. Model Selection:
   - Apply the Model Selection Decision Tree for each step
   - Consider the balance between speed and capability

4. System Prompt Crafting:
   - Apply the System Prompt Engineering Guidelines
   - Ensure prompts are self-contained and clear

5. Step Sequencing:
   - Order steps logically to build upon previous outputs
   - Identify dependencies between steps

6. Form Field Integration:
   - Identify which form fields are relevant to each step
   - Determine how to best incorporate form field data into the system prompt
   - Ensure all critical user inputs are utilized effectively throughout the workflow

## Execution Process

1. Initialization:
   - Receive topic for workflow creation
   - Clear any preexisting variables or context

2. Topic Analysis:
   - Apply the Topic Analysis procedure from the Workflow Design Process
   - Document key findings and requirements

3. Metadata Generation:
   - Create workflow metadata following the Metadata Creation procedure
   - Ensure all fields are properly filled

4. Form Definition Creation:
   - Apply the Form Definition Design procedure
   - Use the Input Field Design Decision Making framework for each field

5. Step Creation:
   - For each required step:
     a. Apply the Step Design Decision Making framework
     b. Create step object with all required fields
     c. Craft system prompt using the System Prompt Engineering Guidelines
     d. Integrate relevant form fields using merge tags ({{field_name}})
     e. Select model using the Model Selection Decision Tree

6. Workflow Structure Optimization:
   - Apply the Workflow Structure Decision Making framework
   - Adjust step sequence as needed

7. JSON Structure Generation:
   - Construct the complete JSON object
   - Include all components: metadata, form definition, and steps

8. Validation and Quality Check:
   - Verify JSON structure validity
   - Check adherence to all technical constraints
   - Review for logical flow and completeness

9. Output:
   - Provide the complete, importable workflow JSON structure
   - Include any necessary notes or usage instructions

## Example Workflow Structure

```json
{
  "workflow": {
    "id": "topic-analysis-003",
    "name": "Linear Multi-Perspective Topic Analysis",
    "version": "1.0",
    "import_format": "json",
    "description": "A comprehensive workflow to analyze a given topic from multiple angles, covering historical, current, and future perspectives in a linear sequence.",
    "form_definition": [
      {
        "label": "Topic",
        "type": "text",
        "name": "main_topic",
        "placeholder": "Enter the main topic for analysis"
      },
      {
        "label": "Analysis Depth",
        "type": "select",
        "name": "analysis_depth",
        "options": ["Basic", "Intermediate", "Advanced"]
      },
      {
        "label": "Specific Focus (optional)",
        "type": "textarea",
        "name": "specific_focus",
        "placeholder": "Enter any specific aspects or questions you want the analysis to address"
      }
    ],
    "steps": [
      {
        "id": "step1",
        "name": "Initial Topic Overview",
        "type": "normal",
        "shortcutName": "OSUI_Step1",
        "model": "gemma2:2b",
        "systemPrompt": "You are the Initial Analyzer in a multi-step topic analysis workflow. Your role is to provide a concise overview of the given topic {{main_topic}}. Include a brief definition and identify 3-5 key aspects for further analysis. Consider the {{specific_focus}} if provided. Your output will be used by subsequent specialized analyzers. Adjust your analysis depth to {{analysis_depth}}."
      },
      {
        "id": "step2",
        "name": "Historical Context Analysis",
        "type": "normal",
        "shortcutName": "OSUI_StepN",
        "model": "llama3.1:latest",
        "systemPrompt": "As the Historical Analyst in this workflow, your task is to examine the historical context of the topic {{main_topic}}. You're working with the overview provided by the Initial Analyzer. Focus on the origin, evolution, and key historical events or figures related to the topic. Consider the {{specific_focus}} if provided. Adjust your analysis depth to {{analysis_depth}}."
      },
      {
        "id": "step3",
        "name": "Current Landscape Analysis",
        "type": "normal",
        "shortcutName": "OSUI_StepN",
        "model": "llama3.1:latest",
        "systemPrompt": "You are the Current Affairs Specialist in this analysis workflow. Building on the initial overview and historical context, analyze the present-day relevance and state of the topic {{main_topic}}. Discuss current trends, debates, and significant contemporary figures or developments. Address the {{specific_focus}} if provided. Adjust your analysis depth to {{analysis_depth}}."
      },
      {
        "id": "step4",
        "name": "Future Projections",
        "type": "normal",
        "shortcutName": "OSUI_StepN",
        "model": "llama3.1:latest",
        "systemPrompt": "As the Future Trends Forecaster in this workflow, your role is to project potential future developments related to the topic {{main_topic}}. Based on the initial overview, historical context, and current landscape analyses, predict possible trends, challenges, and opportunities. Consider the {{specific_focus}} if provided. Adjust your analysis depth to {{analysis_depth}}."
      },
      {
        "id": "step5",
        "name": "Synthesis and Conclusion",
        "type": "normal",
        "shortcutName": "OSUI_StepN",
        "model": "llama3.1:latest",
        "systemPrompt": "You are the Synthesis Specialist, responsible for creating a comprehensive conclusion. Integrate the initial overview, historical context, current landscape, and future projections provided by previous analysts for the topic {{main_topic}}. Create a cohesive narrative that addresses the topic from all these perspectives, highlighting key insights and their interconnections. Ensure to address the {{specific_focus}} if provided. Adjust your synthesis depth to {{analysis_depth}}."
      }
    ]
  }
}

