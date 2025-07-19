/**
 * SpiderFoot New Scan Page - Modern JavaScript
 * 
 * @module spiderfoot.newscan-modern
 * @description Modern ES6+ implementation of new scan functionality
 * @author SpiderFoot Team
 * @license MIT
 */

class NewScanManager {
    constructor() {
        this.tabs = ['use', 'type', 'module'];
        this.activeTab = 'use';
        this.selectedModules = new Set();
        this.init();
    }

    init() {
        // Setup event listeners
        this.setupTabListeners();
        this.setupButtonListeners();
        this.setupFormValidation();
        
        // Initialize tooltips
        this.initTooltips();
        
        // Load saved preferences
        this.loadPreferences();
    }

    setupTabListeners() {
        this.tabs.forEach(tab => {
            const tabElement = document.getElementById(`${tab}tab`);
            if (tabElement) {
                tabElement.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.switchTab(tab);
                });
            }
        });
    }

    setupButtonListeners() {
        // Select/Deselect all buttons
        const selectAllBtn = document.getElementById('btn-select-all');
        const deselectAllBtn = document.getElementById('btn-deselect-all');
        const runScanBtn = document.getElementById('btn-run-scan');

        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.selectAll();
            });
        }

        if (deselectAllBtn) {
            deselectAllBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.deselectAll();
            });
        }

        if (runScanBtn) {
            runScanBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.submitForm();
            });
        }
    }

    setupFormValidation() {
        const scanTarget = document.getElementById('scantarget');
        const scanName = document.getElementById('scanname');

        if (scanTarget) {
            scanTarget.addEventListener('input', () => this.validateTarget());
        }

        if (scanName) {
            scanName.addEventListener('input', () => this.validateScanName());
        }
    }

    initTooltips() {
        // Initialize Bootstrap tooltips
        if (typeof $ !== 'undefined' && $.fn.tooltip) {
            $('[rel="tooltip"]').tooltip();
            $('#scantarget').popover({ 
                'html': true, 
                'animation': true, 
                'trigger': 'focus'
            });
        }
    }

    loadPreferences() {
        // Load saved preferences from localStorage
        const savedTab = localStorage.getItem('sf_newscan_tab');
        if (savedTab && this.tabs.includes(savedTab)) {
            this.switchTab(savedTab);
        }

        const savedModules = localStorage.getItem('sf_selected_modules');
        if (savedModules) {
            try {
                const modules = JSON.parse(savedModules);
                modules.forEach(module => this.selectedModules.add(module));
                this.updateModuleCheckboxes();
            } catch (e) {
                console.error('Failed to load saved modules:', e);
            }
        }
    }

    savePreferences() {
        localStorage.setItem('sf_newscan_tab', this.activeTab);
        localStorage.setItem('sf_selected_modules', JSON.stringify([...this.selectedModules]));
    }

    switchTab(tabname) {
        // Hide current tab
        const currentTable = document.getElementById(`${this.activeTab}table`);
        const currentTab = document.getElementById(`${this.activeTab}tab`);
        
        if (currentTable) currentTable.style.display = 'none';
        if (currentTab) currentTab.classList.remove('active');

        // Show new tab
        const newTable = document.getElementById(`${tabname}table`);
        const newTab = document.getElementById(`${tabname}tab`);
        
        if (newTable) newTable.style.display = 'table';
        if (newTab) newTab.classList.add('active');

        this.activeTab = tabname;

        // Show/hide selectors
        const selectors = document.getElementById('selectors');
        if (selectors) {
            selectors.style.display = this.activeTab === 'use' ? 'none' : 'block';
        }

        this.savePreferences();
    }

    selectAll() {
        const checkboxes = document.querySelectorAll(`[id^=${this.activeTab}_]`);
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
            const moduleId = checkbox.id.replace(`${this.activeTab}_`, '');
            this.selectedModules.add(moduleId);
        });
        this.savePreferences();
    }

    deselectAll() {
        const checkboxes = document.querySelectorAll(`[id^=${this.activeTab}_]`);
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
            const moduleId = checkbox.id.replace(`${this.activeTab}_`, '');
            this.selectedModules.delete(moduleId);
        });
        this.savePreferences();
    }

    updateModuleCheckboxes() {
        this.selectedModules.forEach(moduleId => {
            const checkbox = document.getElementById(`module_${moduleId}`);
            if (checkbox) checkbox.checked = true;
        });
    }

    validateTarget() {
        const scanTarget = document.getElementById('scantarget');
        if (!scanTarget) return false;

        const value = scanTarget.value.trim();
        if (!value) {
            this.setFieldError(scanTarget, 'Please enter a scan target');
            return false;
        }

        // Basic validation for different target types
        const targetType = this.detectTargetType(value);
        if (!targetType) {
            this.setFieldError(scanTarget, 'Invalid target format');
            return false;
        }

        this.clearFieldError(scanTarget);
        return true;
    }

    validateScanName() {
        const scanName = document.getElementById('scanname');
        if (!scanName) return false;

        const value = scanName.value.trim();
        if (!value) {
            this.setFieldError(scanName, 'Please enter a scan name');
            return false;
        }

        if (value.length < 3) {
            this.setFieldError(scanName, 'Scan name must be at least 3 characters');
            return false;
        }

        this.clearFieldError(scanName);
        return true;
    }

    detectTargetType(target) {
        // Domain
        if (/^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9](?:\.[a-zA-Z]{2,})+$/.test(target)) {
            return 'DOMAIN';
        }
        
        // IPv4
        if (/^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/.test(target)) {
            return 'IPV4';
        }
        
        // IPv6
        if (/^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))$/.test(target)) {
            return 'IPV6';
        }
        
        // Email
        if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(target)) {
            return 'EMAIL';
        }
        
        // Phone (E.164 format)
        if (/^\+[1-9]\d{1,14}$/.test(target)) {
            return 'PHONE';
        }
        
        // Bitcoin address
        if (/^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$/.test(target)) {
            return 'BITCOIN';
        }
        
        // ASN
        if (/^\d+$/.test(target) && parseInt(target) > 0 && parseInt(target) < 4294967296) {
            return 'ASN';
        }
        
        // Human name or username (in quotes)
        if (/^"[^"]+"$/.test(target)) {
            return target.toLowerCase().includes(' ') ? 'HUMAN_NAME' : 'USERNAME';
        }
        
        // Subnet
        if (/^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/\d{1,2}$/.test(target)) {
            return 'SUBNET';
        }
        
        return null;
    }

    setFieldError(field, message) {
        field.classList.add('is-invalid');
        const feedbackElement = field.nextElementSibling;
        if (feedbackElement && feedbackElement.classList.contains('invalid-feedback')) {
            feedbackElement.textContent = message;
        } else {
            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            feedback.textContent = message;
            field.parentNode.appendChild(feedback);
        }
    }

    clearFieldError(field) {
        field.classList.remove('is-invalid');
        const feedbackElement = field.nextElementSibling;
        if (feedbackElement && feedbackElement.classList.contains('invalid-feedback')) {
            feedbackElement.remove();
        }
    }

    async submitForm() {
        // Validate form
        if (!this.validateTarget() || !this.validateScanName()) {
            window.sf.notify('error', 'Validation Error', 'Please fix the errors before submitting');
            return;
        }

        // Collect selected items
        const selectedList = [];
        const checkboxes = document.querySelectorAll(`[id^=${this.activeTab}_]:checked`);
        
        checkboxes.forEach(checkbox => {
            selectedList.push(checkbox.id);
        });

        // Update hidden fields
        const moduleListField = document.getElementById('modulelist');
        const typeListField = document.getElementById('typelist');
        
        if (this.activeTab === 'module' && moduleListField) {
            moduleListField.value = selectedList.join(',');
            if (typeListField) typeListField.value = '';
        } else if (this.activeTab === 'type' && typeListField) {
            typeListField.value = selectedList.join(',');
            if (moduleListField) moduleListField.value = '';
        }

        // Show loading indicator
        const runButton = document.getElementById('btn-run-scan');
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<i class="spinner-border spinner-border-sm" role="status"></i> Starting scan...';
        }

        // Submit form
        const form = document.querySelector('form');
        if (form) {
            form.submit();
        }
    }

    // Public method to set selected modules (for use from template)
    setSelectedModules(moduleList) {
        if (!moduleList) return;
        
        const modules = moduleList.split(',');
        modules.forEach(module => {
            if (module) {
                this.selectedModules.add(module);
                const checkbox = document.getElementById(`module_${module}`);
                if (checkbox) {
                    checkbox.checked = true;
                }
            }
        });
        
        if (modules.length > 0) {
            this.switchTab('module');
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.newScanManager = new NewScanManager();
    
    // Handle template-provided selected modules
    const selectedModsElement = document.querySelector('[data-selected-mods]');
    if (selectedModsElement) {
        const selectedMods = selectedModsElement.dataset.selectedMods;
        if (selectedMods) {
            window.newScanManager.setSelectedModules(selectedMods);
        }
    }
});

// Export for ES6 modules
export { NewScanManager };