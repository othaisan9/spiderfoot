/**
 * SpiderFoot Modern JavaScript Module
 * 
 * @module spiderfoot-modern
 * @description Modern ES6+ rewrite of SpiderFoot frontend functionality
 * @author SpiderFoot Team
 * @license MIT
 */

// Theme Manager Class
class ThemeManager {
    constructor() {
        this.themeToggler = document.getElementById('theme-toggler');
        this.togglerText = document.getElementById('toggler-text');
        this.currentTheme = localStorage.getItem('theme') || 'light';
        this.init();
    }

    init() {
        this.applyTheme();
        if (this.themeToggler) {
            this.themeToggler.addEventListener('click', () => this.toggleTheme());
        }
    }

    applyTheme() {
        const isDark = this.currentTheme === 'dark';
        const cssFile = isDark ? 'dark.css' : 'spiderfoot.css';
        
        // Update CSS link
        let themeLink = document.getElementById('theme-stylesheet');
        if (!themeLink) {
            themeLink = document.createElement('link');
            themeLink.id = 'theme-stylesheet';
            themeLink.rel = 'stylesheet';
            themeLink.type = 'text/css';
            document.head.appendChild(themeLink);
        }
        themeLink.href = `${window.docroot}/static/css/${cssFile}`;
        
        // Update UI
        if (this.togglerText) {
            this.togglerText.innerText = isDark ? 'Light Mode' : 'Dark Mode';
        }
        if (this.themeToggler) {
            this.themeToggler.checked = isDark;
        }
    }

    toggleTheme() {
        this.currentTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('theme', this.currentTheme);
        this.applyTheme();
    }
}

// SpiderFoot API Client
class SpiderFootAPI {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl || window.docroot || '';
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        };

        try {
            const response = await fetch(url, { ...defaultOptions, ...options });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    // Scan operations
    async deleteScan(scanId) {
        return this.request(`/scandelete?id=${scanId}`);
    }

    async search(scanId, value, type) {
        return this.request('/search', {
            method: 'POST',
            body: JSON.stringify({ id: scanId, eventType: type, value: value })
        });
    }

    async getScanInfo(scanId) {
        return this.request(`/scaninfo?id=${scanId}`);
    }

    async getScanList() {
        return this.request('/scanlist');
    }

    async startScan(scanData) {
        return this.request('/startscan', {
            method: 'POST',
            body: JSON.stringify(scanData)
        });
    }

    // Module operations
    async getModules() {
        return this.request('/modules');
    }

    async getModuleInfo(moduleName) {
        return this.request(`/moduleinfo?module=${moduleName}`);
    }
}

// Utility functions
const SpiderFootUtils = {
    /**
     * Replace SFURL tags with actual links
     * @param {string} data - HTML string containing SFURL tags
     * @returns {string} HTML with replaced links
     */
    replaceSfUrlTag(data) {
        if (!data) return '';
        
        // Handle HTML-encoded tags
        data = data.replace(
            /&lt;sfurl&gt;(.*)&lt;\/sfurl&gt;/gim,
            '<a target="_blank" rel="noopener noreferrer" href="$1">$1</a>'
        );
        
        // Handle regular tags
        data = data.replace(
            /<sfurl>(.*)<\/sfurl>/gim,
            '<a target="_blank" rel="noopener noreferrer" href="$1">$1</a>'
        );
        
        return data;
    },

    /**
     * Remove SFURL tags
     * @param {string} data - String containing SFURL tags
     * @returns {string} String with removed tags
     */
    removeSfUrlTag(data) {
        if (!data) return '';
        
        return data
            .replace(/&lt;\/?sfurl&gt;/gi, '')
            .replace(/<\/?sfurl>/gi, '');
    },

    /**
     * Format bytes to human readable size
     * @param {number} bytes - Number of bytes
     * @param {number} decimals - Number of decimal places
     * @returns {string} Formatted size string
     */
    formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    },

    /**
     * Format date to locale string
     * @param {string|Date} date - Date to format
     * @returns {string} Formatted date string
     */
    formatDate(date) {
        if (!date) return '';
        
        const d = date instanceof Date ? date : new Date(date);
        return d.toLocaleString();
    },

    /**
     * Debounce function execution
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Show notification using alertify
     * @param {string} type - Notification type (success, error, warning, message)
     * @param {string} title - Notification title
     * @param {string} message - Notification message
     */
    notify(type, title, message) {
        const icon = {
            success: 'glyphicon-ok-circle',
            error: 'glyphicon-remove-circle',
            warning: 'glyphicon-warning-sign',
            message: 'glyphicon-info-sign'
        }[type] || 'glyphicon-info-sign';

        const content = `<i class="glyphicon ${icon}"></i> <b>${title}</b>${message ? '<br/><br/>' + message : ''}`;
        
        if (window.alertify && window.alertify[type]) {
            window.alertify[type](content);
        } else {
            console.log(`[${type.toUpperCase()}] ${title}: ${message}`);
        }
    }
};

// Module Manager for handling unified modules
class ModuleManager {
    constructor(api) {
        this.api = api;
        this.modules = new Map();
        this.unifiedModules = {
            'sfp_unified_dns_filters': {
                name: 'Unified DNS Filters',
                description: 'Unified module for DNS filtering services (AdGuard, Cloudflare, Quad9, etc.)',
                replaces: [
                    'sfp_adguard_dns', 'sfp_cleanbrowsing', 'sfp_cloudflaredns',
                    'sfp_comodo', 'sfp_dns_for_family', 'sfp_opendns',
                    'sfp_quad9', 'sfp_yandexdns'
                ]
            },
            'sfp_unified_ip_info': {
                name: 'Unified IP Information',
                description: 'Unified module for IP geolocation and information services',
                replaces: [
                    'sfp_ipapico', 'sfp_ipapicom', 'sfp_ipstack',
                    'sfp_ipregistry', 'sfp_ipinfo'
                ]
            },
            'sfp_unified_search_engines': {
                name: 'Unified Search Engines',
                description: 'Unified module for web search engines (Bing, DuckDuckGo, Torch)',
                replaces: [
                    'sfp_bingsearch', 'sfp_duckduckgo', 'sfp_torch',
                    'sfp_onionsearchengine', 'sfp_onioncity'
                ]
            }
        };
    }

    async loadModules() {
        try {
            const moduleData = await this.api.getModules();
            this.processModules(moduleData);
        } catch (error) {
            SpiderFootUtils.notify('error', 'Failed to load modules', error.message);
        }
    }

    processModules(moduleData) {
        // Clear existing modules
        this.modules.clear();

        // Process each module
        Object.entries(moduleData).forEach(([moduleId, moduleInfo]) => {
            // Check if this module has been replaced by a unified module
            const isReplaced = Object.values(this.unifiedModules).some(
                unified => unified.replaces.includes(moduleId)
            );

            if (!isReplaced) {
                this.modules.set(moduleId, {
                    id: moduleId,
                    ...moduleInfo,
                    requiresApiKey: this.checkApiKeyRequirement(moduleInfo)
                });
            }
        });

        // Add unified modules
        Object.entries(this.unifiedModules).forEach(([moduleId, moduleInfo]) => {
            this.modules.set(moduleId, {
                id: moduleId,
                ...moduleInfo,
                isUnified: true,
                requiresApiKey: false
            });
        });
    }

    checkApiKeyRequirement(moduleInfo) {
        if (!moduleInfo.opts) return false;
        return Object.keys(moduleInfo.opts).some(key => key.includes('api_key'));
    }

    getModulesByCategory(category) {
        return Array.from(this.modules.values()).filter(
            module => module.group === category
        );
    }

    getModulesByUseCase(useCase) {
        return Array.from(this.modules.values()).filter(
            module => module.group === useCase || useCase === 'all'
        );
    }

    searchModules(query) {
        const lowerQuery = query.toLowerCase();
        return Array.from(this.modules.values()).filter(
            module => 
                module.name.toLowerCase().includes(lowerQuery) ||
                module.description.toLowerCase().includes(lowerQuery)
        );
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize theme manager
    window.themeManager = new ThemeManager();
    
    // Initialize API client
    window.sfAPI = new SpiderFootAPI();
    
    // Initialize module manager
    window.moduleManager = new ModuleManager(window.sfAPI);
    
    // Export utilities to global scope for backward compatibility
    window.sf = {
        ...SpiderFootUtils,
        api: window.sfAPI,
        modules: window.moduleManager
    };
    
    console.log('SpiderFoot Modern JavaScript initialized');
});

// Export for ES6 modules
export { ThemeManager, SpiderFootAPI, SpiderFootUtils, ModuleManager };