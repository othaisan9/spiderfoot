# -*- coding: utf-8 -*-
"""
SpiderFoot BE Nuclei Wrapper

Provides a wrapper for nuclei tool to use project-local configuration and templates.
"""

import os
import subprocess
from typing import List, Dict, Optional
from spiderfoot.tool_utils import tool_manager


class NucleiWrapper:
    """Wrapper for nuclei tool with project-local configuration."""
    
    def __init__(self):
        """Initialize nuclei wrapper."""
        self.project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.tools_dir = os.path.join(self.project_dir, "tools")
        self.config_dir = os.path.join(self.tools_dir, ".config", "nuclei")
        self.templates_dir = os.path.join(self.tools_dir, "nuclei-templates")
        
        # Create config directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Create nuclei config file
        self._create_config()
    
    def _create_config(self):
        """Create nuclei configuration file."""
        config_path = os.path.join(self.config_dir, "config.yaml")
        
        if not os.path.exists(config_path):
            config_content = f"""# Nuclei Configuration for SpiderFoot BE
# See https://nuclei.projectdiscovery.io/nuclei/get-started/#nuclei-config

# Template directories
templates-directory: {self.templates_dir}

# Custom templates directory
custom-templates: {os.path.join(self.tools_dir, "custom-nuclei-templates")}

# Output directory
output-directory: {os.path.join(self.project_dir, "nuclei-output")}

# Rate limiting
rate-limit: 150
bulk-size: 25
concurrency: 25

# Headers
header:
  - 'User-Agent: SpiderFoot-BE/1.0'

# Reporting
reporting:
  markdown:
    enabled: true
    directory: {os.path.join(self.project_dir, "nuclei-reports")}
"""
            with open(config_path, 'w') as f:
                f.write(config_content)
    
    def run_scan(self, target: str, templates: Optional[List[str]] = None,
                 severity: Optional[List[str]] = None,
                 output_format: str = "json") -> Dict:
        """Run nuclei scan on target.
        
        Args:
            target: Target URL or domain
            templates: List of template IDs or paths to use
            severity: List of severities to scan for (critical, high, medium, low, info)
            output_format: Output format (json, markdown, csv)
            
        Returns:
            Dictionary containing scan results
        """
        nuclei_path = tool_manager.get_tool_path('nuclei')
        if not nuclei_path:
            raise RuntimeError("Nuclei not found. Please install it using install_tools.py")
        
        # Build command
        cmd = [
            nuclei_path,
            '-target', target,
            '-config', os.path.join(self.config_dir, 'config.yaml'),
            '-disable-update-check',
            '-json'
        ]
        
        # Add templates if specified
        if templates:
            for template in templates:
                cmd.extend(['-t', template])
        
        # Add severity filters if specified
        if severity:
            cmd.extend(['-severity', ','.join(severity)])
        
        # Set environment
        env = os.environ.copy()
        env['HOME'] = self.tools_dir
        env['NUCLEI_TEMPLATES_PATH'] = self.templates_dir
        
        # Run nuclei
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': result.stderr,
                    'command': ' '.join(cmd)
                }
            
            # Parse JSON output
            import json
            results = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            
            return {
                'success': True,
                'results': results,
                'count': len(results)
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Scan timed out after 5 minutes'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_templates(self) -> bool:
        """Update nuclei templates.
        
        Returns:
            True if successful, False otherwise
        """
        nuclei_path = tool_manager.get_tool_path('nuclei')
        if not nuclei_path:
            return False
        
        env = os.environ.copy()
        env['HOME'] = self.tools_dir
        env['NUCLEI_TEMPLATES_PATH'] = self.templates_dir
        
        try:
            result = subprocess.run(
                [nuclei_path, '-update-templates'],
                capture_output=True,
                text=True,
                env=env
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def list_templates(self) -> List[Dict]:
        """List available nuclei templates.
        
        Returns:
            List of template information
        """
        nuclei_path = tool_manager.get_tool_path('nuclei')
        if not nuclei_path:
            return []
        
        env = os.environ.copy()
        env['HOME'] = self.tools_dir
        env['NUCLEI_TEMPLATES_PATH'] = self.templates_dir
        
        try:
            result = subprocess.run(
                [nuclei_path, '-tl'],
                capture_output=True,
                text=True,
                env=env
            )
            
            if result.returncode != 0:
                return []
            
            templates = []
            for line in result.stdout.strip().split('\n'):
                if line and not line.startswith('['):
                    templates.append({'id': line.strip()})
            
            return templates
            
        except Exception:
            return []


# Global instance
nuclei = NucleiWrapper()