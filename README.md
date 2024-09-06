# OSUI: Ollama Shortcuts UI

Ollama Shortcuts UI is an innovative project that bridges the gap between Ollama's local language models and Apple's Shortcuts app on Mac OS. This web interface allows users to interact with Ollama models through a user-friendly front-end, leveraging Shortcuts as an intermediary to handle API calls and process responses.

The purpose of this project is to build a fully local workflow engine that allows users to compose multi-step AI agent workflows using only Shortcuts and Ollama.

## Features

- **Web Interface**: A user-friendly dashboard for managing workflows, shortcuts, and Ollama model interactions.
- **Workflow Composer**: Create and edit complex workflows, including parallel branching.
- **Shortcuts Library**: Manage and use your Apple Shortcuts directly from the web interface.
- **Form Builder**: Create custom input forms for your workflows.
- **Local Processing**: All operations run locally, ensuring data privacy and security.

## Getting Started

### Prerequisites

- Python 3.7+
- Git
- Ollama installed on your local machine
- Mac OS desktop or laptop computer with Shortcuts app

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/elsheppo/ollama-shortcuts-ui.git
   cd ollama-shortcuts-ui
   ```

2. Run the local server:
   ```
   python webui.py
   ```

3. Open your web browser and navigate to `http://localhost:8000`

4. That's it. Everything should run with a default Python installation.

## Usage

1. **Dashboard**: Get an overview of your workflows and quick actions.
2. **Workflows**: Create and manage workflows that integrate Shortcuts and Ollama operations.
3. **Shortcuts**: View your available Apple Shortcuts. Add them to workflows for complex automations. Add descriptions to Shortcuts since currently they only show the title of the Shortcut with no context about what it does.
4. **Form Builder**: Create custom input forms for your workflows.
5. **Settings**: Configure Ollama API settings and other options.

## Creating Workflows with Claude and the Executable Ontology

Paste the Executable Ontology markdown file into Claude 3.5 Sonnet alongside a description of the workflow you want to design. Sometimes it may have an issue where it structures system prompts incorrectly with multi-line text. You can correct it by telling it to put the system prompt on a single line with no line breaks.

The workflow you get with this will be a linear workflow (no branching / merging) that you can import in OSUI via "Import Workflow". Then you can run the workflow!

Currently this executable ontology is designed to select from either gemma2:2b or llama3.1:latest from your available Ollama model files. If you don't have these models, or you want to change them, you can do this once the workflow is created based on your preferences.

## Contributing

We welcome contributions to Ollama Shortcuts UI! Here's how you can help:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Shortcuts Integration

While we can't include Apple Shortcuts directly in this repository due to their proprietary format, we've created some starting blocks for you. Download it from the following iCloud links:

- [OSUI, Block 1](https://www.icloud.com/shortcuts/26cc4ca06a4a4bb09537a438f0abc3e5): Make this the starting block in a workflow.
- [OSUI, Block N](https://www.icloud.com/shortcuts/c4efc7b0654d4cb88f0b8d754bdc1913): Extend workflows after Block 1 using this block for each step.
- [OSUI Function Router](https://www.icloud.com/shortcuts/1344e0d87a4e4df28a49e3e29f64869f): Demo function calling block that can run the "Get Weather" action when the user asks about the weather.
- [OSUI Function – Get Weather](https://www.icloud.com/shortcuts/43763a5b6f90480d93f79c0ce789d34c): Gets the weather in Austin using Apple Weather. To get the weather in your locality, change the City in the shortcut itself.

To use these Shortcuts:
1. Click on the links above on your Mac
2. Add the Shortcut to your library
3. In the Ollama Shortcuts UI web interface, refresh your Shortcuts list to see the new additions

## Acknowledgments

- The Ollama team for their amazing language model
- Apple for the powerful Shortcuts app
- All contributors and users of Ollama Shortcuts UI

## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for details.
