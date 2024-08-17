# Ollama Shortcuts UI

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

## Contributing

We welcome contributions to Ollama Shortcuts UI! Here's how you can help:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Shortcuts Integration

While we can't include Apple Shortcuts directly in this repository due to their proprietary format, we've created a starting block for you. Download it from the following iCloud link:

- [Ollama Shortcut, Basic Block](https://www.icloud.com/shortcuts/81d8876c3b964a93b553f47d23483f51)


To use this Shortcut:
1. Click on the links above on your Apple device
2. Add the Shortcut to your library
3. In the Ollama Shortcuts UI web interface, refresh your Shortcuts list to see the new additions

## Acknowledgments

- The Ollama team for their amazing language model
- Apple for the powerful Shortcuts app
- All contributors and users of Ollama Shortcuts UI
