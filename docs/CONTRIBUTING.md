# Contributing to Jev Open Source Dashboard

Thank you for your interest in helping build a free, privacy-first alternative to proprietary AI coding assistants!

## 🚀 Quick Setup

```bash
# Clone repo
git clone https://github.com/YOUR-USERNAME/codeforge-ai.git
cd codeforge-ai

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r src/backend/requirements.txt

cd frontend
npm install

# Setup Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen3.5:9b  # or any model you prefer

# Start services
./start.sh
```

See [README.md](../README.md) for full details.

## 🐛 Reporting Bugs

When reporting bugs, please include:
1. **Steps to reproduce** – clear numbered list
2. **Expected vs actual behavior**
3. **Environment**: OS, Ollama version, model used
4. **Error messages** or screenshots when applicable

Use the "Bug Report" GitHub issue template.

## 💡 Feature Requests

Vote on existing feature requests by reacting 👍 to issues. For new ideas:
1. Search existing issues/discussions first
2. Explain the problem you're solving
3. Describe your proposed solution
4. Link to similar features in other tools if applicable

## 📝 Your First Pull Request

### Easy Issues for New Contributors
- Documentation improvements
- UI polish and design feedback
- Test coverage gaps
- Adding new model provider integrations (OpenRouter, Groq, etc.)

### Workflow
1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Make changes with meaningful commit messages
4. Ensure tests pass (if applicable)
5. Push and open PR

### Commit Message Format
```
feat: Add file upload support for code context

- Added FileUploader component to frontend
- Updated App.tsx to handle file attachments  
- Prepared backend endpoint stub for future implementation

Closes #123
```

Use: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## 🏗️ Development Guidelines

### Code Quality
- Python backend: Follow PEP 8, type hints encouraged
- Frontend: TypeScript, ESLint rules enforced
- Components should be small and focused

### Testing
- Write tests for new features when possible
- Test with multiple model sizes (9B vs 27B)
- Verify offline/local mode works

### Backwards Compatibility
- Don't break existing chat functionality
- New features opt-in by default
- Model configuration remains flexible

## 🤝 Community Guidelines

- Be respectful and inclusive
- Assume positive intent
- Keep discussions focused on the project
- Help others learn, especially newcomers

## 💬 Questions?

- Join our Discord server (TBA at launch)
- Open a discussion thread on GitHub
- Email: your.email@example.com

---

**Thank you for contributing to free and open-source AI tools!** 🙏
