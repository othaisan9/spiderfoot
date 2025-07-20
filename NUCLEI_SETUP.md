# Nuclei Setup Guide for SpiderFoot BE

## Dynamic Path Configuration

SpiderFoot BE now supports automatic detection and installation of Nuclei:

### 1. Automatic Detection
The system will first check if Nuclei is already installed system-wide:
- If found: Creates a symlink to the existing installation
- If not found: Installs Nuclei using Go

### 2. Path Configuration

#### For All Systems
When configuring the `sfp_tool_nuclei` module in SpiderFoot Settings:

1. **nuclei_path**: `{project_dir}/tools/bin/nuclei`
2. **template_path**: `{project_dir}/tools/nuclei-templates`

Where `{project_dir}` is your SpiderFoot installation directory.

#### Examples by System

**Linux/macOS:**
```
nuclei_path: /opt/spiderfoot/tools/bin/nuclei
template_path: /opt/spiderfoot/tools/nuclei-templates
```

**Docker:**
```
nuclei_path: /app/tools/bin/nuclei
template_path: /app/tools/nuclei-templates
```

**Custom Installation:**
```
nuclei_path: /home/user/spiderfoot/tools/bin/nuclei
template_path: /home/user/spiderfoot/tools/nuclei-templates
```

## Installation Methods

### Method 1: Using install_tools.py (Recommended)
```bash
cd /path/to/spiderfoot
python install_tools.py --install nuclei
```

This will:
1. Check for existing Nuclei installation
2. Create symlink or install via Go as needed
3. Download/update templates to project directory

### Method 2: Manual Installation

#### If Nuclei is already installed:
```bash
# Create symlink
ln -sf $(which nuclei) /path/to/spiderfoot/tools/bin/nuclei

# Update templates
nuclei -ut -ud /path/to/spiderfoot/tools/nuclei-templates
```

#### If Nuclei needs to be installed:
```bash
# Install via Go
go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest

# Or download binary from releases
wget https://github.com/projectdiscovery/nuclei/releases/download/v2.9.15/nuclei_2.9.15_linux_amd64.zip
unzip nuclei_2.9.15_linux_amd64.zip
mv nuclei /path/to/spiderfoot/tools/bin/

# Update templates
/path/to/spiderfoot/tools/bin/nuclei -ut -ud /path/to/spiderfoot/tools/nuclei-templates
```

## Environment Variables

The following environment variable is set automatically:
```bash
export NUCLEI_TEMPLATES_PATH={project_dir}/tools/nuclei-templates
```

## Docker Deployment

For Docker deployments, the paths are relative to the container:
```dockerfile
# In your Dockerfile
RUN python /app/install_tools.py --install nuclei

# Or manually
RUN go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest && \
    mv /go/bin/nuclei /app/tools/bin/ && \
    /app/tools/bin/nuclei -ut -ud /app/tools/nuclei-templates
```

## Troubleshooting

1. **"nuclei: command not found"**
   - Run: `python install_tools.py --install nuclei`
   - Or install Go and run the install command

2. **"template path does not exist"**
   - Create directory: `mkdir -p {project_dir}/tools/nuclei-templates`
   - Update templates: `nuclei -ut -ud {project_dir}/tools/nuclei-templates`

3. **Permission denied**
   - Ensure write permissions to tools directory
   - Use sudo if necessary (not recommended)

## Notes

1. Templates are always installed locally to the project to ensure consistency
2. The binary can be either system-wide or project-local
3. The `install_tools.py` script handles both scenarios automatically