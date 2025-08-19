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
    status.textContent = message;
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
        console.log('Updating logs with:', logs); // Debug log display
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
            console.log(`Added log ${index}:`, message, 'with status:', status); // Debug each log
        });
        logContainer.scrollTop = logContainer.scrollHeight;
        
        // Make sure the log container is visible
        logContainer.style.display = 'block';
    } else {
        console.log('No logs to display'); // Debug when no logs
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
            console.log('Progress data:', data); // Debug log
            
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
                enableOperationButtons(); // Enable Action buttons
                
                // Show final status based on the current_progress message
                if (data.current_progress) {
                    if (data.current_progress.includes('error')) {
                        showStatus(data.current_progress, 'error');
                    } else if (data.current_progress.includes('already existed')) {
                        showStatus(data.current_progress, 'info');
                    } else {
                        showStatus(data.current_progress, 'success');
                    }
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
                configStatus.innerHTML = `✅ Successfully loaded ${data.count} model configurations`;
                
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
                configStatus.innerHTML = `❌ Failed to load configurations: ${data.message}`;
                configsLoaded = false;
            }
        })
        .catch(error => {
            configStatus.className = 'config-status config-error';
            configStatus.innerHTML = `❌ Network error loading configurations: ${error.message}`;
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
                hfTokenInput.placeholder = '⚠️ HF Token REQUIRED for this model';
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
                html += `<p><strong>Requires HF Token:</strong> <span style="color: #dc3545; font-weight: bold;">⚠️ YES - Required</span></p>`;
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
                html += `<strong>⚠️ Important:</strong> This model requires a Hugging Face token. Please ensure you have provided your HF token before downloading.`;
                html += `</div>`;
            }
            
            contentDiv.innerHTML = html;
            infoDiv.style.display = 'block';
        }
    })
    .catch(error => {
        // If there's an error getting model info, still update the HF token hint
        console.log('Could not load model info:', error);
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
                html += `<p><strong>Requires HF Token:</strong> <span style="color: #dc3545; font-weight: bold;">⚠️ YES - Required</span></p>`;
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
                html += `<strong>⚠️ Important:</strong> This model requires a Hugging Face token. Please ensure you have provided your HF token before downloading.`;
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
                const statusIcon = file.exists ? '✅' : '❌';
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
    updateFileExplorer(); // Load initial file explorer
    loadSavedHFToken(); // Load saved HF token
});

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
    saveBtn.textContent = '✓ Saved';
    saveBtn.disabled = true;
    toggleBtn.style.display = 'inline-block';
    statusSpan.textContent = 'Token saved and masked for security';
    statusSpan.className = 'token-status saved';
    
    // Re-enable save button after a delay
    setTimeout(() => {
        saveBtn.textContent = '💾 Save';
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
        toggleBtn.textContent = '🙈 Hide';
        isTokenMasked = false;
    } else {
        // Mask token
        const maskedToken = 'hf_' + '●'.repeat(savedHFToken.length - 3);
        tokenInput.value = maskedToken;
        tokenInput.classList.add('token-masked');
        toggleBtn.textContent = '👁️ Show';
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

function createFileItem(item) {
    const div = document.createElement('div');
    div.className = `file-item ${item.type}`;
    
    const nameSpan = document.createElement('span');
    nameSpan.textContent = item.name;
    div.appendChild(nameSpan);
    
    if (item.size && item.type === 'file') {
        const sizeSpan = document.createElement('span');
        sizeSpan.className = 'file-size';
        sizeSpan.textContent = formatFileSize(item.size);
        div.appendChild(sizeSpan);
    }
    
    if (item.type === 'folder' && item.children) {
        div.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleFolder(div, item.children);
        });
        
        // Create children container
        const childrenDiv = document.createElement('div');
        childrenDiv.className = 'file-children';
        div.appendChild(childrenDiv);
    }
    
    return div;
}

function toggleFolder(folderElement, children) {
    const childrenContainer = folderElement.querySelector('.file-children');
    const isExpanded = childrenContainer.classList.contains('expanded');
    
    if (isExpanded) {
        childrenContainer.classList.remove('expanded');
        folderElement.classList.remove('expanded');
    } else {
        // Load children if not already loaded
        if (childrenContainer.children.length === 0) {
            children.forEach(child => {
                const childItem = createFileItem(child);
                childrenContainer.appendChild(childItem);
            });
        }
        
        childrenContainer.classList.add('expanded');
        folderElement.classList.add('expanded');
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function disableOperationButtons() {
    const downloadBtn = document.querySelector('button[onclick="downloadModels()"]');
    const deleteBtn = document.querySelector('button[onclick="deleteModels()"]');
    const infoBtn = document.querySelector('button[onclick="showModelInfo()"]');
    const statusBtn = document.querySelector('button[onclick="checkModelStatus()"]');
    
    if (downloadBtn) {
        downloadBtn.disabled = true;
        downloadBtn.textContent = '📥 Operation in Progress...';
    }
    
    if (deleteBtn) {
        deleteBtn.disabled = true;
        deleteBtn.textContent = '🗑️ Operation in Progress...';
    }
    
    if (infoBtn) {
        infoBtn.disabled = true;
        infoBtn.textContent = '📋 Operation in Progress...';
    }
    
    if (statusBtn) {
        statusBtn.disabled = true;
        statusBtn.textContent = '🔍 Operation in Progress...';
    }
}

function enableOperationButtons() {
    const downloadBtn = document.querySelector('button[onclick="downloadModels()"]');
    const deleteBtn = document.querySelector('button[onclick="deleteModels()"]');
    const infoBtn = document.querySelector('button[onclick="showModelInfo()"]');
    const statusBtn = document.querySelector('button[onclick="checkModelStatus()"]');
    
    if (downloadBtn) {
        downloadBtn.disabled = false;
        downloadBtn.textContent = '📥 Download Models';
    }
    
    if (deleteBtn) {
        deleteBtn.disabled = false;
        deleteBtn.textContent = '🗑️ Delete Models';
    }
    
    if (infoBtn) {
        infoBtn.disabled = false;
        infoBtn.textContent = '📋 Show Model Info';
    }
    
    if (statusBtn) {
        statusBtn.disabled = false;
        statusBtn.textContent = '🔍 Check Status';
    }
}

