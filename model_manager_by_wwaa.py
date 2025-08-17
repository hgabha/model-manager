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
    <title>🤖 Model Manager by WeirdWonderfulAi.Art</title>
    <link rel="stylesheet" href="/static/styles.css">
    <script src="/static/script.js"></script>
</head>
<body>
    <div class="header" id="mainHeader">
        <h1>🤖 Model Manager by WeirdWonderfulAi.Art <svg width="48" height="48"><image xlink:href="https://weirdwonderfulai.art/favicon.svg" src="https://weirdwonderfulai.art/favicon-96x96.png" width="48" height="48"/></svg></h1>
        <p>Download and manage AI models for ComfyUI</p>
        <p><small>🙏 Thank you for purchasing my Runpod Toolkit, your support helps the <a href="https://weirdwonderfulai.art">🌏 site</a> and <a href="https://www.youtube.com/@weirdwonderfulaiart">📺 YouTube channel</a> going!!</small></p>
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
                        📥 Download Models
                    </button>
                    <button type="button" onclick="deleteModels()" class="btn-danger">
                        🗑️ Delete Models
                    </button>
                    <button type="button" onclick="showModelInfo()" class="btn-success">
                        📋 Show Model Info
                    </button>
                    <button type="button" onclick="checkModelStatus()" class="btn-info">
                        🔍 Check Status
                    </button>
                </div>
            </form>

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
        </div>
        <!-- File Explorer Side Panel -->
            <div class="card side-panel" id="sidePanel">
                <div class="panel-header">
                    <h3>📁 File Explorer</h3>
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
                <span class="version-info">Model Manager v1.0 - by <a href="https://weirdwonderfulai.art">WeirdWondefulAi.Art</a></span>
            </div>
            <div class="footer-right">
                <a href="https://discord.gg/22ayqpTnhn" class="footer-link">🆘 Support</a>
                <a href="https://weirdwonderfulai.art/model-manager-for-comfyui/" class="footer-link">📚 Documentation</a>
                <a href="https://discord.gg/22ayqpTnhn" class="footer-link">🐛 Report Issue</a>
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

def main():
    print("=" * 60)
    print("🤖 Model Manager by WeirdWonderfulAi.Art v1.0")
    print("=" * 60)
    
    # Load initial configurations
    print("Loading model configurations...")
    if load_model_configs():
        print(f"✅ Successfully loaded {len(model_configs)} model configurations")
    else:
        print("❌ Failed to load model configurations")
        print("The application will still start, but you'll need to refresh configs manually")
    
    print(f"🌐 Starting web server on http://localhost:9999")
    print(f"👆 Use the RunPod **Connect** button to launch")
    print(f"📋 Available models: {len(model_configs)} packages")
    print("=" * 60)
    print("\nPress Ctrl+C to stop the server")
    
    try:
        app.run(host='0.0.0.0', port=9999, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")

if __name__ == '__main__':
    main()
