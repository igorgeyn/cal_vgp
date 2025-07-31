#!/usr/bin/env python3
"""
Copy Repository Code to Clipboard
Formats all code files for easy pasting into Claude
"""

import subprocess
from pathlib import Path
import pyperclip  # Install with: pip install pyperclip

def get_repo_code(repo_path="."):
    """Get all code from repository formatted for Claude"""
    repo_path = Path(repo_path)
    
    output = []
    output.append("# Repository Code Files\n")
    
    # Define file extensions to include
    extensions = ['.py', '.js', '.html', '.css', '.json', '.md', '.txt', '.yml', '.yaml']
    
    # Collect all relevant files
    for ext in extensions:
        for file_path in repo_path.rglob(f'*{ext}'):
            # Skip hidden and ignored directories
            if any(skip in str(file_path) for skip in ['.git', '__pycache__', 'node_modules', 'venv']):
                continue
            
            try:
                relative_path = file_path.relative_to(repo_path)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                output.append(f"\n## File: {relative_path}\n")
                output.append("```" + ext[1:] + "\n")
                output.append(content)
                output.append("\n```\n")
            except:
                pass
    
    return '\n'.join(output)

if __name__ == "__main__":
    import sys
    
    # Get path from command line or use current directory
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    print(f"📂 Scanning repository at: {path}")
    
    # Get all code
    code_text = get_repo_code(path)
    
    # Copy to clipboard
    try:
        pyperclip.copy(code_text)
        print("✅ Code copied to clipboard!")
        print("📋 You can now paste it directly into Claude")
        print(f"📊 Total size: {len(code_text):,} characters")
    except:
        # If clipboard fails, save to file
        with open("repo_code.txt", "w") as f:
            f.write(code_text)
        print("⚠️  Couldn't access clipboard")
        print("📄 Code saved to: repo_code.txt")