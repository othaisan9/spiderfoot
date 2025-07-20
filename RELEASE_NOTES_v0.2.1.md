# 🦇 SpiderFoot BE (BAT INTELLIGENCE Edition) v0.2.1

**Release Date**: January 2025  
**Edition**: BAT INTELLIGENCE Edition  
**Powered by**: SpiderFoot

---

## 🚀 **What's New in v0.2.1**

### 🕷️ **Web Spider Enhancements**
- **Configurable File Extension Filtering**: New `enable_filterfiles` option allows users to control file type filtering
  - Enable/disable filtering of images, PDFs, and other file types on demand
  - Maintains backward compatibility with existing configurations
  - Useful for investigations requiring image analysis or document collection

### 🦇 **BAT INTELLIGENCE Branding**
- **Dynamic Logo Display**: BAT_LOGO now prominently displayed in navigation bar
  - Automatic switching between dark and light themes
  - Professional branding for the BAT INTELLIGENCE Edition
  - Centered positioning for optimal visibility

### 🔧 **Bug Fixes & Improvements**
- Fixed file extension filtering in Web Spider module
- Improved theme switching reliability
- Enhanced UI consistency across dark/light modes
- Better error handling in module configuration

---

## 📦 **Installation & Upgrade**

### **From v0.2.0**
```bash
# Pull latest changes
git pull origin v0.2-neo4j-integration

# Install/update dependencies
pip install -r requirements.txt
pip install -r requirements_neo4j.txt  # If using Neo4j features

# Restart SpiderFoot BE
python sf.py -l 127.0.0.1:5001
```

### **Docker Deployment**
```bash
# With Neo4j support
docker-compose -f docker-compose.neo4j.yml up -d

# Standard deployment
docker-compose up -d
```

---

## 🔧 **Configuration Changes**

### **Web Spider Module**
The Web Spider module now includes an additional configuration option:

```python
'enable_filterfiles': True  # Toggle file extension filtering
```

When set to `False`, the spider will collect all file types including:
- Images (PNG, JPG, GIF, ICO)
- Documents (PDF, DOC, XLS)
- Media files (MP4, MP3, AVI)
- Archives (ZIP, RAR, TAR)

---

## 📈 **Performance Metrics**

| Component | Status | Notes |
|-----------|--------|-------|
| **Web Spider** | ✅ Enhanced | Configurable filtering |
| **UI/UX** | ✅ Improved | BAT_LOGO integration |
| **Theme Support** | ✅ Stable | Reliable dark/light switching |
| **Neo4j Integration** | ✅ Unchanged | All v0.2 features maintained |

---

## 🐛 **Known Issues**
- Module settings require server restart to take effect
- Large image collections may impact scan performance when filtering is disabled

---

## 🔮 **Coming in v0.3**
- Hot-reload for module configuration changes
- Advanced file content analysis capabilities
- Enhanced graph visualization features
- Machine learning correlation engine

---

## 📚 **Documentation**
- Updated module documentation for Web Spider
- New configuration examples in user guide
- Enhanced troubleshooting section

---

## 🙏 **Contributors**
- SpiderFoot BE Development Team
- Original SpiderFoot by Steve Micallef
- Community contributors and testers

---

## 📄 **License**
This project maintains the same MIT license as the original SpiderFoot project.

---

**🦇 SpiderFoot BE v0.2.1 - Empowering OSINT with Intelligence** 🦇

*Powered by SpiderFoot | Enhanced with BAT INTELLIGENCE*