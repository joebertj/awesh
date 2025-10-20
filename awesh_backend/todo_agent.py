"""
TODO Agent for awesh - Agentic loop system like Cursor/Claude

Manages goal-oriented task execution with iterative AI feedback loops.

Features:
- Represents 1 goal with up to 10 iterations
- Tracks progress toward goal completion
- Iterates with AI until goal is achieved or iterations exhausted
- Stops after completing goal or asks user to continue
- Integrates with execution agent for command feedback
- Similar to Cursor's agent mode and Claude's extended thinking

Architecture:
User: "deploy nginx to kubernetes with monitoring"
  ↓
TODO Agent creates goal with subtasks
  ↓
Iteration 1: AI creates deployment YAML → File Editor
Iteration 2: AI applies deployment → Execution Agent
Iteration 3: AI verifies pods running → Execution Agent  
Iteration 4: AI sets up monitoring → File Editor + Execution Agent
  ↓
Goal complete ✅ or Ask user to continue
"""

import os
import sys
import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

def debug_log(message):
    """Log debug message if verbose mode is enabled"""
    verbose = os.getenv('VERBOSE', '0') in ['1', '2']
    if verbose:
        print(f"📋 TODO Agent: {message}", file=sys.stderr)


class TaskStatus(Enum):
    """Status of a task"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """Represents a subtask within a goal"""
    description: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    iteration: int = 0
    error: Optional[str] = None


@dataclass
class Goal:
    """Represents a user goal with multiple tasks"""
    description: str
    tasks: List[Task] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    current_iteration: int = 0
    max_iterations: int = 10
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    ai_context: List[str] = field(default_factory=list)  # Track AI's working memory
    
    def is_complete(self) -> bool:
        """Check if goal is completed"""
        return all(task.status == TaskStatus.COMPLETED for task in self.tasks)
    
    def is_exhausted(self) -> bool:
        """Check if we've exhausted iterations"""
        return self.current_iteration >= self.max_iterations
    
    def get_progress(self) -> Tuple[int, int]:
        """Get progress as (completed, total)"""
        completed = sum(1 for task in self.tasks if task.status == TaskStatus.COMPLETED)
        return completed, len(self.tasks)
    
    def add_context(self, context: str):
        """Add to AI's working memory"""
        self.ai_context.append(context)
        # Keep only last 20 context items to avoid bloat
        if len(self.ai_context) > 20:
            self.ai_context = self.ai_context[-20:]


class TODOAgent:
    """
    Agent that manages goal-oriented execution with iterative loops
    Like Cursor's agent mode and Claude's extended thinking
    """
    
    def __init__(self, max_iterations: int = 10):
        """
        Initialize TODO agent
        
        Args:
            max_iterations: Max iterations per goal (default: 10)
        """
        self.max_iterations = max_iterations
        self.current_goal: Optional[Goal] = None
        self.goal_history: List[Goal] = []
        
    def create_goal(self, user_request: str) -> Goal:
        """
        Create a new goal from user request
        
        Args:
            user_request: User's goal description
            
        Returns:
            New Goal object
        """
        debug_log(f"Creating goal: {user_request}")
        
        goal = Goal(
            description=user_request,
            max_iterations=self.max_iterations,
            started_at=datetime.now()
        )
        
        self.current_goal = goal
        return goal
    
    def should_continue(self) -> Tuple[bool, str]:
        """
        Check if we should continue iterating
        
        Returns:
            (should_continue, reason)
        """
        if not self.current_goal:
            return False, "No active goal"
        
        if self.current_goal.is_complete():
            return False, "Goal completed ✅"
        
        if self.current_goal.is_exhausted():
            return False, f"Max iterations ({self.max_iterations}) reached"
        
        return True, "Continue"
    
    def increment_iteration(self):
        """Increment iteration counter"""
        if self.current_goal:
            self.current_goal.current_iteration += 1
    
    def add_task(self, description: str, status: TaskStatus = TaskStatus.PENDING) -> Task:
        """Add a task to current goal"""
        if not self.current_goal:
            raise ValueError("No active goal")
        
        task = Task(
            description=description,
            status=status,
            iteration=self.current_goal.current_iteration
        )
        
        self.current_goal.tasks.append(task)
        debug_log(f"Added task: {description}")
        
        return task
    
    def update_task_status(self, task_index: int, status: TaskStatus, result: str = None, error: str = None):
        """Update status of a task"""
        if not self.current_goal or task_index >= len(self.current_goal.tasks):
            return
        
        task = self.current_goal.tasks[task_index]
        task.status = status
        if result:
            task.result = result
        if error:
            task.error = error
        
        debug_log(f"Updated task {task_index}: {status.value}")
    
    def complete_goal(self, success: bool = True):
        """Mark current goal as complete"""
        if not self.current_goal:
            return
        
        self.current_goal.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        self.current_goal.completed_at = datetime.now()
        
        # Archive goal
        self.goal_history.append(self.current_goal)
        
        debug_log(f"Goal completed: {self.current_goal.description}")
        
        self.current_goal = None
    
    def get_iteration_context(self) -> str:
        """
        Get context for current iteration
        Returns a formatted string with goal progress and history
        """
        if not self.current_goal:
            return ""
        
        context = f"""
<current_goal>
Goal: {self.current_goal.description}
Iteration: {self.current_goal.current_iteration}/{self.current_goal.max_iterations}
Progress: {self.current_goal.get_progress()[0]}/{self.current_goal.get_progress()[1]} tasks completed
</current_goal>

<tasks>
"""
        
        for i, task in enumerate(self.current_goal.tasks):
            status_emoji = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.BLOCKED: "🚫"
            }.get(task.status, "❓")
            
            context += f"{i+1}. {status_emoji} {task.description}\n"
            if task.result:
                context += f"   Result: {task.result[:100]}...\n"
            if task.error:
                context += f"   Error: {task.error[:100]}...\n"
        
        context += "</tasks>\n"
        
        # Add AI's working memory
        if self.current_goal.ai_context:
            context += "\n<ai_memory>\n"
            for ctx in self.current_goal.ai_context[-5:]:  # Last 5 context items
                context += f"- {ctx}\n"
            context += "</ai_memory>\n"
        
        return context
    
    def format_status(self) -> str:
        """Format current goal status for display"""
        if not self.current_goal:
            return "No active goal"
        
        completed, total = self.current_goal.get_progress()
        progress_percent = (completed / total * 100) if total > 0 else 0
        
        status = f"""
📋 Goal: {self.current_goal.description}
🔄 Iteration: {self.current_goal.current_iteration}/{self.current_goal.max_iterations}
📊 Progress: {completed}/{total} tasks ({progress_percent:.0f}%)

Tasks:
"""
        
        for i, task in enumerate(self.current_goal.tasks):
            status_emoji = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.IN_PROGRESS: "🔄", 
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.BLOCKED: "🚫"
            }.get(task.status, "❓")
            
            status += f"  {i+1}. {status_emoji} {task.description}\n"
        
        return status.strip()


# Singleton instance
_todo_agent_instance = None

def get_todo_agent() -> TODOAgent:
    """Get or create the global TODO agent instance"""
    global _todo_agent_instance
    if _todo_agent_instance is None:
        _todo_agent_instance = TODOAgent()
    return _todo_agent_instance

