#!/usr/bin/env python3
"""
Model Manager by WeirdWonderfulAI.Art
A standalone web interface that loads model configurations from external file so you have the latest all the time
"""

import requests
import json
import threading
import time
import tempfile
import os
import subprocess
import collections
from flask import Flask, render_template_string, request, jsonify
from pathlib import Path
import sys
import os

# Import functions from model-download.py
try:
    from model_download import download_files, delete_files, get_filename_from_url
except ImportError:
    # If running standalone, try to import from current directory
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from model_download import download_files, delete_files, get_filename_from_url
    except ImportError:
        print("ERROR: Cannot import functions from model-download.py")
        print("Make sure model-download.py is in the same directory or in your Python path")
        sys.exit(1)

app = Flask(__name__)

# Configuration
CONFIG_URL = "https://raw.githubusercontent.com/hgabha/scripts/refs/heads/main/model_configs.json"
DEFAULT_BASE_PATH = "/workspace/ComfyUI/models"

# Global variables
model_configs = {}
current_operation = {
    "status": "idle", 
    "progress": [], 
    "total": 0, 
    "current": 0,
    "current_file": "",
    "current_progress": ""
}

# --- ComfyUI Manager State ---
comfyui_process = None
comfyui_port = 8188
comfyui_install_status = {
    "status": "idle",   # idle | installing | done | error
    "log": [],
    "step": ""
}
comfyui_run_log = collections.deque(maxlen=200)

def load_model_configs():
    """Load model configurations from external JSON file"""
    global model_configs
    try:
        print(f"Loading model configurations from: {CONFIG_URL}")
        response = requests.get(CONFIG_URL, timeout=10)
        response.raise_for_status()
        model_configs = response.json()
        print(f"Successfully loaded {len(model_configs)} model configurations")
        return True
    except requests.RequestException as e:
        print(f"Error loading model configurations: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON configuration: {e}")
        return False

def convert_config_format(model_name):
    """Convert the external JSON format to the format expected by download/delete functions"""
    if model_name not in model_configs:
        return None
    
    config = model_configs[model_name]
    return config["files"]

def get_wget_log_tail():
    """Get download progress - prefer current_progress over log file since wget truncates paths"""
    # Always prioritize current_progress for delete operations and custom status messages
    current_progress = current_operation.get('current_progress', '')
    current_status = current_operation.get('status', 'idle')
    
    # For delete operations, always use current_progress instead of log file
    if current_status == 'deleting' and current_progress:
        return current_progress
    
    # For download operations, check if we have current progress with filename
    if current_progress and ':' in current_progress:
        # Already has filename prefix
        return current_progress
    
    # If no current progress, try log file but add filename prefix (for downloads only)
    if current_status == 'downloading':
        log_file = os.path.join(tempfile.gettempdir(), 'wget_progress.log')
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    # Get last non-empty line that looks like progress
                    for line in reversed(lines[-5:]):
                        line = line.strip()
                        if line and ('%' in line or 'eta' in line or 'MB/s' in line):
                            # Add filename prefix to wget output
                            filename = current_operation.get('current_file', '')
                            if filename:
                                return f"{filename}: {line}"
                            return line
        except:
            pass
    
    # Fallback to current_progress
    return current_progress

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="shortcut icon" href="https://weirdwonderfulai.art/favicon.ico" />
    <title>Model Manager by WeirdWonderfulAi.Art</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="stylesheet" href="/static/styles.css">
    <script src="/static/script.js"></script>
</head>
<body>
    <div class="header" id="mainHeader">
        <h1><i class="fas fa-robot"></i> Model Manager by WeirdWonderfulAi.Art <svg width="48" height="48"><image xlink:href="https://weirdwonderfulai.art/favicon.svg" src="https://weirdwonderfulai.art/favicon-96x96.png" width="48" height="48"/></svg></h1>
        <p>Download and manage AI models for ComfyUI</p>
        <p><small><i class="fas fa-hands-helping"></i> Thank you for purchasing my Runpod Toolkit, your support helps the <a href="https://weirdwonderfulai.art"><i class="fas fa-globe"></i> site</a> and <a href="https://www.youtube.com/@weirdwonderfulaiart"><i class="fas fa-video"></i> YouTube channel</a> going!!</small></p>
    </div>

    <div class="main-container">
        <div class="card main-content" id="mainContent">
            <div id="configStatus" class="config-status">
                <span class="loading-spinner"></span>Loading model configurations...
            </div>
            
            <form id="modelForm">
                <div class="form-group">
                    <label for="modelSelect">
                        Select Model Package:
                        <button type="button" class="refresh-btn" onclick="refreshConfigs()">🔄 Refresh</button>
                    </label>
                    <select id="modelSelect" name="model" required>
                        <option value="">Choose a model package...</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="basePath">Base Path (ComfyUI models directory):</label>
                    <input type="text" id="basePath" name="base_path" value="{{ default_path }}" required onchange="updateFileExplorer()">
                </div>

                <div class="form-group">
                    <label for="hfToken">Hugging Face Token (optional):</label>
                    <input type="text" id="hfToken" name="hf_token" placeholder="hf_... (required for some models)">
                </div>

                <div class="button-group">
                    <button type="button" onclick="downloadModels()" class="btn-primary">
                        <i class="fas fa-download"></i> Download Models
                    </button>
                    <button type="button" onclick="deleteModels()" class="btn-danger">
                        <i class="fas fa-trash-alt"></i> Delete Models
                    </button>
                    <button type="button" onclick="showModelInfo()" class="btn-success">
                        <i class="fas fa-info-circle"></i> Show Model Info
                    </button>
                    <button type="button" onclick="checkModelStatus()" class="btn-info">
                        <i class="fas fa-search"></i> Check Status
                    </button>
                </div>
            </form>
            
            <hr style="margin: 30px 0; border: none; border-top: 2px solid #e0e0e0;">
            
            <!-- Custom Download Section -->
            <div id="customDownload">
                <h3><i class="fas fa-link"></i> Custom Model Download</h3>
                <p>Download a model file from a direct URL to a specific folder</p>
                
                <form id="customDownloadForm">
                    <div class="form-group">
                        <label for="customUrl">Model URL (Hugging Face or direct link):</label>
                        <input type="text" id="customUrl" name="custom_url" placeholder="https://huggingface.co/..." required>
                    </div>
                    
                    <div class="form-group">
                        <label for="targetFolder">Target Folder:</label>
                        <select id="targetFolder" name="target_folder" required>
                            <option value="">Select a folder...</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="customFilename">Custom Filename (optional):</label>
                        <input type="text" id="customFilename" name="custom_filename" placeholder="Leave empty to use original filename">
                    </div>
                    
                    <div class="button-group">
                        <button type="button" onclick="downloadCustomModel()" class="btn-primary">
                            <i class="fas fa-download"></i> Download to Selected Folder
                        </button>
                    </div>
                </form>
            </div>

            <div id="status"></div>
            
            <div class="progress-container" id="progressContainer">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div id="progressText">Preparing...</div>
                
                <div class="current-download" id="currentDownload" style="display: none;">
                    <h5>Current Download:</h5>
                    <div id="currentFileName">-</div>
                    <div class="download-progress" id="downloadProgress">Waiting...</div>
                </div>
                
                <div class="log-container" id="logContainer"></div>
            </div>

            <div id="modelInfo" class="model-info" style="display: none;">
                <h4>Model Information</h4>
                <div id="modelInfoContent"></div>
            </div>

            <hr style="margin: 30px 0; border: none; border-top: 2px solid #e0e0e0;">

            <!-- ComfyUI Manager -->
            <div id="comfyuiManager">
                <h3><i class="fas fa-cubes"></i> ComfyUI Manager</h3>

                <!-- Install (collapsible) -->
                <div class="comfyui-subsection" id="installSection">
                    <div class="comfyui-collapse-header" onclick="toggleInstallPanel()">
                        <span><i class="fas fa-download"></i> Install ComfyUI</span>
                        <i class="fas fa-chevron-up" id="installChevron"></i>
                    </div>
                    <div id="installBody" class="comfyui-collapse-body">
                        <div class="form-group" style="margin-top:14px;">
                            <label for="comfyuiInstallDir">Install Directory:</label>
                            <input type="text" id="comfyuiInstallDir" value="/workspace/ComfyUI" placeholder="/workspace/ComfyUI">
                        </div>
                        <div class="form-group" style="margin-top:10px;">
                            <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:normal;">
                                <input type="checkbox" id="comfyuiCreateVenv" checked style="width:16px;height:16px;cursor:pointer;">
                                Create isolated venv inside ComfyUI folder
                            </label>
                            <small style="color:var(--text-secondary, #888);margin-top:4px;display:block;">
                                Installs ComfyUI's dependencies into <code>ComfyUI/venv</code> instead of the current environment.
                            </small>
                        </div>
                        <div class="form-group" style="margin-top:14px;">
                            <label style="font-weight:600;margin-bottom:8px;display:block;"><i class="fas fa-puzzle-piece"></i> Custom Nodes</label>
                            <div id="customNodesList" style="display:flex;flex-direction:column;gap:6px;">
                                <div class="custom-node-row" style="display:flex;align-items:center;gap:8px;">
                                    <input type="checkbox" class="custom-node-check" checked style="width:15px;height:15px;flex-shrink:0;cursor:pointer;">
                                    <input type="text" class="custom-node-url" value="https://github.com/ltdrdata/ComfyUI-Manager" style="flex:1;font-size:0.82em;">
                                    <button type="button" onclick="removeCustomNode(this)" style="background:none;border:none;color:#e57373;cursor:pointer;padding:2px 6px;font-size:1em;" title="Remove"><i class="fas fa-times"></i></button>
                                </div>
                                <div class="custom-node-row" style="display:flex;align-items:center;gap:8px;">
                                    <input type="checkbox" class="custom-node-check" checked style="width:15px;height:15px;flex-shrink:0;cursor:pointer;">
                                    <input type="text" class="custom-node-url" value="https://github.com/crystian/ComfyUI-Crystools" style="flex:1;font-size:0.82em;">
                                    <button type="button" onclick="removeCustomNode(this)" style="background:none;border:none;color:#e57373;cursor:pointer;padding:2px 6px;font-size:1em;" title="Remove"><i class="fas fa-times"></i></button>
                                </div>
                            </div>
                            <button type="button" onclick="addCustomNode()" style="margin-top:8px;background:none;border:1px dashed var(--border-color,#555);color:var(--text-secondary,#aaa);padding:5px 12px;border-radius:4px;cursor:pointer;font-size:0.82em;width:100%;">
                                <i class="fas fa-plus"></i> Add custom node
                            </button>
                        </div>
                        <div class="button-group" style="grid-template-columns: 1fr;">
                            <button type="button" onclick="installComfyUI()" class="btn-primary" id="installBtn">
                                <i class="fas fa-download"></i> Install ComfyUI
                            </button>
                        </div>
                        <div id="installProgress" class="comfyui-log" style="display:none;"></div>
                    </div>
                </div>

                <!-- Run / Stop / Status -->
                <div class="comfyui-subsection" style="margin-top: 14px;">
                    <h4><i class="fas fa-play-circle"></i> Run ComfyUI</h4>
                    <div class="comfyui-run-buttons">
                        <button type="button" onclick="runComfyUI()" class="comfyui-btn comfyui-btn-start" id="runBtn">
                            <i class="fas fa-play"></i> Start
                        </button>
                        <button type="button" onclick="stopComfyUI()" class="comfyui-btn comfyui-btn-stop" id="stopBtn">
                            <i class="fas fa-stop"></i> Stop
                        </button>
                        <button type="button" onclick="checkComfyUIStatus()" class="comfyui-btn comfyui-btn-status" id="comfyStatusBtn">
                            <i class="fas fa-heartbeat"></i> Status
                        </button>
                    </div>
                    <div id="comfyuiStatusBadge" class="comfyui-status-badge" style="display:none;"></div>
                    <div id="comfyuiLog" class="comfyui-log" style="display:none; margin-top: 15px;"></div>
                </div>
            </div>

        </div>

        <!-- File Explorer Side Panel -->
        <div class="card side-panel" id="sidePanel">
            <div class="panel-header">
                <h3><i class="fas fa-folder-open"></i> File Explorer</h3>
            </div>
            <div class="panel-content">
                <div class="current-path" id="currentPath">/workspace/ComfyUI/models</div>
                <div class="file-tree" id="fileTree">
                    <div class="loading">Loading directory structure...</div>
                </div>
            </div>
        </div>

    </div>
    <footer class="footer">
        <div class="footer-content">
            <div class="footer-left">
                <span class="version-info">Model Manager v1.0 by <a href="https://weirdwonderfulai.art" class="footer-link">WeirdWondefulAi.Art</a></span>
            </div>
            <div class="footer-right">
                <a href="https://discord.gg/22ayqpTnhn" class="footer-link"><i class="fas fa-life-ring"></i> Support</a>
                <a href="https://weirdwonderfulai.art/model-manager-for-comfyui/" class="footer-link"><i class="fas fa-book"></i> Documentation</a>
                <a href="https://discord.gg/22ayqpTnhn" class="footer-link"><i class="fas fa-bug"></i> Report Issue</a>
            </div>
        </div>
    </footer>
</body>
</html>
'''

@app.route('/load_configs')
def load_configs():
    """API endpoint to load model configurations"""
    success = load_model_configs()
    if success:
        return jsonify({
            'success': True,
            'count': len(model_configs),
            'models': list(model_configs.keys())
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to load model configurations from external source'
        })

@app.route('/download', methods=['POST'])
def handle_download():
    try:
        data = request.json
        model_name = data.get('model')
        base_path = data.get('base_path')
        hf_token = data.get('hf_token', '').strip()
        
        files_config = convert_config_format(model_name)
        if not files_config:
            return jsonify({'success': False, 'message': 'Invalid model selection'})
        
        # Check if HF token is required but not provided
        if model_name in model_configs:
            requires_hf = model_configs[model_name].get('hf', False)
            if requires_hf and not hf_token:
                return jsonify({
                    'success': False, 
                    'message': f'Hugging Face token is required for {model_name}. Please provide your HF token and try again.'
                })
        
        # Reset progress tracking
        current_operation['status'] = 'downloading'
        current_operation['progress'] = []
        current_operation['total'] = len(files_config)
        current_operation['current'] = 0
        current_operation['current_file'] = ""
        current_operation['current_progress'] = ""
        
        # Run download in a separate thread
        def run_download():
            try:
                all_results = []
                
                for i, file_info in enumerate(files_config):
                    # Update current file being processed
                    filename = file_info.get("filename") or get_filename_from_url(file_info["url"])
                    current_operation['current_file'] = filename
                    current_operation['current'] = i + 1  # 1-based indexing
                    current_operation['current_progress'] = f"Starting download of {filename}..."
                    
                    # Call the original download function for this single file
                    file_results = download_files([file_info], base_path, hf_token)
                    
                    # Create detailed log entries for each file
                    for result in file_results:
                        log_entry = {
                            'status': result['status'],
                            'message': f"Successfully downloaded: {filename}" if result['status'] == 'success' 
                                     else f"File already exists: {filename}" if result['status'] == 'skipped'
                                     else f"Failed to download: {filename} - {result.get('message', 'Unknown error')}",
                            'file': filename
                        }
                        all_results.append(log_entry)
                        current_operation['progress'] = all_results.copy()  # Update progress with all logs so far
                    
                    # Update current progress message
                    if file_results:
                        status = file_results[0]['status']
                        if status == 'success':
                            current_operation['current_progress'] = f"{filename}: Download completed"
                        elif status == 'skipped':
                            current_operation['current_progress'] = f"{filename}: File already exists"
                        elif status == 'error':
                            current_operation['current_progress'] = f"{filename}: Download failed"
                    
                    time.sleep(0.1)  # Small delay to allow UI updates
                
                current_operation['current'] = len(files_config)
                current_operation['status'] = 'idle'
                current_operation['progress'] = all_results  # Final logs
                
                # Update final status based on results
                success_count = len([r for r in all_results if r['status'] == 'success'])
                skipped_count = len([r for r in all_results if r['status'] == 'skipped'])
                error_count = len([r for r in all_results if r['status'] == 'error'])
                
                if error_count > 0:
                    current_operation['current_progress'] = f"Completed with {error_count} errors, {success_count} downloaded, {skipped_count} already existed"
                elif skipped_count > 0:
                    current_operation['current_progress'] = f"Completed: {success_count} downloaded, {skipped_count} file(s) already existed"
                else:
                    current_operation['current_progress'] = f"{success_count} file(s) downloaded successfully"
                    
            except Exception as e:
                current_operation['status'] = 'error'
                current_operation['progress'] = [{'status': 'error', 'message': f"Download failed: {str(e)}", 'file': 'unknown'}]
                current_operation['current_progress'] = f"Download failed: {str(e)}"
        
        thread = threading.Thread(target=run_download)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': f'Checking and downloading {model_name} files...'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/delete', methods=['POST'])
def handle_delete():
    try:
        data = request.json
        model_name = data.get('model')
        base_path = data.get('base_path')
        
        files_config = convert_config_format(model_name)
        if not files_config:
            return jsonify({'success': False, 'message': 'Invalid model selection'})
        
        # Reset progress tracking
        current_operation['status'] = 'deleting'
        current_operation['progress'] = []
        current_operation['total'] = len(files_config)
        current_operation['current'] = 0
        current_operation['current_file'] = ""
        current_operation['current_progress'] = "Preparing to delete files..."
        
        # Run deletion in a separate thread
        def run_delete():
            try:
                all_results = []
                
                for i, file_info in enumerate(files_config):
                    # Update current file being processed
                    filename = file_info.get("filename") or get_filename_from_url(file_info["url"])
                    current_operation['current_file'] = filename
                    current_operation['current'] = i + 1  # 1-based indexing
                    current_operation['current_progress'] = f"Checking {filename}..."
                    
                    # Call the original delete function for this single file
                    file_results = delete_files([file_info], base_path)
                    
                    # Create detailed log entries for each file
                    for result in file_results:
                        log_entry = {
                            'status': result['status'],
                            'message': f"Successfully deleted: {filename}" if result['status'] == 'deleted' 
                                     else f"File not found: {filename}" if result['status'] == 'not_found'
                                     else f"Failed to delete: {filename} - {result.get('message', 'Unknown error')}",
                            'file': filename
                        }
                        all_results.append(log_entry)
                        current_operation['progress'] = all_results.copy()  # Update progress with all logs so far
                    
                    # Update current progress message
                    if file_results:
                        status = file_results[0]['status']
                        if status == 'deleted':
                            current_operation['current_progress'] = f"{filename}: Deleted successfully"
                        elif status == 'not_found':
                            current_operation['current_progress'] = f"{filename}: File not found"
                        elif status == 'error':
                            current_operation['current_progress'] = f"{filename}: Deletion failed"
                    
                    time.sleep(0.1)  # Small delay to allow UI updates
                
                current_operation['current'] = len(files_config)
                current_operation['status'] = 'idle'
                current_operation['progress'] = all_results  # Final logs
                
                # Update final status based on results
                deleted_count = len([r for r in all_results if r['status'] == 'deleted'])
                not_found_count = len([r for r in all_results if r['status'] == 'not_found'])
                error_count = len([r for r in all_results if r['status'] == 'error'])
                
                if error_count > 0:
                    current_operation['current_progress'] = f"Deletion completed with {error_count} errors, {deleted_count} deleted, {not_found_count} not found"
                elif not_found_count > 0:
                    current_operation['current_progress'] = f"Deletion completed: {deleted_count} deleted, {not_found_count} files were not found"
                else:
                    current_operation['current_progress'] = f"All {deleted_count} files deleted successfully"
                    
            except Exception as e:
                current_operation['status'] = 'error'
                current_operation['progress'] = [{'status': 'error', 'message': f"Deletion failed: {str(e)}", 'file': 'unknown'}]
                current_operation['current_progress'] = f"Deletion failed: {str(e)}"
        
        thread = threading.Thread(target=run_delete)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': f'Checking and deleting {model_name} files...'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/model_info', methods=['POST'])
def handle_model_info():
    try:
        data = request.json
        model_name = data.get('model')
        
        if model_name not in model_configs:
            return jsonify({'success': False, 'message': 'Invalid model selection'})
        
        config = model_configs[model_name]
        return jsonify({
            'success': True,
            'model': model_name,
            'files': config['files'],
            'requires_hf': config.get('hf', False)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/check_status', methods=['POST'])
def handle_check_status():
    try:
        data = request.json
        model_name = data.get('model')
        base_path = data.get('base_path')
        
        files_config = convert_config_format(model_name)
        if not files_config:
            return jsonify({'success': False, 'message': 'Invalid model selection'})
        
        file_status = []
        found_count = 0
        
        for file_info in files_config:
            directory = os.path.join(base_path, file_info["directory"].lstrip('/'))
            filename = file_info["filename"] if file_info["filename"] else get_filename_from_url(file_info["url"])
            full_path = os.path.join(directory, filename)
            
            exists = os.path.exists(full_path)
            if exists:
                found_count += 1
                
            file_status.append({
                'path': full_path,
                'exists': exists,
                'filename': filename,
                'directory': file_info["directory"]
            })
        
        return jsonify({
            'success': True,
            'model': model_name,
            'base_path': base_path,
            'total': len(files_config),
            'found': found_count,
            'file_status': file_status
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/browse_directory', methods=['POST'])
def browse_directory():
    try:
        data = request.json
        path = data.get('path', '')
        
        if not path:
            return jsonify({'success': False, 'message': 'No path provided'})
        
        if not os.path.exists(path):
            return jsonify({'success': False, 'message': 'Path does not exist'})
        
        if not os.path.isdir(path):
            return jsonify({'success': False, 'message': 'Path is not a directory'})
        
        structure = []
        
        try:
            # Get directory contents
            items = os.listdir(path)
            items.sort()  # Sort alphabetically
            
            for item in items:
                item_path = os.path.join(path, item)
                
                if os.path.isdir(item_path):
                    # For directories, get immediate children for lazy loading
                    try:
                        children = []
                        sub_items = os.listdir(item_path)
                        sub_items.sort()
                        
                        for sub_item in sub_items[:50]:  # Limit to 50 items per folder
                            sub_path = os.path.join(item_path, sub_item)
                            if os.path.isdir(sub_path):
                                children.append({
                                    'name': sub_item,
                                    'type': 'folder',
                                    'children': []  # Lazy load deeper levels
                                })
                            else:
                                try:
                                    size = os.path.getsize(sub_path)
                                except:
                                    size = 0
                                children.append({
                                    'name': sub_item,
                                    'type': 'file',
                                    'size': size
                                })
                        
                        structure.append({
                            'name': item,
                            'type': 'folder',
                            'children': children
                        })
                    except PermissionError:
                        structure.append({
                            'name': item,
                            'type': 'folder',
                            'children': [{'name': 'Permission denied', 'type': 'file', 'size': 0}]
                        })
                else:
                    try:
                        size = os.path.getsize(item_path)
                    except:
                        size = 0
                    structure.append({
                        'name': item,
                        'type': 'file',
                        'size': size
                    })
            
            return jsonify({
                'success': True,
                'structure': structure
            })
            
        except PermissionError:
            return jsonify({'success': False, 'message': 'Permission denied'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error reading directory: {str(e)}'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_folders', methods=['POST'])
def get_folders():
    """Get list of subdirectories from base path for folder dropdown"""
    try:
        data = request.json
        base_path = data.get('base_path', DEFAULT_BASE_PATH)
        
        if not os.path.exists(base_path):
            return jsonify({'success': False, 'message': 'Base path does not exist'})
        
        if not os.path.isdir(base_path):
            return jsonify({'success': False, 'message': 'Base path is not a directory'})
        
        folders = []
        
        try:
            # Get all subdirectories
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                if os.path.isdir(item_path):
                    folders.append(item)
            
            folders.sort()  # Sort alphabetically
            
            return jsonify({
                'success': True,
                'folders': folders
            })
            
        except PermissionError:
            return jsonify({'success': False, 'message': 'Permission denied'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error reading directory: {str(e)}'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/custom_download', methods=['POST'])
def handle_custom_download():
    """Handle custom URL download to specified folder"""
    try:
        data = request.json
        url = data.get('url', '').strip()
        folder = data.get('folder', '').strip()
        custom_filename = data.get('filename', '').strip()
        base_path = data.get('base_path', DEFAULT_BASE_PATH)
        hf_token = data.get('hf_token', '').strip()
        
        if not url:
            return jsonify({'success': False, 'message': 'URL is required'})
        
        if not folder:
            return jsonify({'success': False, 'message': 'Target folder is required'})
        
        # Create file info structure for download_files function
        file_info = {
            "url": url,
            "directory": folder,
            "filename": custom_filename if custom_filename else ""
        }
        
        # Reset progress tracking
        current_operation['status'] = 'downloading'
        current_operation['progress'] = []
        current_operation['total'] = 1
        current_operation['current'] = 0
        current_operation['current_file'] = custom_filename if custom_filename else get_filename_from_url(url)
        current_operation['current_progress'] = "Starting custom download..."
        
        # Run download in a separate thread
        def run_custom_download():
            try:
                result = download_files([file_info], base_path, hf_token)
                
                current_operation['current'] = 1
                current_operation['status'] = 'idle'
                current_operation['progress'] = result
                
                if result and result[0]['status'] == 'success':
                    current_operation['current_progress'] = "Download completed successfully"
                elif result and result[0]['status'] == 'skipped':
                    current_operation['current_progress'] = "File already exists"
                else:
                    current_operation['current_progress'] = "Download failed"
                    
            except Exception as e:
                current_operation['status'] = 'error'
                current_operation['progress'] = [{'status': 'error', 'message': f"Download failed: {str(e)}", 'file': 'unknown'}]
                current_operation['current_progress'] = f"Download failed: {str(e)}"
        
        thread = threading.Thread(target=run_custom_download)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Custom download started...'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/delete_file', methods=['POST'])
def delete_file():
    try:
        data = request.json
        file_path = data.get('file_path', '')
        
        if not file_path:
            return jsonify({'success': False, 'message': 'No file path provided'})
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': 'File does not exist'})
        
        if not os.path.isfile(file_path):
            return jsonify({'success': False, 'message': 'Path is not a file'})
        
        try:
            os.remove(file_path)
            return jsonify({
                'success': True,
                'message': f'Successfully deleted: {file_path}'
            })
        except PermissionError:
            return jsonify({'success': False, 'message': 'Permission denied'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error deleting file: {str(e)}'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/progress')
def get_progress():
    # Get real-time wget progress from log file
    wget_progress = get_wget_log_tail()
    
    progress_data = {
        'status': current_operation['status'],
        'current': current_operation['current'], 
        'total': current_operation['total'],
        'progress': current_operation['progress'],
        'current_file': current_operation.get('current_file', ''),
        'current_progress': wget_progress or current_operation.get('current_progress', '')
    }
    
    return jsonify(progress_data)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, default_path=DEFAULT_BASE_PATH)

@app.route('/check_comfyui_installed', methods=['POST'])
def check_comfyui_installed():
    data = request.json
    directory = data.get('directory', '/workspace/ComfyUI').strip()
    installed = os.path.exists(os.path.join(directory, 'main.py'))
    return jsonify({'installed': installed, 'directory': directory})


@app.route('/install_comfyui', methods=['POST'])
def install_comfyui():
    global comfyui_install_status

    data = request.json
    install_dir = data.get('install_dir', '/workspace/ComfyUI').strip()
    create_venv = bool(data.get('create_venv', False))
    custom_nodes = data.get('custom_nodes', [])

    if not install_dir:
        return jsonify({'success': False, 'message': 'Install directory is required'})

    if comfyui_install_status['status'] == 'installing':
        return jsonify({'success': False, 'message': 'Installation already in progress'})

    comfyui_install_status = {'status': 'installing', 'log': ['Starting ComfyUI installation...'], 'step': 'init'}

    def run_install():
        import sys
        log = comfyui_install_status['log']
        try:
            install_path = Path(install_dir)

            # Step 1: Clone or skip if already present
            if (install_path / 'main.py').exists():
                log.append(f'ComfyUI already exists at {install_dir} — skipping clone.')
            else:
                log.append(f'Cloning ComfyUI into {install_dir}...')
                comfyui_install_status['step'] = 'cloning'
                clone_proc = subprocess.Popen(
                    ['git', 'clone', 'https://github.com/comfyanonymous/ComfyUI.git', str(install_path)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
                )
                for line in iter(clone_proc.stdout.readline, ''):
                    stripped = line.rstrip()
                    if stripped:
                        log.append(stripped)
                clone_proc.wait()
                if clone_proc.returncode != 0:
                    log.append(f'ERROR: git clone failed (exit code {clone_proc.returncode})')
                    comfyui_install_status['status'] = 'error'
                    return
                log.append('Clone complete.')

            # Step 2: Create venv inside ComfyUI folder (optional)
            if create_venv:
                venv_path = install_path / 'venv'
                if venv_path.exists():
                    log.append(f'Venv already exists at {venv_path} — reusing.')
                else:
                    log.append(f'Creating venv at {venv_path}...')
                    comfyui_install_status['step'] = 'venv'
                    venv_proc = subprocess.Popen(
                        [sys.executable, '-m', 'venv', str(venv_path)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
                    )
                    for line in iter(venv_proc.stdout.readline, ''):
                        stripped = line.rstrip()
                        if stripped:
                            log.append(stripped)
                    venv_proc.wait()
                    if venv_proc.returncode != 0:
                        log.append(f'ERROR: venv creation failed (exit code {venv_proc.returncode})')
                        comfyui_install_status['status'] = 'error'
                        return
                    log.append('Venv created.')
                # Resolve pip inside the new venv
                pip_exe = str(venv_path / 'Scripts' / 'pip.exe') if os.name == 'nt' else str(venv_path / 'bin' / 'pip')
            else:
                pip_exe = 'pip'

            # Step 3: pip install requirements
            req_file = install_path / 'requirements.txt'
            if req_file.exists():
                dest = f'ComfyUI venv ({install_path / "venv"})' if create_venv else 'current environment'
                log.append(f'Installing Python requirements into {dest}...')
                comfyui_install_status['step'] = 'pip'
                pip_proc = subprocess.Popen(
                    [pip_exe, 'install', '-r', str(req_file)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
                )
                for line in iter(pip_proc.stdout.readline, ''):
                    stripped = line.rstrip()
                    if stripped:
                        log.append(stripped)
                pip_proc.wait()
                if pip_proc.returncode != 0:
                    log.append(f'ERROR: pip install failed (exit code {pip_proc.returncode})')
                    comfyui_install_status['status'] = 'error'
                    return
                log.append('Requirements installed successfully.')
            else:
                log.append('No requirements.txt found — skipping pip install.')

            # Step 4: Clone and install custom nodes
            if custom_nodes:
                custom_nodes_path = install_path / 'custom_nodes'
                custom_nodes_path.mkdir(exist_ok=True)
                for node in custom_nodes:
                    url = node.get('url', '').strip().rstrip('/')
                    if not url:
                        continue
                    node_name = url.split('/')[-1].replace('.git', '')
                    node_path = custom_nodes_path / node_name
                    if node_path.exists():
                        log.append(f'[{node_name}] Already exists — skipping clone.')
                    else:
                        log.append(f'[{node_name}] Cloning from {url}...')
                        comfyui_install_status['step'] = f'custom_node:{node_name}'
                        cn_clone = subprocess.Popen(
                            ['git', 'clone', url, str(node_path)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
                        )
                        for line in iter(cn_clone.stdout.readline, ''):
                            stripped = line.rstrip()
                            if stripped:
                                log.append(stripped)
                        cn_clone.wait()
                        if cn_clone.returncode != 0:
                            log.append(f'[{node_name}] ERROR: clone failed — skipping.')
                            continue
                        log.append(f'[{node_name}] Cloned.')
                    node_req = node_path / 'requirements.txt'
                    if node_req.exists():
                        log.append(f'[{node_name}] Installing requirements...')
                        cn_pip = subprocess.Popen(
                            [pip_exe, 'install', '-r', str(node_req)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
                        )
                        for line in iter(cn_pip.stdout.readline, ''):
                            stripped = line.rstrip()
                            if stripped:
                                log.append(stripped)
                        cn_pip.wait()
                        if cn_pip.returncode != 0:
                            log.append(f'[{node_name}] ERROR: pip install failed.')
                        else:
                            log.append(f'[{node_name}] Requirements installed.')

            log.append('✓ ComfyUI installation complete!')
            comfyui_install_status['status'] = 'done'

        except Exception as e:
            log.append(f'ERROR: {str(e)}')
            comfyui_install_status['status'] = 'error'

    thread = threading.Thread(target=run_install)
    thread.daemon = True
    thread.start()
    return jsonify({'success': True, 'message': 'Installation started'})


@app.route('/comfyui_install_progress')
def comfyui_install_progress():
    return jsonify({
        'status': comfyui_install_status['status'],
        'log': list(comfyui_install_status['log']),
        'step': comfyui_install_status.get('step', '')
    })


@app.route('/run_comfyui', methods=['POST'])
def run_comfyui():
    global comfyui_process, comfyui_port, comfyui_run_log

    if comfyui_process and comfyui_process.poll() is None:
        return jsonify({'success': False, 'message': 'ComfyUI is already running'})

    data = request.json
    comfyui_dir = data.get('comfyui_dir', '/workspace/ComfyUI').strip()
    port_str = data.get('port', '8188').strip() or '8188'

    main_py = os.path.join(comfyui_dir, 'main.py')
    if not os.path.exists(main_py):
        return jsonify({'success': False, 'message': f'main.py not found in {comfyui_dir}. Is ComfyUI installed?'})

    try:
        port_int = int(port_str)
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid port number'})

    comfyui_port = port_int
    comfyui_run_log.clear()
    comfyui_run_log.append(f'Starting ComfyUI from {comfyui_dir} on port {port_int}...')

    # Build launch command — activate venv if one exists inside the ComfyUI folder
    if os.name == 'nt':
        activate_script = os.path.join(comfyui_dir, 'venv', 'Scripts', 'activate.bat')
        if os.path.exists(activate_script):
            comfyui_run_log.append('Activating venv...')
            launch_cmd = f'call "{activate_script}" && python "{main_py}" --listen 0.0.0.0 --port {port_int}'
            popen_args = {'args': launch_cmd, 'shell': True}
        else:
            popen_args = {'args': ['python', main_py, '--listen', '0.0.0.0', '--port', str(port_int)]}
    else:
        activate_script = os.path.join(comfyui_dir, 'venv', 'bin', 'activate')
        if os.path.exists(activate_script):
            comfyui_run_log.append('Activating venv...')
            launch_cmd = f'source "{activate_script}" && python "{main_py}" --listen 0.0.0.0 --port {port_int}'
            popen_args = {'args': launch_cmd, 'shell': True, 'executable': '/bin/bash'}
        else:
            popen_args = {'args': ['python', main_py, '--listen', '0.0.0.0', '--port', str(port_int)]}

    try:
        comfyui_process = subprocess.Popen(
            **popen_args,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, cwd=comfyui_dir
        )

        def capture_output():
            try:
                for line in iter(comfyui_process.stdout.readline, ''):
                    stripped = line.rstrip()
                    if stripped:
                        comfyui_run_log.append(stripped)
            except Exception as e:
                comfyui_run_log.append(f'[Log capture error: {e}]')

        t = threading.Thread(target=capture_output)
        t.daemon = True
        t.start()

        return jsonify({'success': True, 'message': f'ComfyUI started on port {port_int}', 'pid': comfyui_process.pid})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/stop_comfyui', methods=['POST'])
def stop_comfyui():
    global comfyui_process

    if not comfyui_process or comfyui_process.poll() is not None:
        return jsonify({'success': False, 'message': 'ComfyUI is not currently running'})

    try:
        comfyui_process.terminate()
        comfyui_process.wait(timeout=10)
        comfyui_run_log.append('ComfyUI stopped gracefully.')
        return jsonify({'success': True, 'message': 'ComfyUI stopped successfully'})
    except subprocess.TimeoutExpired:
        comfyui_process.kill()
        comfyui_run_log.append('ComfyUI force-killed after timeout.')
        return jsonify({'success': True, 'message': 'ComfyUI force-killed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/comfyui_status')
def get_comfyui_status():
    global comfyui_process, comfyui_port
    running = comfyui_process is not None and comfyui_process.poll() is None
    return jsonify({
        'running': running,
        'pid': comfyui_process.pid if running else None,
        'port': comfyui_port if running else None
    })


@app.route('/comfyui_log')
def get_comfyui_log():
    global comfyui_process, comfyui_run_log
    running = comfyui_process is not None and comfyui_process.poll() is None
    return jsonify({
        'running': running,
        'log': list(comfyui_run_log)
    })


def main():
    print("=" * 60)
    print("🤖 Model Manager by WeirdWonderfulAi.Art v1.0")
    print("=" * 60)
    
    # Load initial configurations
    print("Loading model configurations...")
    if load_model_configs():
        print(f"Successfully loaded {len(model_configs)} model configurations")
    else:
        print("Failed to load model configurations")
        print("The application will still start, but you'll need to refresh configs manually")
    
    print(f"Starting web server on http://localhost:9999")
    print(f"Use the RunPod **Connect** button to launch")
    print(f"Available models: {len(model_configs)} packages")
    print("=" * 60)
    print("\nPress Ctrl+C to stop the server")
    
    try:
        app.run(host='0.0.0.0', port=9999, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
    except Exception as e:
        print(f"\nError starting server: {e}")

if __name__ == '__main__':
    main()
