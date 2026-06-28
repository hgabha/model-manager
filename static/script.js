// ComfyUI Model Manager - JavaScript Functions

let pollInterval;
let configsLoaded = false;

function clearPreviousMessages() {
    // Clear any previous status messages when starting a new action
    const status = document.getElementById('status');
    status.style.display = 'none';
    
    // Hide model info section
    const modelInfo = document.getElementById('modelInfo');
    modelInfo.style.display = 'none';
    
    // Clear the current download section
    const currentDownload = document.getElementById('currentDownload');
    currentDownload.style.display = 'none';
    
    // Clear the download progress text
    const downloadProgress = document.getElementById('downloadProgress');
    downloadProgress.textContent = '';
    
    // Clear the current filename
    const currentFileName = document.getElementById('currentFileName');
    currentFileName.textContent = '';
}

function showStatus(message, type = 'info') {
    const status = document.getElementById('status');
    
    // Check if message contains HTML (like our clickable errors link)
    if (message.includes('<a href')) {
        status.innerHTML = message;
    } else {
        status.textContent = message;
    }
    
    status.className = `status-${type}`;
    status.style.display = 'block';
    
    // Messages persist until the next action is triggered
    // No automatic hiding based on timers
}

function showProgress() {
    document.getElementById('progressContainer').style.display = 'block';
}

function hideProgress() {
   const progressContainer = document.getElementById('progressContainer');
   
   // Keep content visible for 3 seconds first
   setTimeout(() => {
       // Start fade out effect after 3 seconds
       progressContainer.style.transition = 'opacity 2s ease-out';
       progressContainer.style.opacity = '0';
       
       // Actually hide the element after the fade completes (2 more seconds)
       setTimeout(() => {
           progressContainer.style.display = 'none';
           // Reset for next use
           progressContainer.style.opacity = '1';
           progressContainer.style.transition = '';
       }, 2000); // 2 seconds fade duration (from 4-5 seconds total)
       
   }, 3000); // Wait 3 seconds before starting fade
   
   if (pollInterval) {
       clearInterval(pollInterval);
   }

}

function updateProgress(current, total, logs = [], currentFile = "", currentProgress = "") {
    // Fix: Use 1-based indexing for display (current + 1)
    const displayCurrent = current > 0 ? current : (total > 0 ? 1 : 0);
    document.getElementById('progressText').textContent = `Processing ${displayCurrent} of ${total} files`;
    
    const currentDownloadDiv = document.getElementById('currentDownload');
    const currentFileNameDiv = document.getElementById('currentFileName');
    const downloadProgressDiv = document.getElementById('downloadProgress');
    
    // Show progress section if we have activity OR if we have logs to display
    if (currentFile || currentProgress || logs.length > 0) {
        currentDownloadDiv.style.display = 'block';
        
        // Always show the current filename prominently
        if (currentFile) {
            currentFileNameDiv.textContent = `Current File: ${currentFile}`;
        } else if (logs.length > 0) {
            // If no current file but we have logs, show completion status
            currentFileNameDiv.textContent = 'Operation completed';
        } else {
            currentFileNameDiv.textContent = 'Processing...';
        }
        
        // Show progress - either our custom message or wget output
        if (currentProgress && currentProgress.trim() !== '') {
            // If it's already a formatted message with filename, show as-is
            if (currentProgress.includes(':') && (currentProgress.includes('exists') || currentProgress.includes('completed') || currentProgress.includes('failed'))) {
                downloadProgressDiv.textContent = currentProgress;
            } else {
                // For raw wget output, just show it (filename is already shown above)
                downloadProgressDiv.textContent = currentProgress;
            }
        } else if (currentFile) {
            downloadProgressDiv.textContent = 'Initializing...';
        } else if (logs.length > 0) {
            downloadProgressDiv.textContent = 'Review results below';
        }
        
        // Auto-scroll to bottom
        downloadProgressDiv.scrollTop = downloadProgressDiv.scrollHeight;
    } else {
        currentDownloadDiv.style.display = 'none';
    }
    
    // Update logs - ALWAYS show logs if we have them
    const logContainer = document.getElementById('logContainer');
    if (logs && logs.length > 0) {
        logContainer.innerHTML = '';
        logs.forEach((log, index) => {
            const div = document.createElement('div');
            
            // Handle different log formats from Python backend
            let message = '';
            let status = 'info';
            
            if (typeof log === 'string') {
                // If log is just a string
                message = log;
                status = 'info';
            } else if (log && typeof log === 'object') {
                // If log is an object with status and message
                message = log.message || log.file || 'Unknown';
                status = log.status || 'info';
                
                // Map different status types to CSS classes
                if (status === 'success' || message.includes('downloaded successfully') || message.includes('completed')) {
                    status = 'success';
                } else if (status === 'error' || message.includes('failed') || message.includes('error')) {
                    status = 'error';
                } else if (status === 'skipped' || message.includes('already exists') || message.includes('already existed')) {
                    status = 'skipped';
                } else if (status === 'deleted' || message.includes('deleted')) {
                    status = 'success';
                } else if (status === 'not_found' || message.includes('not found')) {
                    status = 'skipped';
                }
            }
            
            div.className = `log-entry log-${status}`;
            div.textContent = message;
            logContainer.appendChild(div);
        });
        logContainer.scrollTop = logContainer.scrollHeight;
        
        // Make sure the log container is visible
        logContainer.style.display = 'block';
    }
}

// Add a function to show countdown before hiding progress
function showCompletionMessage(message, delay = 10000) {
    const progressText = document.getElementById('progressText');
    const originalText = progressText.textContent;
    
    let countdown = Math.floor(delay / 1000);
    progressText.textContent = `${message} (Progress will fade out in ${countdown}s)`;
    
    const countdownInterval = setInterval(() => {
        countdown--;
        if (countdown > 5) {
            // First phase: showing countdown to fade start
            progressText.textContent = `${message} (Progress will fade out in ${countdown}s)`;
        } else if (countdown > 0) {
            // Second phase: fading has started
            progressText.textContent = `${message} (Fading out... ${countdown}s remaining)`;
        } else {
            clearInterval(countdownInterval);
            progressText.textContent = originalText;
        }
    }, 1000);
}

function pollProgress() {
    fetch('/progress')
        .then(response => response.json())
        .then(data => {
            updateProgress(
                data.current, 
                data.total, 
                data.progress, 
                data.current_file || "", 
                data.current_progress || ""
            );
            
            if (data.status === 'idle') {
                // Operation completed - show final status
                hideProgress();
                enableOperationButtons();
                
                // Show final status based on the current_progress message
                if (data.current_progress) {
                    let statusMessage = data.current_progress;
                    let statusType = 'success';
                    
                    if (data.current_progress.includes('error')) {
                        statusType = 'error';
                        // Make "errors" clickable if there are errors
                        statusMessage = statusMessage.replace(/(\d+)\s+errors?/g, '<a href="#" onclick="showErrorDetails(); return false;" style="color: #dc3545; text-decoration: underline; font-weight: bold;">$1 errors</a>');
                    } else if (data.current_progress.includes('already existed')) {
                        statusType = 'info';
                    }
                    
                    showStatus(statusMessage, statusType);
                } else {
                    showStatus('Operation completed!', 'success');
                }
                
                // Refresh file explorer to show new files
                updateFileExplorer();
            }
        })
        .catch(error => {
            console.error('Error polling progress:', error);
        });
}

function loadModelConfigs() {
    clearPreviousMessages();
    
    const configStatus = document.getElementById('configStatus');
    configStatus.innerHTML = '<span class="loading-spinner"></span>Loading model configurations...';
    
    fetch('/load_configs')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                configStatus.className = 'config-status config-loaded';
                configStatus.innerHTML = `<i class="fas fa-check-circle" style="color: #28a745;"></i> Successfully loaded ${data.count} model configurations`;
                
                const select = document.getElementById('modelSelect');
                select.innerHTML = '<option value="">Choose a model package...</option>';
                
                // Sort models alphabetically before adding to dropdown
                const sortedModels = data.models.sort((a, b) => a.localeCompare(b));
                sortedModels.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    select.appendChild(option);
                });
                
                // Add event listener to update HF token hint when model selection changes
                select.addEventListener('change', updateHFTokenHint);
                
                configsLoaded = true;
            } else {
                configStatus.className = 'config-status config-error';
                configStatus.innerHTML = `<i class="fas fa-exclamation-circle" style="color: #dc3545;"></i> Failed to load configurations: ${data.message}`;
                configsLoaded = false;
            }
        })
        .catch(error => {
            configStatus.className = 'config-status config-error';
            configStatus.innerHTML = `<i class="fas fa-exclamation-circle" style="color: #dc3545;"></i> Network error loading configurations: ${error.message}`;
            configsLoaded = false;
        });
}

function updateHFTokenHint() {
    const modelSelect = document.getElementById('modelSelect').value;
    const hfTokenInput = document.getElementById('hfToken');
    
    if (!modelSelect) {
        hfTokenInput.placeholder = 'hf_... (required for some models)';
        hfTokenInput.style.borderColor = '';
        hfTokenInput.style.backgroundColor = '';
        // Hide model info when no model is selected
        document.getElementById('modelInfo').style.display = 'none';
        return;
    }
    
    // Automatically show model info for the selected model
    fetch('/model_info', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            model: modelSelect
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update HF token field styling and placeholder
            if (data.requires_hf) {
                hfTokenInput.placeholder = 'HF Token REQUIRED for this model';
                hfTokenInput.style.borderColor = '#ffc107';
                hfTokenInput.style.backgroundColor = '#fff3cd';
            } else {
                hfTokenInput.placeholder = 'hf_... (not required for this model)';
                hfTokenInput.style.borderColor = '';
                hfTokenInput.style.backgroundColor = '';
            }
            
            // Automatically display model info (same as showModelInfo function)
            const infoDiv = document.getElementById('modelInfo');
            const contentDiv = document.getElementById('modelInfoContent');
            
            let html = `<p><strong>Package:</strong> ${data.model}</p>`;
            
            // Highlight HF token requirement
            if (data.requires_hf) {
                html += `<p><strong>Requires HF Token:</strong> <span style="color: #dc3545; font-weight: bold;"><i class="fas fa-exclamation-triangle"></i> YES - Required</span></p>`;
            } else {
                html += `<p><strong>Requires HF Token:</strong> <span style="color: #28a745;">No</span></p>`;
            }
            
            html += `<p><strong>Total Files:</strong> ${data.files.length}</p>`;
            html += '<ul class="file-list">';
            
            data.files.forEach(file => {
                const filename = file.filename || file.url.split('/').pop().split('?')[0];
                html += `<li><strong>${file.directory}/${filename}</strong><br>`;
                html += `<small style="color: #6c757d;">URL: ${file.url}</small></li>`;
            });
            
            html += '</ul>';
            
            // Add warning message if HF token is required
            if (data.requires_hf) {
                html += `<div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px; padding: 10px; margin-top: 15px;">`;
                html += `<strong><i class="fas fa-exclamation-triangle"></i> Important:</strong> This model requires a Hugging Face token. Please ensure you have provided your HF token before downloading.`;
                html += `</div>`;
            }
            
            contentDiv.innerHTML = html;
            infoDiv.style.display = 'block';
        }
    })
    .catch(error => {
        // If there's an error getting model info, still update the HF token hint
        hfTokenInput.placeholder = 'hf_... (could not check requirements)';
        hfTokenInput.style.borderColor = '';
        hfTokenInput.style.backgroundColor = '';
    });
}

function refreshConfigs() {
    loadModelConfigs();
}

function downloadModels() {
    clearPreviousMessages();
    
    if (!configsLoaded) {
        showStatus('Please wait for configurations to load', 'error');
        return;
    }
    
    const modelSelect = document.getElementById('modelSelect').value;
    const basePath = document.getElementById('basePath').value;
    const hfToken = getCurrentHFToken(); // Use the function to get actual token
    
    if (!modelSelect) {
        showStatus('Please select a model package', 'error');
        return;
    }
    
    if (!basePath) {
        showStatus('Please enter a base path', 'error');
        return;
    }

    showStatus('Starting download...', 'info');
    showProgress();
    disableOperationButtons(); // Disable Action buttons
    
    pollInterval = setInterval(pollProgress, 1000);

    fetch('/download', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            model: modelSelect,
            base_path: basePath,
            hf_token: hfToken
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showStatus(data.message, 'info');
        } else {
            showStatus(`Download failed: ${data.message}`, 'error');
            hideProgress();
            enableOperationButtons(); // Enable Action buttons
        }
    })
    .catch(error => {
        showStatus(`Error: ${error.message}`, 'error');
        hideProgress();
        enableOperationButtons(); // Enable Action buttons
    });
}

function deleteModels() {
    clearPreviousMessages(); // Add this line that was missing
    
    if (!configsLoaded) {
        showStatus('Please wait for configurations to load', 'error');
        return;
    }
    
    const modelSelect = document.getElementById('modelSelect').value;
    const basePath = document.getElementById('basePath').value;
    
    if (!modelSelect) {
        showStatus('Please select a model package', 'error');
        return;
    }
    
    if (!basePath) {
        showStatus('Please enter a base path', 'error');
        return;
    }

    if (!confirm(`Are you sure you want to delete all files for "${modelSelect}"? This action cannot be undone.`)) {
        return;
    }

    showStatus('Starting deletion...', 'info');
    showProgress();
    disableOperationButtons(); // Disable Action buttons
    
    pollInterval = setInterval(pollProgress, 1000);

    fetch('/delete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            model: modelSelect,
            base_path: basePath
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showStatus(`Deletion started! ${data.message}`, 'success');
        } else {
            showStatus(`Deletion failed: ${data.message}`, 'error');
            hideProgress();
        }
    })
    .catch(error => {
        showStatus(`Error: ${error.message}`, 'error');
        hideProgress();
    });
}

function showModelInfo() {
    clearPreviousMessages();
    
    if (!configsLoaded) {
        showStatus('Please wait for configurations to load', 'error');
        return;
    }
    
    const modelSelect = document.getElementById('modelSelect').value;
    
    if (!modelSelect) {
        showStatus('Please select a model package', 'error');
        return;
    }

    fetch('/model_info', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            model: modelSelect
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const infoDiv = document.getElementById('modelInfo');
            const contentDiv = document.getElementById('modelInfoContent');
            
            let html = `<p><strong>Package:</strong> ${data.model}</p>`;
            
            // Highlight HF token requirement
            if (data.requires_hf) {
                html += `<p><strong>Requires HF Token:</strong> <span style="color: #dc3545; font-weight: bold;"><i class="fas fa-exclamation-triangle"></i> YES - Required</span></p>`;
            } else {
                html += `<p><strong>Requires HF Token:</strong> <span style="color: #28a745;">No</span></p>`;
            }
            
            html += `<p><strong>Total Files:</strong> ${data.files.length}</p>`;
            html += '<ul class="file-list">';
            
            data.files.forEach(file => {
                const filename = file.filename || file.url.split('/').pop().split('?')[0];
                html += `<li><strong>${file.directory}/${filename}</strong><br>`;
                html += `<small style="color: #6c757d;">URL: ${file.url}</small></li>`;
            });
            
            html += '</ul>';
            
            // Add warning message if HF token is required
            if (data.requires_hf) {
                html += `<div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px; padding: 10px; margin-top: 15px;">`;
                html += `<strong><i class="fas fa-exclamation-triangle"></i> Important:</strong> This model requires a Hugging Face token. Please ensure you have provided your HF token before downloading.`;
                html += `</div>`;
            }
            
            contentDiv.innerHTML = html;
            infoDiv.style.display = 'block';
        } else {
            showStatus(`Error: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        showStatus(`Error: ${error.message}`, 'error');
    });
}

function checkModelStatus() {
    clearPreviousMessages();
    
    if (!configsLoaded) {
        showStatus('Please wait for configurations to load', 'error');
        return;
    }
    
    const modelSelect = document.getElementById('modelSelect').value;
    const basePath = document.getElementById('basePath').value;
    
    if (!modelSelect) {
        showStatus('Please select a model package', 'error');
        return;
    }
    
    if (!basePath) {
        showStatus('Please enter a base path', 'error');
        return;
    }

    showStatus('Checking file status...', 'info');

    fetch('/check_status', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            model: modelSelect,
            base_path: basePath
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const infoDiv = document.getElementById('modelInfo');
            const contentDiv = document.getElementById('modelInfoContent');
            
            let html = `<p><strong>Package:</strong> ${data.model}</p>`;
            html += `<p><strong>Base Path:</strong> ${data.base_path}</p>`;
            html += `<p><strong>Files Found:</strong> ${data.found}/${data.total}</p>`;
            html += '<ul class="file-list">';
            
            data.file_status.forEach(file => {
                const statusIcon = file.exists ? '<i class="fas fa-check-circle" style="color: #28a745;"></i>' : '<i class="fas fa-times-circle" style="color: #dc3545;"></i>';
                const statusText = file.exists ? 'EXISTS' : 'MISSING';
                html += `<li>${statusIcon} <strong>${file.path}</strong> - ${statusText}</li>`;
            });
            
            html += '</ul>';
            contentDiv.innerHTML = html;
            infoDiv.style.display = 'block';
            
            // Show completion status
            if (data.found === data.total) {
                showStatus(`All ${data.total} files are present!`, 'success');
            } else {
                showStatus(`${data.found}/${data.total} files found. ${data.total - data.found} files missing.`, 'info');
            }
        } else {
            showStatus(`Error: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        showStatus(`Error: ${error.message}`, 'error');
    });
}

// Load configurations on page load
document.addEventListener('DOMContentLoaded', function() {
    loadModelConfigs();
    updateFileExplorer();
    loadSavedHFToken();
    setTimeout(function() {
        loadFolderDropdown();
    }, 500);
    checkComfyUIStatus();
    autoDetectComfyUIInstalled();
});

function toggleInstallPanel(forceCollapse) {
    const body = document.getElementById('installBody');
    const chevron = document.getElementById('installChevron');
    const shouldCollapse = forceCollapse !== undefined ? forceCollapse : !body.classList.contains('collapsed');
    body.classList.toggle('collapsed', shouldCollapse);
    chevron.className = shouldCollapse ? 'fas fa-chevron-down' : 'fas fa-chevron-up';
}

function autoDetectComfyUIInstalled() {
    const dir = document.getElementById('comfyuiInstallDir').value.trim() || '/workspace/ComfyUI';
    fetch('/check_comfyui_installed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directory: dir })
    })
    .then(r => r.json())
    .then(data => {
        if (data.installed) {
            toggleInstallPanel(true); // collapse
        }
    })
    .catch(() => {});
}

// HF Token Management
let savedHFToken = '';
let isTokenMasked = false;

function saveHFToken() {
    const tokenInput = document.getElementById('hfToken');
    const saveBtn = document.getElementById('saveTokenBtn');
    const toggleBtn = document.getElementById('toggleTokenBtn');
    const statusSpan = document.getElementById('tokenStatus');
    
    const token = tokenInput.value.trim();
    
    if (!token) {
        statusSpan.textContent = 'Please enter a token to save';
        statusSpan.className = 'token-status error';
        return;
    }
    
    if (!token.startsWith('hf_')) {
        statusSpan.textContent = 'Invalid token format. HF tokens should start with "hf_"';
        statusSpan.className = 'token-status error';
        return;
    }
    
    // Save to memory (not localStorage as per restrictions)
    savedHFToken = token;
    isTokenMasked = true;
    
    // Mask the token display
    const maskedToken = 'hf_' + '●'.repeat(token.length - 3);
    tokenInput.value = maskedToken;
    tokenInput.classList.add('token-masked');
    
    // Update UI
    saveBtn.innerHTML = '<i class="fas fa-check"></i> Saved';
    saveBtn.disabled = true;
    toggleBtn.style.display = 'inline-block';
    statusSpan.textContent = 'Token saved and masked for security';
    statusSpan.className = 'token-status saved';
    
    // Re-enable save button after a delay
    setTimeout(() => {
        saveBtn.innerHTML = '<i class="fas fa-save"></i> Save';
        saveBtn.disabled = false;
    }, 2000);
}

function toggleTokenVisibility() {
    const tokenInput = document.getElementById('hfToken');
    const toggleBtn = document.getElementById('toggleTokenBtn');
    
    if (isTokenMasked && savedHFToken) {
        // Show real token
        tokenInput.value = savedHFToken;
        tokenInput.classList.remove('token-masked');
        toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i> Hide';
        isTokenMasked = false;
    } else {
        // Mask token
        const maskedToken = 'hf_' + '●'.repeat(savedHFToken.length - 3);
        tokenInput.value = maskedToken;
        tokenInput.classList.add('token-masked');
        toggleBtn.innerHTML = '<i class="fas fa-eye"></i> Show';
        isTokenMasked = true;
    }
}

function loadSavedHFToken() {
    // Since we can't use localStorage, tokens are only saved during the session
    // This function is here for consistency and future enhancement
}

function getCurrentHFToken() {
    // Return the actual token for API calls, regardless of masking state
    if (savedHFToken) {
        return savedHFToken;
    }
    
    const tokenInput = document.getElementById('hfToken');
    const inputValue = tokenInput.value.trim();
    
    // If input contains masked token, return saved token
    if (inputValue.includes('●') && savedHFToken) {
        return savedHFToken;
    }
    
    return inputValue;
}

function updateFileExplorer() {
    const basePath = document.getElementById('basePath').value;
    const currentPath = document.getElementById('currentPath');
    const fileTree = document.getElementById('fileTree');
    
    if (currentPath) {
        currentPath.textContent = basePath;
    }
    
    if (fileTree) {
        fileTree.innerHTML = '<div class="loading">Loading directory structure...</div>';
        
        fetch('/browse_directory', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                path: basePath
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayFileTree(data.structure, fileTree);
            } else {
                fileTree.innerHTML = `<div class="error">Error: ${data.message}</div>`;
            }
        })
        .catch(error => {
            fileTree.innerHTML = `<div class="error">Failed to load directory: ${error.message}</div>`;
        });
    }
    
    // Also refresh the folder dropdown for custom downloads
    loadFolderDropdown();
}

function displayFileTree(structure, container) {
    container.innerHTML = '';
    
    if (!structure || structure.length === 0) {
        container.innerHTML = '<div class="loading">Directory is empty</div>';
        return;
    }
    
    structure.forEach(item => {
        const fileItem = createFileItem(item);
        container.appendChild(fileItem);
    });
}

function createFileItem(item, parentPath = '') {
    const div = document.createElement('div');
    div.className = `file-item-wrapper ${item.type}`;
    
    // Create the main item row (folder name or file name with button)
    const itemRow = document.createElement('div');
    itemRow.className = `file-item ${item.type}`;
    
    const contentWrapper = document.createElement('span');
    contentWrapper.className = 'file-item-content';
    
    const nameSpan = document.createElement('span');
    nameSpan.className = 'file-name';
    
    // For files, add size in GB format in parentheses
    if (item.size && item.type === 'file') {
        const sizeGB = (item.size / (1024 * 1024 * 1024)).toFixed(2);
        nameSpan.textContent = `${item.name} (${sizeGB} GB)`;
    } else {
        nameSpan.textContent = item.name;
    }
    
    contentWrapper.appendChild(nameSpan);
    itemRow.appendChild(contentWrapper);
    
    // Add delete button for files
    if (item.type === 'file') {
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'file-delete-btn';
        deleteBtn.innerHTML = '<i class="fas fa-times"></i>';
        deleteBtn.title = 'Delete file';
        deleteBtn.onclick = function(e) {
            e.stopPropagation();
            deleteFileFromExplorer(item.name, parentPath);
        };
        itemRow.appendChild(deleteBtn);
    }
    
    div.appendChild(itemRow);
    
    // For folders, add click handler and children container
    if (item.type === 'folder' && item.children) {
        const currentPath = parentPath ? `${parentPath}/${item.name}` : item.name;
        itemRow.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleFolder(div, item.children, currentPath);
        });
        
        // Create children container (will appear below the folder row)
        const childrenDiv = document.createElement('div');
        childrenDiv.className = 'file-children';
        div.appendChild(childrenDiv);
    }
    
    return div;
}

function toggleFolder(folderElement, children, parentPath) {
    const childrenContainer = folderElement.querySelector('.file-children');
    const folderRow = folderElement.querySelector('.file-item');
    const isExpanded = childrenContainer.classList.contains('expanded');
    
    if (isExpanded) {
        childrenContainer.classList.remove('expanded');
        folderRow.classList.remove('expanded');
    } else {
        // Load children if not already loaded
        if (childrenContainer.children.length === 0) {
            children.forEach(child => {
                const childItem = createFileItem(child, parentPath);
                childrenContainer.appendChild(childItem);
            });
        }
        
        childrenContainer.classList.add('expanded');
        folderRow.classList.add('expanded');
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function deleteFileFromExplorer(filename, relativePath) {
    const basePath = document.getElementById('basePath').value;
    const fullPath = relativePath ? `${basePath}/${relativePath}/${filename}` : `${basePath}/${filename}`;
    
    if (!confirm(`Are you sure you want to delete "${filename}"?\n\nPath: ${fullPath}\n\nThis action cannot be undone.`)) {
        return;
    }
    
    fetch('/delete_file', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            file_path: fullPath
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showStatus(`Successfully deleted: ${filename}`, 'success');
            // Refresh the file explorer to show updated structure
            updateFileExplorer();
        } else {
            showStatus(`Failed to delete ${filename}: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        showStatus(`Error deleting file: ${error.message}`, 'error');
    });
}

function disableOperationButtons() {
    const downloadBtn = document.querySelector('button[onclick="downloadModels()"]');
    const deleteBtn = document.querySelector('button[onclick="deleteModels()"]');
    const infoBtn = document.querySelector('button[onclick="showModelInfo()"]');
    const statusBtn = document.querySelector('button[onclick="checkModelStatus()"]');
    
    if (downloadBtn) {
        downloadBtn.disabled = true;
        downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Operation in Progress...';
    }
    
    if (deleteBtn) {
        deleteBtn.disabled = true;
        deleteBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Operation in Progress...';
    }
    
    if (infoBtn) {
        infoBtn.disabled = true;
        infoBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Operation in Progress...';
    }
    
    if (statusBtn) {
        statusBtn.disabled = true;
        statusBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Operation in Progress...';
    }
}

function enableOperationButtons() {
    const downloadBtn = document.querySelector('button[onclick="downloadModels()"]');
    const deleteBtn = document.querySelector('button[onclick="deleteModels()"]');
    const infoBtn = document.querySelector('button[onclick="showModelInfo()"]');
    const statusBtn = document.querySelector('button[onclick="checkModelStatus()"]');
    
    if (downloadBtn) {
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download Models';
    }
    
    if (deleteBtn) {
        deleteBtn.disabled = false;
        deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i> Delete Models';
    }
    
    if (infoBtn) {
        infoBtn.disabled = false;
        infoBtn.innerHTML = '<i class="fas fa-info-circle"></i> Show Model Info';
    }
    
    if (statusBtn) {
        statusBtn.disabled = false;
        statusBtn.innerHTML = '<i class="fas fa-search"></i> Check Status';
    }
}

function showErrorDetails() {
    const logContainer = document.getElementById('logContainer');
    const progressContainer = document.getElementById('progressContainer');
    
    if (logContainer && progressContainer) {
        // Show the progress container and log container
        progressContainer.style.display = 'block';
        progressContainer.style.opacity = '1';
        progressContainer.style.transition = '';
        
        logContainer.style.display = 'block';
        
        // Scroll to the log container
        logContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        // Add a temporary highlight effect to draw attention
        logContainer.style.border = '2px solid #dc3545';
        logContainer.style.borderRadius = '4px';
        
        // Remove highlight after 3 seconds
        setTimeout(() => {
            logContainer.style.border = '';
            logContainer.style.borderRadius = '';
        }, 3000);
    }
}

// Custom Download Functions
function loadFolderDropdown() {
    const basePath = document.getElementById('basePath');
    const targetFolder = document.getElementById('targetFolder');
    
    if (!targetFolder) {
        console.log('Target folder element not found');
        return;
    }
    
    if (!basePath) {
        console.log('Base path element not found');
        return;
    }
    
    const basePathValue = basePath.value;
    console.log('Loading folders from:', basePathValue);
    
    targetFolder.innerHTML = '<option value="">Loading folders...</option>';
    
    fetch('/get_folders', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            base_path: basePathValue
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Folders response:', data);
        if (data.success) {
            targetFolder.innerHTML = '<option value="">Select a folder...</option>';
            data.folders.forEach(folder => {
                const option = document.createElement('option');
                option.value = folder;
                option.textContent = folder;
                targetFolder.appendChild(option);
            });
            console.log('Loaded', data.folders.length, 'folders');
        } else {
            targetFolder.innerHTML = '<option value="">Error loading folders</option>';
            console.error('Error loading folders:', data.message);
        }
    })
    .catch(error => {
        targetFolder.innerHTML = '<option value="">Error loading folders</option>';
        console.error('Error loading folders:', error);
    });
}

function downloadCustomModel() {
    clearPreviousMessages();
    
    const customUrl = document.getElementById('customUrl').value.trim();
    const targetFolder = document.getElementById('targetFolder').value;
    const customFilename = document.getElementById('customFilename').value.trim();
    const basePath = document.getElementById('basePath').value;
    const hfToken = getCurrentHFToken();
    
    if (!customUrl) {
        showStatus('Please enter a URL', 'error');
        return;
    }
    
    if (!targetFolder) {
        showStatus('Please select a target folder', 'error');
        return;
    }
    
    if (!basePath) {
        showStatus('Please enter a base path', 'error');
        return;
    }
    
    showStatus('Starting custom download...', 'info');
    showProgress();
    
    pollInterval = setInterval(pollProgress, 1000);
    
    fetch('/custom_download', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            url: customUrl,
            folder: targetFolder,
            filename: customFilename,
            base_path: basePath,
            hf_token: hfToken
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showStatus(data.message, 'info');
        } else {
            showStatus(`Download failed: ${data.message}`, 'error');
            hideProgress();
        }
    })
    .catch(error => {
        showStatus(`Error: ${error.message}`, 'error');
        hideProgress();
    });
}

// --- ComfyUI Manager ---
let comfyuiInstallPollInterval = null;
let comfyuiLogPollInterval = null;

function installComfyUI() {
    const dir = document.getElementById('comfyuiInstallDir').value.trim();
    if (!dir) {
        alert('Please enter an install directory');
        return;
    }

    const logDiv = document.getElementById('installProgress');
    logDiv.style.display = 'block';
    logDiv.textContent = 'Starting installation...\n';

    const btn = document.getElementById('installBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Installing...';

    const createVenv = document.getElementById('comfyuiCreateVenv').checked;

    fetch('/install_comfyui', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ install_dir: dir, create_venv: createVenv })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            comfyuiInstallPollInterval = setInterval(pollInstallProgress, 1500);
        } else {
            logDiv.textContent += `\nError: ${data.message}`;
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-download"></i> Install ComfyUI';
        }
    })
    .catch(err => {
        logDiv.textContent += `\nError: ${err.message}`;
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-download"></i> Install ComfyUI';
    });
}

function pollInstallProgress() {
    fetch('/comfyui_install_progress')
        .then(r => r.json())
        .then(data => {
            const logDiv = document.getElementById('installProgress');
            logDiv.textContent = data.log.join('\n');
            logDiv.scrollTop = logDiv.scrollHeight;

            if (data.status === 'done' || data.status === 'error') {
                clearInterval(comfyuiInstallPollInterval);
                comfyuiInstallPollInterval = null;
                const btn = document.getElementById('installBtn');
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-download"></i> Install ComfyUI';
                if (data.status === 'done') {
                    updateFileExplorer();
                    toggleInstallPanel(true); // collapse on success
                }
            }
        })
        .catch(() => {});
}

function runComfyUI() {
    const dir = document.getElementById('comfyuiInstallDir').value.trim() || '/workspace/ComfyUI';
    const port = '8188';

    const logDiv = document.getElementById('comfyuiLog');
    logDiv.style.display = 'block';
    logDiv.textContent = 'Starting ComfyUI...\n';

    const btn = document.getElementById('runBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';

    fetch('/run_comfyui', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comfyui_dir: dir, port: port })
    })
    .then(r => r.json())
    .then(data => {
        btn.innerHTML = '<i class="fas fa-play"></i> Start ComfyUI';
        if (data.success) {
            comfyuiLogPollInterval = setInterval(pollComfyUILog, 2000);
            checkComfyUIStatus();
        } else {
            logDiv.textContent += `\nError: ${data.message}`;
            btn.disabled = false;
        }
    })
    .catch(err => {
        logDiv.textContent += `\nError: ${err.message}`;
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-play"></i> Start ComfyUI';
    });
}

function stopComfyUI() {
    if (!confirm('Are you sure you want to stop ComfyUI?')) return;

    fetch('/stop_comfyui', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            const logDiv = document.getElementById('comfyuiLog');
            logDiv.style.display = 'block';
            logDiv.textContent += `\n${data.message}`;
            logDiv.scrollTop = logDiv.scrollHeight;

            if (comfyuiLogPollInterval) {
                clearInterval(comfyuiLogPollInterval);
                comfyuiLogPollInterval = null;
            }

            document.getElementById('runBtn').disabled = false;
            checkComfyUIStatus();
        })
        .catch(err => alert(`Stop failed: ${err.message}`));
}

function pollComfyUILog() {
    fetch('/comfyui_log')
        .then(r => r.json())
        .then(data => {
            const logDiv = document.getElementById('comfyuiLog');
            if (logDiv && data.log && data.log.length > 0) {
                logDiv.textContent = data.log.join('\n');
                logDiv.scrollTop = logDiv.scrollHeight;
            }
            if (!data.running) {
                if (comfyuiLogPollInterval) {
                    clearInterval(comfyuiLogPollInterval);
                    comfyuiLogPollInterval = null;
                }
                document.getElementById('runBtn').disabled = false;
                checkComfyUIStatus();
            }
        })
        .catch(() => {});
}

function checkComfyUIStatus() {
    fetch('/comfyui_status')
        .then(r => r.json())
        .then(data => {
            const badge = document.getElementById('comfyuiStatusBadge');
            badge.style.display = 'inline-block';

            if (data.running) {
                badge.className = 'comfyui-status-badge status-running';
                badge.innerHTML = `<i class="fas fa-circle"></i> Running &mdash; PID: ${data.pid} | Port: ${data.port}`;
                document.getElementById('runBtn').disabled = true;
            } else {
                badge.className = 'comfyui-status-badge status-stopped';
                badge.innerHTML = '<i class="fas fa-circle"></i> Stopped';
                document.getElementById('runBtn').disabled = false;
            }
        })
        .catch(() => {});
}
