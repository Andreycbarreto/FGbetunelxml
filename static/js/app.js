/**
 * NFe XML Processor - Main JavaScript Application
 * Handles UI interactions, file uploads, and real-time updates
 */

// Global app object
window.NFEApp = {
    init: function() {
        this.initFeatherIcons();
        this.initTooltips();
        this.initFileUpload();
        this.initProcessingUpdates();
        this.initGlobalEventHandlers();
        this.initSearchAndFilters();
    },

    // Initialize Feather icons
    initFeatherIcons: function() {
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    },

    // Initialize Bootstrap tooltips
    initTooltips: function() {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function(tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    },

    // Enhanced file upload functionality
    initFileUpload: function() {
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('fileInput');
        
        if (!uploadZone || !fileInput) return;

        // Drag and drop events
        uploadZone.addEventListener('dragover', this.handleDragOver.bind(this));
        uploadZone.addEventListener('dragleave', this.handleDragLeave.bind(this));
        uploadZone.addEventListener('drop', this.handleDrop.bind(this));
        
        // File input change
        fileInput.addEventListener('change', this.handleFileSelect.bind(this));
    },

    handleDragOver: function(e) {
        e.preventDefault();
        e.stopPropagation();
        e.currentTarget.classList.add('dragover');
    },

    handleDragLeave: function(e) {
        e.preventDefault();
        e.stopPropagation();
        e.currentTarget.classList.remove('dragover');
    },

    handleDrop: function(e) {
        e.preventDefault();
        e.stopPropagation();
        e.currentTarget.classList.remove('dragover');
        
        const files = Array.from(e.dataTransfer.files);
        this.processSelectedFiles(files);
    },

    handleFileSelect: function(e) {
        const files = Array.from(e.target.files);
        this.processSelectedFiles(files);
    },

    processSelectedFiles: function(files) {
        // Filter XML files only
        const xmlFiles = files.filter(file => 
            file.name.toLowerCase().endsWith('.xml') && file.size <= 50 * 1024 * 1024
        );

        if (xmlFiles.length !== files.length) {
            this.showAlert('warning', 'Apenas arquivos XML até 50MB são aceitos.');
        }

        if (xmlFiles.length > 0) {
            this.updateFileList(xmlFiles);
            this.updateUploadButton(true);
        }
    },

    updateFileList: function(files) {
        const fileList = document.getElementById('fileList');
        const container = fileList?.querySelector('.file-list-container');
        
        if (!container) return;

        fileList.style.display = 'block';
        container.innerHTML = files.map((file, index) => `
            <div class="file-item d-flex justify-content-between align-items-center p-3 border rounded mb-2">
                <div class="d-flex align-items-center">
                    <i class="feather-file-text me-3 text-primary"></i>
                    <div>
                        <strong>${file.name}</strong>
                        <small class="text-muted d-block">${this.formatFileSize(file.size)}</small>
                    </div>
                </div>
                <button type="button" class="btn btn-sm btn-outline-danger" onclick="NFEApp.removeFile(${index})">
                    <i class="feather-x"></i>
                </button>
            </div>
        `).join('');

        // Replace feather icons
        this.initFeatherIcons();
    },

    removeFile: function(index) {
        // This would need to be implemented with a proper file management system
        console.log('Remove file at index:', index);
    },

    updateUploadButton: function(enabled) {
        const uploadBtn = document.getElementById('uploadBtn');
        if (uploadBtn) {
            uploadBtn.disabled = !enabled;
        }
    },

    formatFileSize: function(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // Processing status updates
    initProcessingUpdates: function() {
        // Auto-refresh processing status more frequently on processing page
        if (window.location.pathname.includes('/processing')) {
            // Start with immediate check
            this.updateProcessingStatus();
            // Then check every 5 seconds for faster response
            setInterval(this.updateProcessingStatus.bind(this), 5000);
        }
    },

    updateProcessingStatus: function() {
        fetch('/api/processing_status')
            .then(response => response.json())
            .then(data => {
                this.updateStatusDisplay(data);
                this.updateProgressBar(data);
                
                // Auto refresh when processing is complete
                if (data.total_files > 0 && data.processed_files === data.total_files && 
                    data.processing_files === 0 && data.pending_files === 0) {
                    
                    const statusElement = document.getElementById('processingStatus');
                    if (statusElement) {
                        statusElement.innerHTML = `
                            <i class="feather-check me-2"></i>
                            Todos os arquivos foram processados - Atualizando página...
                        `;
                    }
                    
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                }
            })
            .catch(error => {
                console.error('Error updating processing status:', error);
            });
    },

    updateStatusDisplay: function(data) {
        const statusElement = document.getElementById('processingStatus');
        if (!statusElement) return;

        if (data.processing_files > 0) {
            statusElement.innerHTML = `
                <i class="feather-clock me-2"></i>
                Processando ${data.processing_files} arquivo(s)...
            `;
        } else if (data.pending_files > 0) {
            statusElement.innerHTML = `
                <i class="feather-pause me-2"></i>
                ${data.pending_files} arquivo(s) aguardando processamento
            `;
        } else if (data.total_files > 0) {
            statusElement.innerHTML = `
                <i class="feather-check me-2"></i>
                Todos os arquivos foram processados
            `;
        }
    },

    updateProgressBar: function(data) {
        const progressBar = document.getElementById('processingProgress');
        if (!progressBar) return;

        const progress = data.total_files > 0 
            ? (data.processed_files / data.total_files) * 100 
            : 0;
        
        progressBar.style.width = progress + '%';
        progressBar.setAttribute('aria-valuenow', progress);
    },

    // Global event handlers
    initGlobalEventHandlers: function() {
        // Handle form submissions with loading states
        document.addEventListener('submit', this.handleFormSubmit.bind(this));
        
        // Handle AJAX errors globally
        window.addEventListener('unhandledrejection', this.handleUnhandledRejection.bind(this));
        
        // Auto-hide alerts after 5 seconds
        this.autoHideAlerts();
    },

    handleFormSubmit: function(e) {
        const form = e.target;
        if (!form.matches('form[data-loading]')) return;

        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="spinner-border spinner-border-sm me-2"></i>Processando...';
            submitBtn.disabled = true;

            // Re-enable button after 30 seconds as fallback
            setTimeout(() => {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }, 30000);
        }
    },

    handleUnhandledRejection: function(event) {
        console.error('Unhandled promise rejection:', event.reason);
        this.showAlert('danger', 'Erro de comunicação com o servidor. Tente novamente.');
    },

    autoHideAlerts: function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(alert => {
            setTimeout(() => {
                if (alert.parentNode) {
                    const bsAlert = new bootstrap.Alert(alert);
                    bsAlert.close();
                }
            }, 5000);
        });
    },

    // Search and filter functionality
    initSearchAndFilters: function() {
        // Global search functionality
        const searchInput = document.getElementById('globalSearch');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce(this.handleGlobalSearch.bind(this), 300));
        }

        // Table filters
        const filterInputs = document.querySelectorAll('[data-filter-table]');
        filterInputs.forEach(input => {
            input.addEventListener('input', this.debounce(this.handleTableFilter.bind(this), 300));
        });
    },

    handleGlobalSearch: function(e) {
        const query = e.target.value.toLowerCase();
        const searchableElements = document.querySelectorAll('[data-searchable]');
        
        searchableElements.forEach(element => {
            const text = element.textContent.toLowerCase();
            const parent = element.closest('tr, .card, .list-item');
            
            if (parent) {
                parent.style.display = text.includes(query) ? '' : 'none';
            }
        });
    },

    handleTableFilter: function(e) {
        const input = e.target;
        const tableId = input.dataset.filterTable;
        const column = input.dataset.filterColumn;
        const table = document.getElementById(tableId);
        
        if (!table) return;

        const query = input.value.toLowerCase();
        const rows = table.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            const cell = row.cells[column];
            if (cell) {
                const text = cell.textContent.toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            }
        });
    },

    // Utility functions
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func.apply(this, args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    showAlert: function(type, message, persistent = false) {
        const alertsContainer = document.querySelector('.container');
        if (!alertsContainer) return;

        const alertId = 'alert-' + Date.now();
        const alertHTML = `
            <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show mt-3 ${persistent ? 'alert-permanent' : ''}" role="alert">
                <i class="feather-${this.getAlertIcon(type)} me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        alertsContainer.insertAdjacentHTML('afterbegin', alertHTML);
        this.initFeatherIcons();

        if (!persistent) {
            setTimeout(() => {
                const alert = document.getElementById(alertId);
                if (alert) {
                    const bsAlert = new bootstrap.Alert(alert);
                    bsAlert.close();
                }
            }, 5000);
        }
    },

    getAlertIcon: function(type) {
        const icons = {
            'success': 'check-circle',
            'danger': 'alert-triangle',
            'warning': 'alert-triangle',
            'info': 'info',
            'primary': 'info',
            'secondary': 'info'
        };
        return icons[type] || 'info';
    },

    // API helpers
    apiCall: function(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        };

        return fetch(url, { ...defaultOptions, ...options })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .catch(error => {
                console.error('API call failed:', error);
                this.showAlert('danger', 'Erro de comunicação com o servidor');
                throw error;
            });
    },

    // Clipboard helper
    copyToClipboard: function(text, successMessage = 'Copiado para a área de transferência!') {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(() => {
                this.showAlert('success', successMessage);
            }).catch(err => {
                console.error('Failed to copy: ', err);
                this.fallbackCopyTextToClipboard(text);
            });
        } else {
            this.fallbackCopyTextToClipboard(text);
        }
    },

    fallbackCopyTextToClipboard: function(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.top = '0';
        textArea.style.left = '0';
        textArea.style.position = 'fixed';
        
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            const successful = document.execCommand('copy');
            if (successful) {
                this.showAlert('success', 'Copiado para a área de transferência!');
            } else {
                this.showAlert('warning', 'Não foi possível copiar automaticamente');
            }
        } catch (err) {
            console.error('Fallback: Copying text command was unsuccessful', err);
            this.showAlert('warning', 'Não foi possível copiar automaticamente');
        }
        
        document.body.removeChild(textArea);
    },

    // Theme management
    initTheme: function() {
        // The app uses Bootstrap's dark theme by default
        // This function can be extended for theme switching if needed
        const savedTheme = localStorage.getItem('nfe-theme');
        if (savedTheme) {
            document.documentElement.setAttribute('data-bs-theme', savedTheme);
        }
    },

    setTheme: function(theme) {
        document.documentElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('nfe-theme', theme);
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    NFEApp.init();
});

// Global utility functions for inline usage
window.deleteFile = function(fileId) {
    if (confirm('Tem certeza que deseja excluir este arquivo? Esta ação não pode ser desfeita.')) {
        fetch(`/delete_file/${fileId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => {
            if (response.ok) {
                NFEApp.showAlert('success', 'Arquivo excluído com sucesso');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                NFEApp.showAlert('danger', 'Erro ao excluir arquivo');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            NFEApp.showAlert('danger', 'Erro de comunicação');
        });
    }
};

window.processNextFile = function() {
    const button = event.target;
    const originalText = button.innerHTML;
    
    button.innerHTML = '<i class="spinner-border spinner-border-sm me-2"></i>Processando...';
    button.disabled = true;
    
    fetch('/process_next', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            NFEApp.showAlert('success', data.message);
            setTimeout(() => window.location.reload(), 2000);
        } else {
            NFEApp.showAlert('danger', data.message);
            button.innerHTML = originalText;
            button.disabled = false;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        NFEApp.showAlert('danger', 'Erro de comunicação com o servidor');
        button.innerHTML = originalText;
        button.disabled = false;
    });
};

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NFEApp;
}
