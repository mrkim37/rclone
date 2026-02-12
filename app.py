import subprocess
import threading
import os
import json
import time
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# Store active jobs in memory
active_jobs = {}
job_history = []
job_id_counter = 0
job_lock = threading.Lock()

HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rclone CopyURL WebUI</title>
  <style>
    body { background:#121212; color:#e0e0e0; font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; padding: 20px; margin: 0; }
    .container { width:100%; max-width:800px; }
    .box { background: #1e1e1e; padding: 25px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); margin-bottom: 20px; }
    h2 { text-align: center; color: #4caf50; margin-bottom: 20px; }
    h3 { color: #4caf50; margin-bottom: 15px; font-size: 18px; border-bottom: 1px solid #444; padding-bottom: 8px; }
    input { background: #2d2d2d; border: 1px solid #444; color: #fff; padding:12px; margin-bottom:15px; width:100%; box-sizing: border-box; border-radius: 4px; font-size: 14px; }
    select { background: #2d2d2d; border: 1px solid #444; color: #fff; padding:12px; margin-bottom:15px; width:100%; box-sizing: border-box; border-radius: 4px; font-size: 14px; }
    button { background: #4caf50; color: white; border: none; padding: 12px; width: 100%; border-radius: 4px; cursor: pointer; font-weight: bold; transition: background 0.3s; font-size: 14px; }
    button:hover { background: #45a049; }
    button:disabled { background: #333; cursor: not-allowed; }
    .remote-info { background: #2d2d2d; padding: 12px; border-radius: 4px; margin-bottom: 15px; border: 1px solid #444; }
    .remote-info .size { color: #4caf50; font-size: 14px; font-weight: bold; }
    .remote-info .loading { color: #888; font-style: italic; }
    .folder-browser { background: #2d2d2d; border: 1px solid #444; border-radius: 4px; margin-bottom: 15px; max-height: 300px; overflow-y: auto; }
    .folder-item { padding: 10px; cursor: pointer; border-bottom: 1px solid #333; display: flex; align-items: center; transition: background 0.2s; }
    .folder-item:hover { background: #3d3d3d; }
    .folder-item.selected { background: #4caf50; color: #000; }
    .folder-icon { margin-right: 8px; font-size: 16px; }
    .breadcrumb { background: #2d2d2d; padding: 8px 12px; border-radius: 4px; margin-bottom: 10px; font-size: 13px; color: #888; }
    .breadcrumb span { cursor: pointer; color: #4caf50; }
    .breadcrumb span:hover { text-decoration: underline; }
    pre { background:#000; padding:15px; height:300px; overflow-y:auto; border-radius: 4px; font-size: 13px; line-height: 1.5; color: #00ff00; border: 1px solid #333; margin-top: 20px; white-space: pre-wrap; word-wrap: break-word; }
    .hidden { display: none; }
    .status-msg { font-size: 12px; color: #888; text-align: center; margin-top: 10px; }
    
    .job-item { background: #2d2d2d; padding: 12px; border-radius: 4px; margin-bottom: 10px; border-left: 4px solid #4caf50; }
    .job-item.running { border-left-color: #2196F3; }
    .job-item.completed { border-left-color: #4caf50; }
    .job-item.failed { border-left-color: #f44336; }
    .job-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .job-title { font-weight: bold; color: #fff; }
    .job-status { font-size: 12px; padding: 4px 8px; border-radius: 3px; font-weight: bold; }
    .job-status.running { background: #2196F3; }
    .job-status.completed { background: #4caf50; }
    .job-status.failed { background: #f44336; }
    .job-details { font-size: 12px; color: #aaa; line-height: 1.4; }
    .job-progress { font-size: 13px; color: #4caf50; margin-top: 5px; font-family: monospace; }
    .job-actions { margin-top: 8px; }
    .job-actions button { padding: 6px 12px; font-size: 12px; margin-right: 5px; width: auto; }
    .view-btn { background: #2196F3; }
    .view-btn:hover { background: #1976D2; }
    .tab-buttons { display: flex; gap: 10px; margin-bottom: 20px; }
    .tab-btn { flex: 1; padding: 12px; background: #2d2d2d; border: 1px solid #444; color: #fff; cursor: pointer; border-radius: 4px; transition: all 0.3s; font-weight: bold; }
    .tab-btn.active { background: #4caf50; color: #000; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    
    .url-display { background: #2d2d2d; padding: 10px; border-radius: 4px; margin-bottom: 15px; font-size: 12px; word-break: break-all; }
    .url-display a { color: #4caf50; text-decoration: none; }
    .url-display a:hover { text-decoration: underline; }
    
    .info-box { background: #1a3a1a; border: 1px solid #4caf50; padding: 15px; border-radius: 4px; margin-bottom: 20px; font-size: 13px; }
    .info-box strong { color: #4caf50; }
  </style>
</head>
<body>
  <div class="container">
    <div class="info-box">
      <strong>📁 WebDAV Access:</strong> Connect to <code>/webdav/</code> for WebDAV access<br>
      <strong>🌐 Current URL:</strong> <span id="currentUrl"></span>
    </div>
    
    <div class="tab-buttons">
      <button class="tab-btn active" onclick="switchTab('upload')">📤 New Upload</button>
      <button class="tab-btn" onclick="switchTab('jobs')">📋 Active Jobs</button>
      <button class="tab-btn" onclick="switchTab('history')">📜 History</button>
    </div>

    <div id="uploadTab" class="tab-content active">
      <div class="box">
        <h2>🚀 Rclone CopyURL Manager</h2>
        
        <input id="url" type="text" placeholder="Direct Download URL (https://example.com/file.zip)">
        
        <select id="remoteSelect" onchange="onRemoteChange()">
          <option value="">Loading remotes...</option>
        </select>
        
        <div id="remoteInfo" class="remote-info hidden">
          <div class="size" id="remoteSize">Size: Loading...</div>
        </div>
        
        <div id="breadcrumb" class="breadcrumb hidden"></div>
        
        <div id="folderBrowser" class="folder-browser hidden"></div>
        
        <input id="selectedPath" type="text" placeholder="Selected folder path (e.g., /Movies/)" readonly>
        
        <button id="startBtn" onclick="start()">Start Upload</button>
        <pre id="log">Ready to start...\nWaiting for URL and destination...</pre>
        <div class="status-msg">Select a remote and folder to begin</div>
      </div>
    </div>

    <div id="jobsTab" class="tab-content">
      <div class="box">
        <h2>📋 Active Jobs</h2>
        <div id="activeJobsList"></div>
      </div>
    </div>

    <div id="historyTab" class="tab-content">
      <div class="box">
        <h2>📜 Job History (Last 20)</h2>
        <div id="jobHistoryList"></div>
      </div>
    </div>
  </div>

  <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
  <script>
    const socket = io();
    const logElem = document.getElementById('log');
    const startBtn = document.getElementById('startBtn');
    const remoteSelect = document.getElementById('remoteSelect');
    const remoteInfo = document.getElementById('remoteInfo');
    const remoteSize = document.getElementById('remoteSize');
    const folderBrowser = document.getElementById('folderBrowser');
    const breadcrumb = document.getElementById('breadcrumb');
    const selectedPath = document.getElementById('selectedPath');
    
    let currentRemote = '';
    let currentPath = '/';
    let folders = [];
    let currentJobId = null;

    // Display current URL
    document.getElementById('currentUrl').innerHTML = '<a href="' + window.location.origin + '/webdav/" target="_blank">' + window.location.origin + '/webdav/</a>';

    function switchTab(tab) {
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
      
      if (tab === 'upload') {
        document.querySelector('.tab-btn:nth-child(1)').classList.add('active');
        document.getElementById('uploadTab').classList.add('active');
      } else if (tab === 'jobs') {
        document.querySelector('.tab-btn:nth-child(2)').classList.add('active');
        document.getElementById('jobsTab').classList.add('active');
        loadActiveJobs();
      } else if (tab === 'history') {
        document.querySelector('.tab-btn:nth-child(3)').classList.add('active');
        document.getElementById('historyTab').classList.add('active');
        loadHistory();
      }
    }

    setInterval(() => {
      if (document.getElementById('jobsTab').classList.contains('active')) {
        loadActiveJobs();
      }
    }, 3000);

    function loadActiveJobs() {
      fetch('/api/jobs/active')
        .then(r => r.json())
        .then(data => {
          const container = document.getElementById('activeJobsList');
          if (data.jobs.length === 0) {
            container.innerHTML = '<div style="color:#888; text-align:center; padding:20px;">No active jobs running</div>';
            return;
          }
          
          container.innerHTML = data.jobs.map(job => `
            <div class="job-item running">
              <div class="job-header">
                <div class="job-title">Job #${job.id}</div>
                <div class="job-status running">RUNNING</div>
              </div>
              <div class="job-details">
                📁 ${job.remote}:${job.path}<br>
                🔗 ${job.url.substring(0, 50)}${job.url.length > 50 ? '...' : ''}
              </div>
              <div class="job-progress">${job.last_progress || 'Initializing...'}</div>
              <div class="job-actions">
                <button class="view-btn" onclick="viewJob(${job.id})">View Live Progress</button>
              </div>
            </div>
          `).join('');
        })
        .catch(err => {
          document.getElementById('activeJobsList').innerHTML = '<div style="color:#f44336; text-align:center; padding:20px;">Error loading jobs</div>';
        });
    }

    function loadHistory() {
      fetch('/api/jobs/history')
        .then(r => r.json())
        .then(data => {
          const container = document.getElementById('jobHistoryList');
          if (data.jobs.length === 0) {
            container.innerHTML = '<div style="color:#888; text-align:center; padding:20px;">No completed jobs yet</div>';
            return;
          }
          
          container.innerHTML = data.jobs.map(job => `
            <div class="job-item ${job.status}">
              <div class="job-header">
                <div class="job-title">Job #${job.id}</div>
                <div class="job-status ${job.status}">${job.status.toUpperCase()}</div>
              </div>
              <div class="job-details">
                📁 ${job.remote}:${job.path}<br>
                🔗 ${job.url.substring(0, 50)}${job.url.length > 50 ? '...' : ''}<br>
                ⏱️ ${job.completed_at}
              </div>
            </div>
          `).join('');
        })
        .catch(err => {
          document.getElementById('jobHistoryList').innerHTML = '<div style="color:#f44336; text-align:center; padding:20px;">Error loading history</div>';
        });
    }

    function viewJob(jobId) {
      currentJobId = jobId;
      switchTab('upload');
      logElem.textContent = 'Connecting to job #' + jobId + '...\\n';
      socket.emit('subscribe_job', jobId);
    }

    // Load remotes on page load
    fetch('/api/remotes')
      .then(r => r.json())
      .then(data => {
        remoteSelect.innerHTML = '<option value="">-- Select a remote --</option>';
        if (data.remotes && data.remotes.length > 0) {
          data.remotes.forEach(remote => {
            const opt = document.createElement('option');
            opt.value = remote;
            opt.textContent = remote;
            remoteSelect.appendChild(opt);
          });
        } else {
          remoteSelect.innerHTML = '<option value="">No remotes found</option>';
        }
      })
      .catch(err => {
        remoteSelect.innerHTML = '<option value="">Error loading remotes</option>';
      });

    socket.on('log', msg => {
      if (msg.includes('%') && msg.match(/\\d+%/)) {
          const lines = logElem.textContent.split('\\n');
          if (lines.length > 0 && lines[lines.length - 1].includes('%')) {
              lines[lines.length - 1] = msg;
              logElem.textContent = lines.join('\\n');
          } else {
              logElem.textContent += msg + "\\n";
          }
      } else {
          logElem.textContent += msg + "\\n";
      }
      logElem.scrollTop = logElem.scrollHeight;
    });

    socket.on('finished', () => {
        startBtn.disabled = false;
        startBtn.textContent = "Start Upload";
        currentJobId = null;
    });

    function onRemoteChange() {
      currentRemote = remoteSelect.value;
      if (!currentRemote) {
        remoteInfo.classList.add('hidden');
        folderBrowser.classList.add('hidden');
        breadcrumb.classList.add('hidden');
        selectedPath.value = '';
        return;
      }
      
      remoteInfo.classList.remove('hidden');
      remoteSize.innerHTML = '<span class="loading">Calculating size...</span>';
      
      fetch('/api/size', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({remote: currentRemote})
      })
      .then(r => r.json())
      .then(data => {
        remoteSize.textContent = 'Total Size: ' + (data.size || 'Unknown');
      })
      .catch(() => {
        remoteSize.textContent = 'Total Size: Unable to calculate';
      });
      
      currentPath = '/';
      loadFolders();
    }

    function loadFolders() {
      folderBrowser.innerHTML = '<div style="padding:15px; color:#888; text-align:center;">Loading folders...</div>';
      folderBrowser.classList.remove('hidden');
      breadcrumb.classList.remove('hidden');
      
      fetch('/api/list', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({remote: currentRemote, path: currentPath})
      })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          folderBrowser.innerHTML = `<div style="padding:15px; color:#f44336; text-align:center;">Error: ${data.error}</div>`;
          return;
        }
        folders = data.folders || [];
        renderFolders();
        updateBreadcrumb();
      })
      .catch(err => {
        folderBrowser.innerHTML = `<div style="padding:15px; color:#f44336; text-align:center;">Failed to load folders: ${err.message}</div>`;
      });
    }

    function renderFolders() {
      folderBrowser.innerHTML = '';
      
      if (currentPath !== '/') {
        const parentDiv = document.createElement('div');
        parentDiv.className = 'folder-item';
        parentDiv.innerHTML = '<span class="folder-icon">⬆️</span> .. (Parent Directory)';
        parentDiv.onclick = () => goToParent();
        folderBrowser.appendChild(parentDiv);
      }
      
      if (folders.length === 0) {
        const emptyDiv = document.createElement('div');
        emptyDiv.style.padding = '15px';
        emptyDiv.style.color = '#888';
        emptyDiv.style.textAlign = 'center';
        emptyDiv.textContent = currentPath === '/' ? 'No folders in root' : 'This folder is empty';
        folderBrowser.appendChild(emptyDiv);
      } else {
        folders.forEach(folder => {
          const div = document.createElement('div');
          div.className = 'folder-item';
          div.innerHTML = `<span class="folder-icon">📁</span> ${folder.name}`;
          div.onclick = () => {
            if (folder.isDir) {
              navigateToFolder(folder.name);
            }
          };
          div.ondblclick = () => selectFolder(folder.name);
          folderBrowser.appendChild(div);
        });
      }
      
      const selectCurrentDiv = document.createElement('div');
      selectCurrentDiv.className = 'folder-item';
      selectCurrentDiv.style.borderTop = '2px solid #4caf50';
      selectCurrentDiv.style.marginTop = '5px';
      selectCurrentDiv.innerHTML = '<span class="folder-icon">✅</span> <strong>Select This Folder</strong>';
      selectCurrentDiv.onclick = () => selectCurrentFolder();
      folderBrowser.appendChild(selectCurrentDiv);
    }

    function navigateToFolder(folderName) {
      currentPath = currentPath.endsWith('/') ? currentPath + folderName : currentPath + '/' + folderName;
      loadFolders();
    }

    function goToParent() {
      if (currentPath === '/') return;
      const parts = currentPath.split('/').filter(p => p);
      parts.pop();
      currentPath = parts.length === 0 ? '/' : '/' + parts.join('/') + '/';
      loadFolders();
    }

    function selectCurrentFolder() {
      selectedPath.value = currentPath;
      // Visual feedback
      document.querySelectorAll('.folder-item').forEach(el => el.classList.remove('selected'));
      event.target.closest('.folder-item').classList.add('selected');
    }

    function selectFolder(folderName) {
      const path = currentPath.endsWith('/') ? currentPath + folderName + '/' : currentPath + '/' + folderName + '/';
      selectedPath.value = path;
    }

    function updateBreadcrumb() {
      const parts = currentPath.split('/').filter(p => p);
      let html = '<span onclick="navigateToPath(\'/\')">🏠 Root</span>';
      let path = '';
      parts.forEach((part, i) => {
        path += '/' + part;
        const fullPath = path;
        html += ` / <span onclick="navigateToPath('${fullPath}')">${part}</span>`;
      });
      breadcrumb.innerHTML = html;
    }

    function navigateToPath(path) {
      currentPath = path === '/' ? '/' : path + '/';
      loadFolders();
    }

    function start(){
      const url = document.getElementById('url').value.trim();
      const path = selectedPath.value || currentPath;
      
      if(!url) {
          alert("Please enter a download URL!");
          return;
      }
      if(!currentRemote) {
          alert("Please select a remote!");
          return;
      }

      logElem.textContent = "Initializing upload...\\n";
      startBtn.disabled = true;
      startBtn.textContent = "Uploading...";

      fetch('/start', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({url, remote: currentRemote, path})
      })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          logElem.textContent = 'Error: ' + data.error + '\\n';
          startBtn.disabled = false;
          startBtn.textContent = "Start Upload";
          return;
        }
        currentJobId = data.job_id;
        logElem.textContent = `Job #${data.job_id} started!\\nURL: ${url}\\nDestination: ${currentRemote}:${path}\\n\\n`;
      })
      .catch(err => {
        logElem.textContent = 'Failed to start job: ' + err.message + '\\n';
        startBtn.disabled = false;
        startBtn.textContent = "Start Upload";
      });
    }
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/upload')
def upload_page():
    """Alias for root path"""
    return render_template_string(HTML)

@app.route('/api/remotes', methods=['GET'])
def get_remotes():
    try:
        result = subprocess.run(
            ["rclone", "listremotes"],
            capture_output=True,
            text=True
        )
        remotes = [line.strip().rstrip(':') for line in result.stdout.strip().split('\n') if line.strip()]
        return jsonify({'remotes': remotes})
    except Exception as e:
        return jsonify({'error': str(e), 'remotes': []})

@app.route('/api/size', methods=['POST'])
def get_remote_size():
    try:
        data = request.json
        remote = data['remote']
        
        result = subprocess.run(
            ["rclone", "size", f"{remote}:", "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return jsonify({'size': 'Unable to access'})
        
        size_data = json.loads(result.stdout)
        bytes_size = size_data.get('bytes', 0)
        size_str = format_bytes(bytes_size)
        
        return jsonify({'size': size_str})
    except Exception as e:
        return jsonify({'size': 'Unknown'})

@app.route('/api/list', methods=['POST'])
def list_folders():
    try:
        data = request.json
        remote = data['remote']
        path = data.get('path', '/')
        
        # Normalize path
        if path and path != '/':
            if not path.startswith('/'):
                path = '/' + path
            if not path.endswith('/'):
                path += '/'
        elif not path:
            path = '/'
        
        full_path = f"{remote}:{path}"
        
        result = subprocess.run(
            ["rclone", "lsjson", full_path, "--dirs-only"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else 'Failed to list directory'
            return jsonify({'folders': [], 'error': error_msg})
        
        if not result.stdout.strip():
            return jsonify({'folders': []})
            
        folders_data = json.loads(result.stdout)
        folders = [{'name': f['Name'], 'isDir': f.get('IsDir', True)} for f in folders_data]
        
        return jsonify({'folders': folders})
    except json.JSONDecodeError:
        return jsonify({'folders': [], 'error': 'Invalid response from rclone'})
    except subprocess.TimeoutExpired:
        return jsonify({'folders': [], 'error': 'Request timeout'})
    except Exception as e:
        return jsonify({'folders': [], 'error': str(e)})

@app.route('/api/jobs/active', methods=['GET'])
def get_active_jobs():
    with job_lock:
        jobs = [
            {
                'id': job_id,
                'url': job['url'],
                'remote': job['remote'],
                'path': job['path'],
                'last_progress': job.get('last_progress', 'Starting...')
            }
            for job_id, job in active_jobs.items()
        ]
    return jsonify({'jobs': jobs})

@app.route('/api/jobs/history', methods=['GET'])
def get_job_history():
    with job_lock:
        recent_jobs = sorted(job_history, key=lambda x: x['id'], reverse=True)[:20]
    return jsonify({'jobs': recent_jobs})

@socketio.on('subscribe_job')
def subscribe_to_job(job_id):
    with job_lock:
        if job_id in active_jobs:
            logs = active_jobs[job_id].get('logs', [])
            for log in logs[-50:]:  # Send last 50 logs
                socketio.emit('log', log)

@app.route('/start', methods=['POST'])
def start_task():
    global job_id_counter
    
    data = request.json
    
    if not data.get('url') or not data.get('remote'):
        return jsonify({'error': 'URL and remote are required'}), 400
    
    with job_lock:
        job_id_counter += 1
        job_id = job_id_counter
        
        active_jobs[job_id] = {
            'id': job_id,
            'url': data['url'],
            'remote': data['remote'],
            'path': data.get('path', '/'),
            'status': 'running',
            'started_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'logs': [],
            'last_progress': 'Initializing...'
        }
    
    threading.Thread(target=run_rclone, args=(data, job_id), daemon=True).start()
    return jsonify({'status': 'started', 'job_id': job_id})

def run_rclone(data, job_id):
    remote = data['remote']
    if ':' not in remote:
        remote += ':'
    
    path = data.get('path', '/')
    url = data["url"]
    
    # Extract filename from URL
    url_path = url.split('?')[0].split('#')[0]
    filename = url_path.rstrip('/').split('/')[-1]
    
    if not filename or '.' not in filename or len(filename) > 255:
        filename = 'downloaded_file_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Ensure path ends with /
    if not path.endswith('/'):
        path += '/'
    
    destination = f"{remote}{path}{filename}"
    
    cmd = [
        "rclone", "copyurl", 
        url, 
        destination,
        "-P", 
        "--transfers", "3", 
        "--low-level-retries", "20", 
        "--retries", "10", 
        "--retries-sleep", "10s",
        "--timeout", "300s",
        "--contimeout", "60s"
    ]

    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1,
            universal_newlines=True
        )

        for line in iter(process.stdout.readline, ""):
            if line:
                stripped_line = line.strip()
                socketio.emit('log', stripped_line)
                
                with job_lock:
                    if job_id in active_jobs:
                        active_jobs[job_id]['logs'].append(stripped_line)
                        # Keep only last 1000 logs to prevent memory issues
                        if len(active_jobs[job_id]['logs']) > 1000:
                            active_jobs[job_id]['logs'] = active_jobs[job_id]['logs'][-500:]
                        if '%' in stripped_line:
                            active_jobs[job_id]['last_progress'] = stripped_line
        
        process.wait()
        final_status = 'completed' if process.returncode == 0 else 'failed'
        
        socketio.emit('log', f'\\n=== Upload {final_status.upper()} ===')
        
        # Move to history
        with job_lock:
            if job_id in active_jobs:
                job_data = active_jobs.pop(job_id)
                job_data['status'] = final_status
                job_data['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                job_data.pop('logs', None)  # Remove logs to save memory
                job_history.append(job_data)
                # Keep only last 100 jobs in history
                if len(job_history) > 100:
                    job_history.pop(0)
                
    except Exception as e:
        socketio.emit('log', f'\\n=== ERROR: {str(e)} ===')
        with job_lock:
            if job_id in active_jobs:
                job_data = active_jobs.pop(job_id)
                job_data['status'] = 'failed'
                job_data['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                job_data.pop('logs', None)
                job_history.append(job_data)
    
    socketio.emit('finished')

def format_bytes(bytes_size):
    if bytes_size == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if abs(bytes_size) < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} EB"

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True, use_reloader=False)
