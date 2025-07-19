# -*- coding: utf-8 -*-
"""
SpiderFoot BE Tool Utilities

Helper functions for integrating third-party tools with SpiderFoot modules.
"""

import os
import sys
import subprocess
from typing import Dict, List, Optional, Tuple


class ToolManager:
    """Manages third-party tool integration for SpiderFoot modules."""
    
    def __init__(self):
        """Initialize the tool manager."""
        # Get project root directory
        self.project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.tools_dir = os.path.join(self.project_dir, "tools")
        self.bin_dir = os.path.join(self.tools_dir, "bin")
        self.python_packages_dir = os.path.join(self.tools_dir, "python_packages")
        
        # Setup environment if tools directory exists
        if os.path.exists(self.tools_dir):
            self._setup_environment()
    
    def _setup_environment(self):
        """Setup environment variables for tool access."""
        # Add project bin directory to PATH
        current_path = os.environ.get('PATH', '')
        if self.bin_dir not in current_path:
            os.environ['PATH'] = f"{self.bin_dir}{os.pathsep}{current_path}"
        
        # Add Python packages to path
        if self.python_packages_dir not in sys.path:
            sys.path.insert(0, self.python_packages_dir)
    
    def get_tool_path(self, tool_name: str) -> Optional[str]:
        """Get the full path to a tool binary.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Full path to the tool if found, None otherwise
        """
        tool_path = os.path.join(self.bin_dir, tool_name)
        if os.path.exists(tool_path) and os.access(tool_path, os.X_OK):
            return tool_path
        
        # Fallback to system PATH
        import shutil
        return shutil.which(tool_name)
    
    def check_tool_installed(self, tool_name: str) -> bool:
        """Check if a tool is installed and accessible.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if tool is installed, False otherwise
        """
        return self.get_tool_path(tool_name) is not None
    
    def run_tool(self, tool_name: str, args: List[str], 
                 timeout: Optional[int] = None) -> Tuple[int, str, str]:
        """Run a tool with the given arguments.
        
        Args:
            tool_name: Name of the tool
            args: List of arguments to pass to the tool
            timeout: Timeout in seconds (optional)
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        tool_path = self.get_tool_path(tool_name)
        if not tool_path:
            return (-1, "", f"Tool '{tool_name}' not found")
        
        cmd = [tool_path] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return (result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (-1, "", f"Tool '{tool_name}' timed out after {timeout} seconds")
        except Exception as e:
            return (-1, "", f"Error running tool '{tool_name}': {str(e)}")
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tools in the project directory.
        
        Returns:
            List of tool names
        """
        if not os.path.exists(self.bin_dir):
            return []
        
        tools = []
        for item in os.listdir(self.bin_dir):
            item_path = os.path.join(self.bin_dir, item)
            if os.path.isfile(item_path) and os.access(item_path, os.X_OK):
                tools.append(item)
        
        return sorted(tools)


# Global instance for easy access
tool_manager = ToolManager()