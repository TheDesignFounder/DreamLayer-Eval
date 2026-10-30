# Contributing to DreamLayer AI

For the research workbench, follow [research contributor setup](research-contributing.md).
It specifies Python 3.11/3.12, POSIX execution, offline tests, CI and formatting.
The older generation-service setup below has a separate dependency environment.

Thank you for your interest in contributing to DreamLayer AI! This guide will help you get started with contributing to the project.

## 🤝 How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **🐛 Bug Reports** - Report issues you encounter
- **✨ Feature Requests** - Suggest new features or improvements
- **📝 Documentation** - Improve or add documentation
- **🔧 Code Contributions** - Submit code changes and improvements
- **🎨 UI/UX Improvements** - Enhance the user interface
- **🧪 Testing** - Help test features and report issues

### Getting Started

1. **Fork the repository**
   ```bash
   git clone https://github.com/your-username/DreamLayer.git
   cd DreamLayer
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes** following the style guidelines below

4. **Test your changes**
   ```bash
   # Test the backend
   cd dream_layer_backend
   python -m pytest tests/
   
   # Test the frontend
   cd dream_layer_frontend
   npm test
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request** on GitHub

## 📋 Development Setup

### Prerequisites

- **Python 3.8+**
- **Node.js 16+**
- **Git**
- **Docker** (optional, for containerized development)

### Local Development Environment

1. **Clone and setup**
   ```bash
   git clone https://github.com/DreamLayer-AI/DreamLayer.git
   cd DreamLayer
   ```

2. **Install Python dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Install Node.js dependencies**
   ```bash
   cd dream_layer_frontend
   npm install
   cd ..
   ```

4. **Setup pre-commit hooks**
   ```bash
   pre-commit install
   ```

### Development Scripts

```bash
# Start development servers
npm run dev:backend    # Start Flask API server
npm run dev:frontend   # Start React development server
npm run dev:comfyui    # Start ComfyUI server

# Run tests
npm run test:backend   # Run Python tests
npm run test:frontend  # Run React tests
npm run test:e2e       # Run end-to-end tests

# Code quality checks
npm run lint           # Run ESLint
npm run format         # Run Prettier
npm run type-check     # Run TypeScript checks
```

## 📝 Code Style Guidelines

### Python Style Guide

We follow **PEP 8** with some modifications:

#### Code Formatting
```python
# Use Black for code formatting
# Line length: 88 characters
# Use double quotes for strings

def example_function(param1: str, param2: int) -> bool:
    """Example function with proper docstring.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When parameters are invalid
    """
    if not param1:
        raise ValueError("param1 cannot be empty")
    
    return param2 > 0
```

#### Import Organization
```python
# Standard library imports
import os
import sys
from typing import Optional, Tuple

# Third-party imports
import requests
from flask import Flask, jsonify

# Local imports
from .utils import helper_function
from .models import User
```

#### Type Hints
```python
from typing import Dict, List, Optional, Union

def process_data(
    data: List[Dict[str, Union[str, int]]],
    config: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Process data with proper type hints."""
    pass
```

### TypeScript/JavaScript Style Guide

We follow **Airbnb JavaScript Style Guide** with TypeScript additions:

#### Code Formatting
```typescript
// Use Prettier for formatting
// Use ESLint for linting
// Use TypeScript strict mode

interface UserData {
  id: string;
  name: string;
  email: string;
}

const processUser = (user: UserData): string => {
  if (!user.name) {
    throw new Error('User name is required');
  }
  
  return `${user.name} (${user.email})`;
};
```

#### Component Structure
```typescript
import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';

interface ComponentProps {
  title: string;
  onAction: (data: string) => void;
}

export const ExampleComponent: React.FC<ComponentProps> = ({
  title,
  onAction,
}) => {
  const [state, setState] = useState<string>('');
  
  useEffect(() => {
    // Effect logic
  }, []);
  
  const handleClick = (): void => {
    onAction(state);
  };
  
  return (
    <div className="example-component">
      <h2>{title}</h2>
      <Button onClick={handleClick}>Action</Button>
    </div>
  );
};
```

### Commit Message Convention

We use **Conventional Commits**:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### Types
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, etc.)
- **refactor**: Code refactoring
- **test**: Adding or updating tests
- **chore**: Maintenance tasks

#### Examples
```bash
feat: add ControlNet support for image generation
fix(api): resolve model loading issue on Windows
docs: update installation guide for macOS
style: format Python code with Black
refactor(utils): improve API key validation
test: add unit tests for prompt generation
chore: update dependencies to latest versions
```

## 🧪 Testing Guidelines

### Python Testing

We use **pytest** for testing:

```python
import pytest
from unittest.mock import Mock, patch
from dream_layer_backend.utils import validate_api_key

class TestAPIKeyValidation:
    def test_valid_openai_key(self):
        """Test valid OpenAI API key validation."""
        key = "sk-" + "0" * 48  # Deliberately synthetic format fixture; never a credential.
        assert validate_api_key(key, "openai") is True
    
    def test_invalid_openai_key(self):
        """Test invalid OpenAI API key validation."""
        key = "invalid-key"
        assert validate_api_key(key, "openai") is False
    
    @patch('os.getenv')
    def test_missing_api_key(self, mock_getenv):
        """Test behavior when API key is missing."""
        mock_getenv.return_value = None
        # Test implementation
```

### Frontend Testing

We use **Jest** and **React Testing Library**:

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { ExampleComponent } from './ExampleComponent';

describe('ExampleComponent', () => {
  it('renders with correct title', () => {
    const mockOnAction = jest.fn();
    render(<ExampleComponent title="Test Title" onAction={mockOnAction} />);
    
    expect(screen.getByText('Test Title')).toBeInTheDocument();
  });
  
  it('calls onAction when button is clicked', () => {
    const mockOnAction = jest.fn();
    render(<ExampleComponent title="Test" onAction={mockOnAction} />);
    
    fireEvent.click(screen.getByRole('button'));
    expect(mockOnAction).toHaveBeenCalled();
  });
});
```

### End-to-End Testing

We use **Playwright** for E2E tests:

```typescript
import { test, expect } from '@playwright/test';

test('image generation workflow', async ({ page }) => {
  await page.goto('http://localhost:8080');
  
  // Enter prompt
  await page.fill('[data-testid="prompt-input"]', 'A beautiful sunset');
  
  // Select model
  await page.selectOption('[data-testid="model-select"]', 'sd15.safetensors');
  
  // Click generate
  await page.click('[data-testid="generate-button"]');
  
  // Wait for result
  await expect(page.locator('[data-testid="generated-image"]')).toBeVisible();
});
```

## 📚 Documentation Standards

### Code Documentation

#### Python Docstrings
```python
def complex_function(param1: str, param2: int, *, optional_param: bool = True) -> Dict[str, Any]:
    """Perform complex operation with detailed description.
    
    This function performs a complex operation that requires multiple steps.
    It handles various edge cases and provides comprehensive error handling.
    
    Args:
        param1: The primary input parameter. Must be a non-empty string.
        param2: The secondary input parameter. Must be a positive integer.
        optional_param: Optional boolean parameter. Defaults to True.
        
    Returns:
        A dictionary containing the operation results with the following keys:
        - 'status': Operation status ('success' or 'error')
        - 'data': The processed data
        - 'metadata': Additional information about the operation
        
    Raises:
        ValueError: When param1 is empty or param2 is negative
        RuntimeError: When the operation fails due to external factors
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result['status'])
        'success'
    """
```

#### TypeScript Documentation
```typescript
/**
 * Processes user data and returns formatted results
 * 
 * @param userData - The user data to process
 * @param options - Optional processing configuration
 * @returns Promise resolving to processed user data
 * 
 * @example
 * ```typescript
 * const result = await processUserData(user, { format: 'json' });
 * console.log(result.name); // "John Doe"
 * ```
 */
async function processUserData(
  userData: UserData,
  options?: ProcessingOptions
): Promise<ProcessedUserData> {
  // Implementation
}
```

### API Documentation

Document all API endpoints with examples:

```markdown
## POST /api/generate

Generate an image from text prompt.

### Request Body
```json
{
  "prompt": "A beautiful sunset over mountains",
  "negative_prompt": "blurry, low quality",
  "model": "sd15.safetensors",
  "settings": {
    "steps": 20,
    "cfg": 7.0,
    "width": 512,
    "height": 512
  }
}
```

### Response
```json
{
  "status": "success",
  "image_url": "/api/images/generated_123.png",
  "metadata": {
    "generation_time": 15.2,
    "model_used": "sd15.safetensors",
    "parameters": {
      "steps": 20,
      "cfg": 7.0
    }
  }
}
```
```

## 🔧 Pre-commit Hooks

We use pre-commit hooks to ensure code quality:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
  
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

## 🚀 Release Process

### Version Management

We use **Semantic Versioning** (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

- [ ] All tests pass
- [ ] Documentation is updated
- [ ] Changelog is updated
- [ ] Version is bumped
- [ ] Release notes are written
- [ ] GitHub release is created

### Creating a Release

```bash
# Update version
npm version patch  # or minor, major

# Create release branch
git checkout -b release/v1.2.3

# Update changelog
# Update documentation

# Create pull request
git push origin release/v1.2.3

# After merge, create GitHub release
```

## 🤝 Community Guidelines

### Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please:

- Be respectful and considerate
- Use inclusive language
- Be patient with newcomers
- Provide constructive feedback
- Help others learn and grow

### Communication

- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Discord**: Join our Discord server for real-time chat
- **Email**: Contact maintainers for sensitive issues

### Recognition

Contributors are recognized in several ways:

- **Contributors list** on GitHub
- **Release notes** for significant contributions
- **Documentation credits** for documentation contributions
- **Special thanks** for major features

## 📞 Getting Help

### Before Asking

1. **Check the documentation** - Your question might already be answered
2. **Search existing issues** - Similar problems might have been reported
3. **Try to reproduce** - Ensure the issue is reproducible
4. **Provide context** - Include relevant details and error messages

### How to Ask

When asking for help, please include:

- **Environment details** (OS, Python version, Node.js version)
- **Steps to reproduce** the issue
- **Expected vs actual behavior**
- **Error messages** and stack traces
- **Relevant code snippets**

### Where to Ask

- **Bug reports**: GitHub Issues
- **Feature requests**: GitHub Discussions
- **General questions**: GitHub Discussions or Discord
- **Security issues**: Email maintainers directly

---

Thank you for contributing to DreamLayer AI! Your contributions help make this project better for everyone. 
