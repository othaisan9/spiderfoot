#!/bin/bash

# SpiderFoot BE v0.2.1 Release Build Script
# BAT INTELLIGENCE Edition

VERSION="0.2.1"
RELEASE_NAME="spiderfoot-be-v${VERSION}"
BUILD_DIR="dist"
RELEASE_DIR="${BUILD_DIR}/${RELEASE_NAME}"

echo "🦇 Building SpiderFoot BE v${VERSION} - BAT INTELLIGENCE Edition"
echo "================================================"

# Clean previous builds
echo "→ Cleaning previous builds..."
rm -rf ${BUILD_DIR}
mkdir -p ${RELEASE_DIR}

# Copy all files
echo "→ Copying all project files..."
# Copy everything except cache/temp directories
for item in *; do
    if [[ "$item" != "dist" && "$item" != "__pycache__" && "$item" != ".venv" && "$item" != ".git" && "$item" != ".pytest_cache" && "$item" != ".claude" && "$item" != "node_modules" ]]; then
        if [[ -f "$item" ]]; then
            cp "$item" ${RELEASE_DIR}/ 2>/dev/null || true
        elif [[ -d "$item" ]]; then
            cp -r "$item" ${RELEASE_DIR}/ 2>/dev/null || true
        fi
    fi
done

# Copy hidden files that we want
cp .gitignore ${RELEASE_DIR}/ 2>/dev/null || true
cp .github ${RELEASE_DIR}/ -r 2>/dev/null || true

# Clean up any remaining cache files
echo "→ Cleaning up any remaining cache files..."
find ${RELEASE_DIR} -name "*.pyc" -delete 2>/dev/null || true
find ${RELEASE_DIR} -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find ${RELEASE_DIR} -name ".DS_Store" -delete 2>/dev/null || true

# Create version file
echo "→ Creating version info..."
cat > ${RELEASE_DIR}/VERSION << EOF
SpiderFoot BE (BAT INTELLIGENCE Edition)
Version: ${VERSION}
Release Date: $(date +"%Y-%m-%d")
Branch: v0.2-neo4j-integration
EOF

# Create quick start guide
echo "→ Creating quick start guide..."
cat > ${RELEASE_DIR}/QUICKSTART.md << 'EOF'
# 🦇 SpiderFoot BE - Quick Start Guide

## Installation

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements_neo4j.txt  # Optional: For Neo4j support
   ```

2. **Start SpiderFoot BE**
   ```bash
   python sf.py -l 127.0.0.1:5001
   ```

3. **Access Web UI**
   Open browser to: http://localhost:5001

## Docker Deployment

**With Neo4j:**
```bash
docker-compose -f docker-compose.neo4j.yml up -d
```

**Standard:**
```bash
docker-compose up -d
```

## Key Features in v0.2.1
- Configurable file extension filtering in Web Spider
- BAT_LOGO branding with dark/light theme support
- Neo4j graph database integration
- High-performance async modules

For full documentation, see README_BE.md
EOF

# Create archive
echo "→ Creating release archives..."
cd ${BUILD_DIR}

# Create tar.gz
tar -czf ${RELEASE_NAME}.tar.gz ${RELEASE_NAME}/
echo "✓ Created ${RELEASE_NAME}.tar.gz"

# Create zip
zip -qr ${RELEASE_NAME}.zip ${RELEASE_NAME}/
echo "✓ Created ${RELEASE_NAME}.zip"

# Calculate checksums
echo "→ Calculating checksums..."
sha256sum ${RELEASE_NAME}.tar.gz > ${RELEASE_NAME}.tar.gz.sha256
sha256sum ${RELEASE_NAME}.zip > ${RELEASE_NAME}.zip.sha256

# Create release notes summary
cat > RELEASE_SUMMARY.txt << EOF
SpiderFoot BE v${VERSION} - BAT INTELLIGENCE Edition
=============================================

Release Archives:
- ${RELEASE_NAME}.tar.gz
- ${RELEASE_NAME}.zip

SHA256 Checksums:
$(cat ${RELEASE_NAME}.tar.gz.sha256)
$(cat ${RELEASE_NAME}.zip.sha256)

Release Date: $(date +"%Y-%m-%d %H:%M:%S")
Git Commit: $(git rev-parse HEAD)

What's New:
- Configurable file extension filtering in Web Spider
- BAT_LOGO integration with theme support
- Bug fixes and performance improvements

See RELEASE_NOTES_v${VERSION}.md for full details.
EOF

echo ""
echo "🎉 Build complete!"
echo "📦 Release packages created in: ${BUILD_DIR}/"
echo ""
ls -lh ${BUILD_DIR}/${RELEASE_NAME}.*
echo ""
echo "🦇 SpiderFoot BE v${VERSION} is ready for distribution!"