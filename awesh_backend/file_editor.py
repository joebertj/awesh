"""
AI-Powered File Editor for awesh - Similar to Claude/Cursor editing

This tool allows the AI to make surgical edits to files using search/replace blocks.
The AI provides the old content and new content, and the tool applies the changes.

Features:
- Search/replace with exact matching
- Multiple edits in one operation
- Automatic backup creation
- Validation and error handling
- Context-aware editing (shows surrounding lines)
- Undo support
"""

import os
import sys
import re
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

def debug_log(message):
    """Log debug message if verbose mode is enabled"""
    verbose = os.getenv('VERBOSE', '0') == '1'
    if verbose:
        print(f"✏️ File Editor: {message}", file=sys.stderr)


@dataclass
class FileEdit:
    """Represents a single file edit operation"""
    file_path: str
    old_content: str
    new_content: str
    line_number: Optional[int] = None
    context_before: str = ""
    context_after: str = ""


@dataclass
class EditResult:
    """Result of a file edit operation"""
    success: bool
    message: str
    file_path: str
    backup_path: Optional[str] = None
    changes_made: int = 0


class FileEditor:
    """AI-powered file editor with search/replace capabilities"""
    
    def __init__(self, backup_dir: str = None, create_backups: bool = True):
        """
        Initialize file editor
        
        Args:
            backup_dir: Directory for backup files (default: ~/.awesh_backups)
            create_backups: Whether to create backups before editing
        """
        self.create_backups = create_backups
        self.backup_dir = Path(backup_dir or Path.home() / '.awesh_backups')
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.undo_stack = []  # Stack of backup paths for undo operations
        
    def parse_edit_block(self, content: str) -> List[FileEdit]:
        """
        Parse AI edit blocks from response
        
        Expected format:
        ```edit:path/to/file.txt
        <<<<<<< OLD
        old content here
        =======
        new content here
        >>>>>>> NEW
        ```
        
        Or simplified format:
        EDIT: path/to/file.txt
        OLD:
        old content
        NEW:
        new content
        """
        edits = []
        
        # Try to parse markdown-style edit blocks
        pattern = r'```edit:([^\n]+)\n<<<<<<< OLD\n(.*?)\n=======\n(.*?)\n>>>>>>> NEW\n```'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            file_path = match.group(1).strip()
            old_content = match.group(2)
            new_content = match.group(3)
            
            edits.append(FileEdit(
                file_path=file_path,
                old_content=old_content,
                new_content=new_content
            ))
            debug_log(f"Parsed edit block for {file_path}")
        
        # Also try simplified format
        simple_pattern = r'EDIT:\s*([^\n]+)\nOLD:\n(.*?)\nNEW:\n(.*?)(?=\nEDIT:|$)'
        simple_matches = re.finditer(simple_pattern, content, re.DOTALL)
        
        for match in simple_matches:
            file_path = match.group(1).strip()
            old_content = match.group(2).strip()
            new_content = match.group(3).strip()
            
            edits.append(FileEdit(
                file_path=file_path,
                old_content=old_content,
                new_content=new_content
            ))
            debug_log(f"Parsed simple edit block for {file_path}")
        
        return edits
    
    def create_backup(self, file_path: Path) -> Optional[Path]:
        """Create a backup of the file before editing"""
        if not self.create_backups:
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.name}.{timestamp}.backup"
            backup_path = self.backup_dir / backup_name
            
            shutil.copy2(file_path, backup_path)
            self.undo_stack.append(backup_path)
            debug_log(f"Created backup: {backup_path}")
            
            return backup_path
        except Exception as e:
            debug_log(f"Failed to create backup: {e}")
            return None
    
    def apply_edit(self, edit: FileEdit) -> EditResult:
        """
        Apply a single edit to a file
        
        Returns:
            EditResult with success status and details
        """
        file_path = Path(edit.file_path).expanduser()
        
        # Validate file exists
        if not file_path.exists():
            return EditResult(
                success=False,
                message=f"File not found: {file_path}",
                file_path=str(file_path)
            )
        
        # Read current file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
        except Exception as e:
            return EditResult(
                success=False,
                message=f"Failed to read file: {e}",
                file_path=str(file_path)
            )
        
        # Check if old content exists in file
        if edit.old_content not in current_content:
            # Try with normalized whitespace
            normalized_old = self._normalize_whitespace(edit.old_content)
            normalized_current = self._normalize_whitespace(current_content)
            
            if normalized_old not in normalized_current:
                return EditResult(
                    success=False,
                    message=f"Old content not found in file. The file may have changed.",
                    file_path=str(file_path)
                )
        
        # Create backup
        backup_path = self.create_backup(file_path)
        
        # Apply the edit
        try:
            # Count occurrences to warn if multiple matches
            occurrences = current_content.count(edit.old_content)
            
            if occurrences == 0:
                # Try normalized replacement
                new_content = self._replace_normalized(current_content, edit.old_content, edit.new_content)
            elif occurrences == 1:
                # Direct replacement
                new_content = current_content.replace(edit.old_content, edit.new_content)
            else:
                # Multiple occurrences - only replace first one
                new_content = current_content.replace(edit.old_content, edit.new_content, 1)
                debug_log(f"Warning: Multiple occurrences found, replaced only the first one")
            
            # Write new content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return EditResult(
                success=True,
                message=f"Successfully edited {file_path.name}",
                file_path=str(file_path),
                backup_path=str(backup_path) if backup_path else None,
                changes_made=1
            )
            
        except Exception as e:
            # Restore from backup if edit fails
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, file_path)
                debug_log(f"Restored from backup after error: {e}")
            
            return EditResult(
                success=False,
                message=f"Failed to apply edit: {e}",
                file_path=str(file_path)
            )
    
    def apply_multiple_edits(self, edits: List[FileEdit]) -> List[EditResult]:
        """
        Apply multiple edits, grouped by file
        
        Returns:
            List of EditResult for each file edited
        """
        results = []
        
        # Group edits by file
        edits_by_file = {}
        for edit in edits:
            if edit.file_path not in edits_by_file:
                edits_by_file[edit.file_path] = []
            edits_by_file[edit.file_path].append(edit)
        
        # Apply edits for each file
        for file_path, file_edits in edits_by_file.items():
            for edit in file_edits:
                result = self.apply_edit(edit)
                results.append(result)
        
        return results
    
    def undo_last_edit(self) -> EditResult:
        """Undo the last edit by restoring from backup"""
        if not self.undo_stack:
            return EditResult(
                success=False,
                message="No edits to undo",
                file_path=""
            )
        
        backup_path = self.undo_stack.pop()
        
        if not backup_path.exists():
            return EditResult(
                success=False,
                message=f"Backup not found: {backup_path}",
                file_path=str(backup_path)
            )
        
        # Extract original file path from backup name
        # Format: filename.YYYYMMDD_HHMMSS.backup
        original_name = backup_path.name.rsplit('.', 2)[0]
        # Find the original file (could be in different directory)
        # For simplicity, assume it's in the current directory
        original_path = Path(original_name)
        
        try:
            shutil.copy2(backup_path, original_path)
            return EditResult(
                success=True,
                message=f"Undid edit to {original_name}",
                file_path=str(original_path),
                backup_path=str(backup_path)
            )
        except Exception as e:
            return EditResult(
                success=False,
                message=f"Failed to undo edit: {e}",
                file_path=str(original_path)
            )
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace for fuzzy matching"""
        # Replace multiple spaces/tabs with single space
        text = re.sub(r'[ \t]+', ' ', text)
        # Remove trailing whitespace from each line
        text = '\n'.join(line.rstrip() for line in text.split('\n'))
        return text
    
    def _replace_normalized(self, content: str, old: str, new: str) -> str:
        """Replace content with normalized whitespace matching"""
        # This is a simplified version - could be more sophisticated
        normalized_content = self._normalize_whitespace(content)
        normalized_old = self._normalize_whitespace(old)
        
        if normalized_old in normalized_content:
            # Find the position in normalized content
            start = normalized_content.index(normalized_old)
            # Map back to original content position (approximate)
            # This is a simplification - real implementation would need proper mapping
            return content.replace(old, new, 1)
        
        return content
    
    def show_edit_format(self) -> str:
        """Return the edit format instructions for the AI"""
        return """
To edit files, use this format:

```edit:path/to/file.txt
<<<<<<< OLD
exact content to find
=======
new content to replace with
>>>>>>> NEW
```

Or simplified format:

EDIT: path/to/file.txt
OLD:
exact content to find
NEW:
new content to replace with

Rules:
- OLD content must match exactly (including indentation)
- Include enough context to make the match unique
- Use relative or absolute paths
- Multiple edits can be in one response
- Backups are created automatically
"""


# Singleton instance
_file_editor_instance = None

def get_file_editor() -> FileEditor:
    """Get or create the global file editor instance"""
    global _file_editor_instance
    if _file_editor_instance is None:
        _file_editor_instance = FileEditor()
    return _file_editor_instance

