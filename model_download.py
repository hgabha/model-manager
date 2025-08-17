#!/usr/bin/env python3
"""
ComfyUI Model Download Functions
Functions for downloading and deleting model files using wget
"""

import subprocess
from urllib.parse import urlparse
import os
import tempfile
import re

# Global variables for progress tracking
current_operation = {
    "status": "idle", 
    "progress": [], 
    "total": 0, 
    "current": 0,
    "current_file": "",
    "current_progress": ""
}

def get_filename_from_url(url):
    """Extract filename from URL, removing query parameters"""
    path = urlparse(url).path
    filename = os.path.basename(path)
    return filename


def download_files(urls_array, base_path, hf_token=""):
    """Download files from URLs array using wget with log file output"""
    num_urls = len(urls_array)
    print(f"Found {num_urls} URLs to download")

    # Create log file for wget progress
    log_file = os.path.join(tempfile.gettempdir(), 'wget_progress.log')
    
    results = []
    for idx, entry in enumerate(urls_array, 1):
        url = entry["url"]
        directory = os.path.join(base_path, entry["directory"].lstrip('/'))
        provided_filename = entry["filename"]

        os.makedirs(directory, exist_ok=True)

        if provided_filename:
            filename = provided_filename
            print(filename)
        else:
            filename = get_filename_from_url(url)
            print(filename)

        full_path = os.path.join(directory, filename)
        print(full_path)
        # Update progress with current file (idx is 1-based, so idx-1 for 0-based current)
        current_operation['current'] = idx - 1
        current_operation['current_file'] = filename
        current_operation['current_progress'] = f"Checking {filename}..."

        if os.path.exists(full_path):
            message = f"File already exists: {full_path} - Skipping download..."
            print(message)
            results.append({"status": "skipped", "file": filename, "message": message})
            current_operation['progress'] = results
            current_operation['current_progress'] = f"{filename}: File already exists - skipped"
            # Update current to show this file as processed
            current_operation['current'] = idx
            continue

        print(f"Downloading: {filename}")
        
        # Update status to show starting download
        results.append({"status": "downloading", "file": filename, "message": f"Starting download: {filename}"})
        current_operation['progress'] = results
        current_operation['current_progress'] = f"{filename}: Starting download..."



        try:
            cmd = ["wget", "--progress=bar:noscroll"]  # Remove 'force'
            if hf_token:
                cmd.extend(["--header", f"Authorization: Bearer {hf_token}"])
            cmd.extend(["-O", full_path, url])
            
            print(f"Command: {' '.join(cmd)}")
            
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                current_line = ""
                for char in iter(lambda: process.stdout.read(1), ''):
                    if char == '\r':
                        # Carriage return - write current line and reset
                        if current_line.strip():
                            log.write(current_line.strip() + '\n') #filename + '\t' + 
                            log.flush()
                        current_line = ""
                    elif char == '\n':
                        # New line
                        if current_line.strip():
                            log.write(current_line.strip() + '\n')
                            log.flush()
                        current_line = ""
                    else:
                        current_line += char
                
                # Write any remaining content
                if current_line.strip():
                    log.write(current_line.strip() + '\n')
                
                return_code = process.wait()
                
            if return_code == 0:
                message = f"Successfully downloaded: {filename}"
                print(message)
                # Update the last result entry
                results[-1] = {"status": "success", "file": filename, "message": message}
                current_operation['current_progress'] = f"{filename}: Download completed successfully"
                # Update current to show this file as processed
                current_operation['current'] = idx
            else:
                message = f"Download failed for {filename} (exit code: {return_code})"
                print(message)
                results[-1] = {"status": "error", "file": filename, "message": message}
                current_operation['current_progress'] = f"{filename}: Download failed (exit code: {return_code})"
                # Update current to show this file as processed
                current_operation['current'] = idx

        except subprocess.CalledProcessError as e:
            message = f"Error downloading {url}: {e}"
            print(message)
            results[-1] = {"status": "error", "file": filename, "message": message}
            current_operation['current_progress'] = f"{filename}: Download error - {e}"
            # Update current to show this file as processed
            current_operation['current'] = idx
        except Exception as e:
            message = f"Unexpected error with {url}: {e}"
            print(message)
            results[-1] = {"status": "error", "file": filename, "message": message}
            current_operation['current_progress'] = f"{filename}: Unexpected error - {e}"
            # Update current to show this file as processed
            current_operation['current'] = idx
        
        current_operation['progress'] = results
    
    return results


def delete_files(urls_array, base_path):
    """Delete files based on URLs array"""
    num_urls = len(urls_array)
    results = []

    # Clear the wget log file to prevent showing old download messages
    log_file = os.path.join(tempfile.gettempdir(), 'wget_progress.log')
    try:
        with open(log_file, 'w') as log:
            log.write("Starting file deletion...\n")
    except:
        pass

    for idx, entry in enumerate(urls_array, 1):
        url = entry["url"]
        directory = os.path.join(base_path, entry["directory"])
        provided_filename = entry["filename"]

        if provided_filename:
            filename = provided_filename
        else:
            filename = get_filename_from_url(url)

        full_path = os.path.join(directory, filename)

        print(f"Attempting to delete file {idx} of {num_urls}")
        
        # Update current operation progress
        current_operation['current'] = idx - 1
        current_operation['current_file'] = filename
        current_operation['current_progress'] = f"{filename}: Checking for deletion..."

        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                message = f"Found file {full_path}...deleted!"
                print(message)
                results.append({"status": "deleted", "file": filename, "message": message})
                current_operation['current_progress'] = f"{filename}: Deleted successfully"
                # Update current to show this file as processed
                current_operation['current'] = idx
            except Exception as e:
                message = f"Error deleting {full_path}: {e}"
                print(message)
                results.append({"status": "error", "file": filename, "message": message})
                current_operation['current_progress'] = f"{filename}: Error deleting file - {e}"
                # Update current to show this file as processed
                current_operation['current'] = idx
        else:
            message = f"Skipping file {full_path}...not found!"
            print(message)
            results.append({"status": "not_found", "file": filename, "message": message})
            current_operation['current_progress'] = f"{filename}: File not found - nothing to delete"
            # Update current to show this file as processed
            current_operation['current'] = idx
        
        current_operation['progress'] = results
    
    return results