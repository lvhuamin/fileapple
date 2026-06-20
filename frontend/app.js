/**
 * 学习目录 - 现代网盘风格前端
 */

// ========== 状态管理 ==========

const state = {
    currentView: 'grid',  // grid | list
    currentNavView: 'all',  // all | uploads | downloads | category | ...
    currentSource: 'all',   // all | uploads | downloads
    currentCategory: '',     // category name
    currentPath: '/',
    selectedFiles: new Set(),
    currentDetail: null,
    files: [],
    disks: [],
    uploadQueue: [],
    isUploading: false
};

// ========== 上传队列管理器（支持后台上传）==========

const UploadQueueManager = {
    DB_NAME: 'FileAppleUploadQueue',
    DB_VERSION: 1,
    STORE_NAME: 'pendingUploads',
    
    db: null,
    
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.DB_NAME, this.DB_VERSION);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                resolve();
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(this.STORE_NAME)) {
                    const store = db.createObjectStore(this.STORE_NAME, { keyPath: 'id' });
                    store.createIndex('status', 'status', { unique: false });
                    store.createIndex('createdAt', 'createdAt', { unique: false });
                }
            };
        });
    },
    
    async addUpload(uploadData) {
        if (!this.db) await this.init();
        
        const record = {
            id: 'upload_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8),
            file: uploadData.file,
            fileName: uploadData.file.name,
            fileSize: uploadData.file.size,
            fileType: uploadData.file.type,
            targetDir: uploadData.targetDir || '',
            status: 'pending', // pending, uploading, completed, failed
            progress: 0,
            taskId: null,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            error: null
        };
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.STORE_NAME], 'readwrite');
            const store = transaction.objectStore(this.STORE_NAME);
            const request = store.add(record);
            
            request.onsuccess = () => resolve(record);
            request.onerror = () => reject(request.error);
        });
    },
    
    async updateUpload(id, updates) {
        if (!this.db) await this.init();
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.STORE_NAME], 'readwrite');
            const store = transaction.objectStore(this.STORE_NAME);
            const request = store.get(id);
            
            request.onsuccess = () => {
                const record = request.result;
                if (record) {
                    Object.assign(record, updates, { updatedAt: new Date().toISOString() });
                    const updateRequest = store.put(record);
                    updateRequest.onsuccess = () => resolve(record);
                    updateRequest.onerror = () => reject(updateRequest.error);
                } else {
                    reject(new Error('Record not found'));
                }
            };
            request.onerror = () => reject(request.error);
        });
    },
    
    async getPendingUploads() {
        if (!this.db) await this.init();
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.STORE_NAME], 'readonly');
            const store = transaction.objectStore(this.STORE_NAME);
            const index = store.index('status');
            const request = index.getAll('pending');
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },
    
    async getAllUploads() {
        if (!this.db) await this.init();
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.STORE_NAME], 'readonly');
            const store = transaction.objectStore(this.STORE_NAME);
            const request = store.getAll();
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },
    
    async deleteUpload(id) {
        if (!this.db) await this.init();
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.STORE_NAME], 'readwrite');
            const store = transaction.objectStore(this.STORE_NAME);
            const request = store.delete(id);
            
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    },
    
    async clearCompleted() {
        if (!this.db) await this.init();
        
        const uploads = await this.getAllUploads();
        const completed = uploads.filter(u => u.status === 'completed' || u.status === 'failed');
        
        for (const upload of completed) {
            await this.deleteUpload(upload.id);
        }
    }
};

// ========== 工具函数 ==========

const API_BASE = window.location.origin;

// ========== 前端日志上报 ==========

function clientLog(level, message, data = {}) {
    const logEntry = {
        timestamp: new Date().toISOString(),
        level: level,
        message: message,
        data: data,
        userAgent: navigator.userAgent.substring(0, 100)
    };

    // 发送到后端
    fetch(`${API_BASE}/api/client/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(logEntry)
    }).catch(() => {}); // 静默失败

    // 同时打印到控制台
    const prefix = `[CLIENT:${level}]`;
    if (level === 'error') {
        console.error(prefix, message, data);
    } else if (level === 'warning') {
        console.warn(prefix, message, data);
    } else {
        console.log(prefix, message, data);
    }
}

// 捕获全局错误
window.addEventListener('error', (e) => {
    clientLog('error', 'JavaScript Error', {
        message: e.message,
        filename: e.filename,
        lineno: e.lineno,
        colno: e.colno
    });
});

window.addEventListener('unhandledrejection', (e) => {
    clientLog('error', 'Unhandled Promise Rejection', {
        reason: String(e.reason)
    });
});

function formatSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatTime(isoString) {
    if (!isoString) return '-';
    const d = new Date(isoString);
    return d.toLocaleString('zh-CN');
}

function getFileIcon(name, isDir = false) {
    if (isDir) return { icon: 'fa-folder', class: 'folder' };
    const ext = name.split('.').pop().toLowerCase();
    const icons = {
        'pdf': { icon: 'fa-file-pdf', class: 'pdf' },
        'doc': { icon: 'fa-file-word', class: 'doc' },
        'docx': { icon: 'fa-file-word', class: 'doc' },
        'xls': { icon: 'fa-file-excel', class: 'xls' },
        'xlsx': { icon: 'fa-file-excel', class: 'xls' },
        'zip': { icon: 'fa-file-archive', class: 'zip' },
        'rar': { icon: 'fa-file-archive', class: 'zip' },
        '7z': { icon: 'fa-file-archive', class: 'zip' },
        'mp3': { icon: 'fa-file-audio', class: 'mp3' },
        'mp4': { icon: 'fa-file-video', class: 'mp4' },
        'wav': { icon: 'fa-file-audio', class: 'mp3' },
        'jpg': { icon: 'fa-file-image', class: 'img' },
        'jpeg': { icon: 'fa-file-image', class: 'img' },
        'png': { icon: 'fa-file-image', class: 'img' },
        'gif': { icon: 'fa-file-image', class: 'img' },
        'txt': { icon: 'fa-file-alt', class: 'default' },
        'md': { icon: 'fa-file-alt', class: 'default' },
        'js': { icon: 'fa-file-code', class: 'default' },
        'py': { icon: 'fa-file-code', class: 'default' },
        'html': { icon: 'fa-file-code', class: 'default' },
        'css': { icon: 'fa-file-code', class: 'default' },
    };
    return icons[ext] || { icon: 'fa-file', class: 'default' };
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const icons = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        warning: 'fa-exclamation-circle'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fas ${icons[type]}"></i>
        <span class="toast-message">${message}</span>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ========== API 请求 ==========

async function api(endpoint, options = {}) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
                ...options.headers
            }
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: '请求失败' }));
            throw new Error(err.detail || err.message || '请求失败');
        }

        return res.json();
    } catch (e) {
        console.error('API Error:', e);
        showToast(e.message, 'error');
        throw e;
    }
}

// ========== 文件操作 ==========

async function loadFiles() {
    try {
        showLoading(true);
        let url = '/api/files';
        const params = [];

        if (state.currentSource === 'uploads') {
            params.push('source=uploads');
        } else if (state.currentSource === 'downloads') {
            params.push('source=downloads');
        }

        if (state.currentPath && state.currentPath !== '/') {
            const apiPath = state.currentPath.startsWith('/') ? state.currentPath.slice(1) : state.currentPath;
            params.push('path=' + encodeURIComponent(apiPath));
        }

        if (state.currentNavView === 'uploads') {
            params.push('sort_by=time');
            params.push('order=desc');
        }

        if (params.length > 0) url += '?' + params.join('&');
        const data = await api(url);
        state.files = data.items || [];
        renderFiles();
        updateNavCounts();
    } catch (e) {
        showToast('加载文件失败', 'error');
    } finally {
        showLoading(false);
    }
}

// ========== 恋爱专区 ==========

const LOVE_ZONE_DIR = '恋爱专区';

async function loadLoveZoneFiles() {
    try {
        const data = await api(`/api/files?path=${encodeURIComponent(LOVE_ZONE_DIR)}&source=uploads&sort_by=time&order=desc`);
        state.files = data.items || [];
        renderLoveZone();
    } catch (e) {
        state.files = [];
        renderLoveZone();
    }
    updateNavCounts();
}

function renderLoveZone() {
    const container = document.getElementById('fileContainer');
    if (!container) return;

    container.innerHTML = `
        <div class="love-zone-page">
            <div class="love-zone-header">
                <div class="love-zone-title">
                    <i class="fas fa-heart" style="color: #ff4757;"></i>
                    <h2>恋爱专区</h2>
                </div>
                <p class="love-zone-desc">上传聊天记录、截图、音频、视频或文档，自动转文字后存入恋爱军师知识库</p>
            </div>

            <div class="love-zone-upload">
                <div class="love-upload-dropzone" id="loveUploadDropzone">
                    <i class="fas fa-cloud-upload-alt"></i>
                    <p>拖拽文件到此处，上传到恋爱专区</p>
                    <p class="upload-hint">支持 MP3/MP4/PDF/EPUB/JPG/PNG/TXT/MD，上传后自动处理</p>
                    <button class="btn btn-primary" id="btnLoveUpload">
                        <i class="fas fa-upload"></i> 选择文件
                    </button>
                    <input type="file" id="loveFileInput" multiple hidden>
                </div>
                <div class="love-upload-queue" id="loveUploadQueue"></div>
            </div>

            <div class="love-zone-files">
                <div class="love-zone-section-title">
                    <i class="fas fa-folder-open"></i>
                    <span>已上传文件 (${state.files.length})</span>
                </div>
                <div id="loveFileList">
                    ${state.files.length === 0 ? `
                        <div class="empty-state" style="padding: 40px;">
                            <i class="fas fa-heart" style="font-size: 48px; color: var(--gray-300);"></i>
                            <h3>恋爱专区为空</h3>
                            <p>上传你的资料，系统会自动处理并存入知识库</p>
                        </div>
                    ` : state.files.map(f => `
                        <div class="love-file-item">
                            <div class="love-file-icon ${getFileIcon(f.name).class}">
                                <i class="fas ${getFileIcon(f.name).icon}"></i>
                            </div>
                            <div class="love-file-info">
                                <div class="love-file-name">${f.name}</div>
                                <div class="love-file-meta">${formatSize(f.size)} · ${formatTime(f.modified)}</div>
                            </div>
                            <div class="love-file-status">
                                <span class="love-status-dot"></span>
                                ${f.name.endsWith('.md') || f.name.endsWith('.txt') ? '已处理' : '待处理'}
                            </div>
                            <button class="icon-btn" onclick="downloadLoveFile('${f.path.replace(/'/g, "\\'")}')" title="下载">
                                <i class="fas fa-download"></i>
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;

    initLoveUpload();
}

function downloadLoveFile(path) {
    window.open(API_BASE + '/api/files/download/' + encodeURIComponent(path) + '?source=uploads', '_blank');
}

function initLoveUpload() {
    const dropzone = document.getElementById('loveUploadDropzone');
    const fileInput = document.getElementById('loveFileInput');
    const selectBtn = document.getElementById('btnLoveUpload');
    if (!dropzone) return;

    selectBtn?.addEventListener('click', (e) => { e.stopPropagation(); fileInput?.click(); });
    dropzone.addEventListener('click', () => fileInput?.click());
    fileInput?.addEventListener('change', (e) => {
        if (e.target.files.length) handleLoveFiles(e.target.files);
    });
    dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleLoveFiles(e.dataTransfer.files);
    });
}

function handleLoveFiles(files) {
    const queue = document.getElementById('loveUploadQueue');
    if (!queue) return;
    queue.innerHTML = '';

    Array.from(files).forEach(file => {
        const item = document.createElement('div');
        item.className = 'upload-item';
        item.innerHTML = `
            <div class="upload-item-info">
                <div class="upload-item-name">${file.name}</div>
                <div class="upload-item-size">${formatSize(file.size)}</div>
                <div class="upload-item-progress">
                    <div class="upload-item-fill" style="width: 0%"></div>
                </div>
            </div>
            <button class="icon-btn" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        queue.appendChild(item);
        uploadLoveFile(file, item.querySelector('.upload-item-fill'));
    });
}

async function uploadLoveFile(file, progressBar) {
    const CHUNK_SIZE = 5 * 1024 * 1024;
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

    try {
        const params = new URLSearchParams({ file_name: file.name, file_size: file.size, target_dir: LOVE_ZONE_DIR });
        const initRes = await fetch(`${API_BASE}/api/upload/init`, {
            method: 'POST',
            body: params
        });
        const initData = await initRes.json();
        if (initData.error) { showToast('上传失败: ' + initData.error, 'error'); return; }

        const taskId = initData.task_id;
        const uploadedChunks = new Set(initData.uploaded_chunks || []);

        for (let i = 0; i < totalChunks; i++) {
            if (uploadedChunks.has(i)) continue;
            const start = i * CHUNK_SIZE;
            const end = Math.min(start + CHUNK_SIZE, file.size);
            const chunk = file.slice(start, end);
            const formData = new FormData();
            formData.append('task_id', taskId);
            formData.append('chunk_index', i);
            formData.append('chunk', chunk);
            await fetch(`${API_BASE}/api/upload/chunk`, { method: 'POST', body: formData });
            const percent = ((i + 1) / totalChunks * 100).toFixed(0);
            if (progressBar) progressBar.style.width = percent + '%';
        }

        await fetch(`${API_BASE}/api/upload/merge`, {
            method: 'POST',
            body: new URLSearchParams({ task_id: taskId })
        });
        if (progressBar) progressBar.style.width = '100%';
        showToast(`${file.name} 上传成功 ✅`);
        setTimeout(() => loadLoveZoneFiles(), 500);
    } catch (e) {
        showToast('上传失败: ' + e.message, 'error');
    }
}

function renderFiles() {
    const container = document.getElementById('fileContainer');
    if (!container) return;

    // 保存emptyState元素引用（因为innerHTML会删除它）
    let emptyState = document.getElementById('emptyState');
    if (!emptyState) {
        // 如果不存在则创建
        emptyState = document.createElement('div');
        emptyState.id = 'emptyState';
        emptyState.className = 'empty-state';
        emptyState.innerHTML = '<i class="fas fa-folder-open"></i><h3>文件夹为空</h3><p>拖拽文件到此处，或点击上方「上传」按钮</p>';
        container.appendChild(emptyState);
    }

    if (state.files.length === 0) {
        container.innerHTML = '';
        emptyState.style.display = 'flex';
        container.appendChild(emptyState);
        return;
    }

    emptyState.style.display = 'none';

    if (state.currentView === 'grid') {
        container.innerHTML = `
            <div class="file-grid">
                ${state.files.map(f => renderFileGridItem(f)).join('')}
            </div>
        `;
    } else {
        container.innerHTML = `
            <div class="file-list-view">
                ${state.files.map(f => renderFileListItem(f)).join('')}
            </div>
        `;
    }

    // 绑定事件
    bindFileEvents();
}

function renderFileGridItem(file) {
    const icon = getFileIcon(file.name, file.is_dir);
    const isSelected = state.selectedFiles.has(file.path);

    const _sp = file.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    return `
        <div class="file-item ${isSelected ? 'selected' : ''}"
             data-path="${file.path}"
             data-name="${file.name}"
             data-dir="${file.is_dir}"
             onclick="handleFileClick(event, '${_sp}', ${file.is_dir})">
            <label class="file-checkbox" onclick="event.stopPropagation()">
                <input type="checkbox" ${isSelected ? 'checked' : ''} onchange="toggleSelect('${_sp}')">
                <span class="checkmark"></span>
            </label>
            <div class="file-icon ${icon.class}">
                <i class="fas ${icon.icon}"></i>
            </div>
            <div class="file-info">
                <div class="file-name" title="${file.name}">${file.name}</div>
                <div class="file-meta">
                    ${file.is_dir ? '文件夹' : formatSize(file.size)} · ${formatTime(file.modified)}
                </div>
            </div>
        </div>
    `;
}

function renderFileListItem(file) {
    const icon = getFileIcon(file.name, file.is_dir);
    const isSelected = state.selectedFiles.has(file.path);

    const _sp2 = file.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    return `
        <div class="file-list-item ${isSelected ? 'selected' : ''}"
             data-path="${file.path}"
             data-dir="${file.is_dir}"
             onclick="handleFileClick(event, '${_sp2}', ${file.is_dir})">
            <div class="file-list-name">
                <label class="checkbox" onclick="event.stopPropagation()">
                    <input type="checkbox" ${isSelected ? 'checked' : ''} onchange="toggleSelect('${_sp2}')">
                    <span class="checkmark"></span>
                </label>
                <i class="fas ${icon.icon}" style="color: var(--gray-400);"></i>
                <span>${file.name}</span>
            </div>
            <div class="file-list-size">${file.is_dir ? '-' : formatSize(file.size)}</div>
            <div class="file-list-date">${formatTime(file.modified)}</div>
            <div class="file-list-actions">
                <button class="icon-btn" onclick="event.stopPropagation(); downloadFile('${_sp2}')" title="下载">
                    <i class="fas fa-download"></i>
                </button>
                <button class="icon-btn" onclick="event.stopPropagation(); showShareModal('${_sp2}')" title="分享">
                    <i class="fas fa-share-alt"></i>
                </button>
            </div>
        </div>
    `;
}

function bindFileEvents() {
    document.querySelectorAll('.file-item, .file-list-item').forEach(item => {
        item.addEventListener('dblclick', () => {
            const path = item.dataset.path;
            const isDir = item.dataset.dir === 'true';
            if (isDir) {
                navigateTo(path);
            } else {
                showDetail(path);
            }
        });
    });
}

function handleFileClick(event, path, isDir) {
    const ctrlPressed = event?.ctrlKey || event?.metaKey || false;
    if (ctrlPressed) {
        toggleSelect(path);
    } else {
        state.selectedFiles.clear();
        state.selectedFiles.add(path);
        updateToolbar();
        renderFiles();
        if (!isDir) {
            showDetail(path);
        }
    }
}

function toggleSelect(path) {
    if (state.selectedFiles.has(path)) {
        state.selectedFiles.delete(path);
    } else {
        state.selectedFiles.add(path);
    }
    updateToolbar();
    renderFiles();
}

function updateToolbar() {
    const count = state.selectedFiles.size;
    document.getElementById('selectedCount').textContent = `${count} 项已选中`;

    const btns = ['btnDownload', 'btnShare', 'btnMove', 'btnDelete', 'btnKnowledge', 'btnTag'];
    btns.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.disabled = count === 0;
    });

    // 全选复选框
    const selectAll = document.getElementById('selectAll');
    if (selectAll) {
        selectAll.checked = count === state.files.length && count > 0;
    }
}

// ========== 导航操作 ==========

async function navigateTo(path) {
    state.currentPath = path;
    // 回到根时重置侧边栏高亮到当前视图
    if (path === '/') {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        const selector = state.currentNavView === 'category' ? '[data-view="downloads"]' : `[data-view="${state.currentNavView}"]`;
        const defaultNav = document.querySelector(selector);
        if (defaultNav) defaultNav.classList.add('active');
    }
    const pathDisplay = path === '/' ? '全部文件' : path.split('/').pop();
    document.getElementById('currentPath').innerHTML = `
        <i class="fas fa-folder"></i>
        ${pathDisplay}
    `;
    // 控制返回按钮显隐
    const backBtn = document.getElementById('btnBack');
    if (backBtn) backBtn.style.display = (path === '/') ? 'none' : 'flex';
    state.selectedFiles.clear();
    await loadFiles();
    updateBreadcrumb(path);
}

function updateBreadcrumb(path) {
    const breadcrumb = document.getElementById('breadcrumb');
    if (path === '/') {
        breadcrumb.innerHTML = '<span class="breadcrumb-item active">全部文件</span>';
        return;
    }

    const parts = path.split('/').filter(Boolean);
    let html = '<span class="breadcrumb-item" onclick="navigateTo(\'/\')">全部文件</span>';
    let currentPath = '';

    parts.forEach((part, i) => {
        currentPath += '/' + part;
        const safePath = currentPath.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        html += `<span class="breadcrumb-item ${i === parts.length - 1 ? 'active' : ''}"
                       onclick="navigateTo('${safePath}')">${part}</span>`;
    });

    breadcrumb.innerHTML = html;
}

// ========== 文件详情 ==========

async function showDetail(path) {
    const panel = document.getElementById('detailPanel');
    const content = document.getElementById('detailContent');

    const file = state.files.find(f => f.path === path);
    if (!file) return;

    state.currentDetail = file;
    panel.classList.add('active');

    const icon = getFileIcon(file.name, file.is_dir);
    content.innerHTML = `
        <div class="detail-preview">
            <i class="fas ${icon.icon}" style="color: var(--gray-400);"></i>
        </div>
        <div class="detail-info">
            <div class="detail-row">
                <span class="detail-label">文件名</span>
                <span class="detail-value">${file.name}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">大小</span>
                <span class="detail-value">${file.is_dir ? '-' : formatSize(file.size)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">修改时间</span>
                <span class="detail-value">${formatTime(file.modified)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">类型</span>
                <span class="detail-value">${file.is_dir ? '文件夹' : file.name.split('.').pop().toUpperCase()}</span>
            </div>
        </div>
        <div class="detail-actions">
            <button class="btn btn-primary btn-block" onclick="downloadFile('${path.replace(/\\/g,'\\\\').replace(/'/g,"\\'")}')">
                <i class="fas fa-download"></i> 下载
            </button>
            <button class="btn btn-secondary btn-block" onclick="showShareModal('${path.replace(/\\/g,'\\\\').replace(/'/g,"\\'")}')">
                <i class="fas fa-share-alt"></i> 分享
            </button>
        </div>
    `;
}

function closeDetail() {
    document.getElementById('detailPanel').classList.remove('active');
    state.currentDetail = null;
}

// ========== 文件操作 ==========

async function downloadFile(path) {
    const src = state.currentSource || 'uploads';
    window.open(`${API_BASE}/api/files/download/${encodeURIComponent(path)}?source=${src}`, '_blank');
}

async function deleteSelectedFiles() {
    if (state.selectedFiles.size === 0) return;

    if (!confirm(`确定删除 ${state.selectedFiles.size} 个文件？`)) return;

    let success = 0, failed = 0;
    for (const path of state.selectedFiles) {
        try {
            await api(`/api/files?path=${encodeURIComponent(path)}`, { method: 'DELETE' });
            success++;
        } catch (e) {
            failed++;
        }
    }

    state.selectedFiles.clear();
    showToast(`删除完成: ${success} 成功, ${failed} 失败`);
    await loadFiles();
}

async function showShareModal(path) {
    document.getElementById('shareModal').classList.add('active');
    document.getElementById('shareUrl').value = `${API_BASE}/s/${btoa(path).replace(/=/g, '')}`;
}

async function createShareLink() {
    if (state.selectedFiles.size === 0) {
        showToast('请先选择文件', 'warning');
        return;
    }

    const path = Array.from(state.selectedFiles)[0];
    const expiry = document.getElementById('shareExpiry').value;
    const password = document.getElementById('sharePassword').value;

    try {
        const data = await api('/api/share', {
            method: 'POST',
            body: JSON.stringify({
                file_path: path,
                expiry_days: parseInt(expiry),
                password: password || undefined
            })
        });

        const shareUrl = `${API_BASE}/s/${data.share_id}`;
        document.getElementById('shareUrl').value = shareUrl;
        showToast('分享链接已创建');
    } catch (e) {
        // 使用备用方案
        document.getElementById('shareUrl').value = `${API_BASE}/s/${btoa(path).replace(/=/g, '')}`;
    }
}

async function copyShareLink() {
    const input = document.getElementById('shareUrl');
    await navigator.clipboard.writeText(input.value);
    showToast('链接已复制');
}

// ========== 模态框管理 ==========

function openModal(id) {
    // 关闭详情面板
    const detailPanel = document.getElementById('detailPanel');
    if (detailPanel) detailPanel.classList.remove('active');
    document.getElementById(id).classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

// 上传模态框
function openUploadModal() {
    openModal('uploadModal');
    document.getElementById('uploadQueue').innerHTML = '';
}

function closeUploadModal() {
    closeModal('uploadModal');
}

// 云盘管理模态框
async function openCloudModal() {
    openModal('cloudModal');
    await loadDisks();
    showCloudTab('disks');
}

function closeCloudModal() {
    closeModal('cloudModal');
}

function showCloudTab(tab) {
    document.querySelectorAll('.cloud-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.cloud-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
    document.getElementById(`cloud-${tab}`).classList.add('active');
}

// 知识导入模态框
async function openKnowledgeModal() {
    openModal('knowledgeModal');
    await loadKnowledgeFiles();
}

function closeKnowledgeModal() {
    closeModal('knowledgeModal');
}

// ========== 云盘管理 ==========

async function loadDisks() {
    try {
        const data = await api('/api/disks');
        state.disks = data.disks || [];
        renderDisks();
    } catch (e) {
        console.error('加载云盘失败:', e);
    }
}

function renderDisks() {
    const list = document.getElementById('diskList');
    if (state.disks.length === 0) {
        list.innerHTML = `
            <div class="empty-state" style="padding: 40px;">
                <i class="fas fa-cloud" style="font-size: 48px;"></i>
                <h3>暂无云盘</h3>
                <p>点击「添加网盘」添加您的第一个云盘</p>
            </div>
        `;
        return;
    }

    const icons = {
        alist: 'fa-server',
        aliyun: 'fa-cloud',
        baidu: 'fa-cloud-sun',
        quark: 'fa-atom',
        tianyi: 'fa-mobile-alt',
        '115': 'fa-box'
    };

    list.innerHTML = state.disks.map(disk => `
        <div class="disk-card">
            <div class="disk-icon ${disk.type}">
                <i class="fas ${icons[disk.type] || 'fa-hdd'}"></i>
            </div>
            <div class="disk-info">
                <div class="disk-name">${disk.name}</div>
                <div class="disk-meta">
                    ${disk.mount_path} · ${disk.status === 'idle' ? '空闲' : disk.status}
                </div>
            </div>
            <div class="disk-actions">
                <button class="icon-btn" onclick="syncDisk('${disk.id}')" title="同步">
                    <i class="fas fa-sync"></i>
                </button>
                <button class="icon-btn" onclick="removeDisk('${disk.id}')" title="删除">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

async function addDisk() {
    const name = document.getElementById('diskName').value;
    const diskType = document.getElementById('diskType').value;
    const host = document.getElementById('alistHost').value;
    const username = document.getElementById('diskUsername').value;
    const password = document.getElementById('diskPassword').value;
    const mountPath = document.getElementById('diskMountPath').value;

    if (!name) {
        showToast('请输入网盘名称', 'warning');
        return;
    }

    try {
        const formData = new FormData();
        formData.append('name', name);
        formData.append('disk_type', diskType);
        formData.append('host', host);
        formData.append('username', username);
        formData.append('password', password);
        formData.append('mount_path', mountPath);

        await fetch(`${API_BASE}/api/disks`, {
            method: 'POST',
            body: formData
        });

        showToast('云盘添加成功');
        await loadDisks();
        showCloudTab('disks');

        // 清空表单
        document.querySelectorAll('#cloud-add input, #cloud-add select').forEach(i => i.value = '');
    } catch (e) {
        showToast('添加失败: ' + e.message, 'error');
    }
}

async function syncDisk(diskId) {
    showToast('开始同步...', 'warning');
    try {
        const formData = new FormData();
        formData.append('remote_path', '/');
        formData.append('local_category', '其他');

        await fetch(`${API_BASE}/api/disks/${diskId}/sync`, {
            method: 'POST',
            body: formData
        });

        showToast('同步完成');
        await loadDisks();
        await loadFiles();
    } catch (e) {
        showToast('同步失败', 'error');
    }
}

async function removeDisk(diskId) {
    if (!confirm('确定删除此云盘？')) return;

    try {
        await api(`/api/disks/${diskId}`, { method: 'DELETE' });
        showToast('云盘已删除');
        await loadDisks();
    } catch (e) {
        showToast('删除失败', 'error');
    }
}

// ========== 知识导入 ==========

async function loadKnowledgeFiles() {
    try {
        const data = await api('/api/knowledge/scan');
        const pending = data.files || [];

        document.getElementById('statPending').textContent = pending.length;

        const container = document.getElementById('knowledgeFiles');
        if (pending.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>暂无待导入文件</p></div>';
            return;
        }

        container.innerHTML = `
            <div class="knowledge-header">
                <label class="checkbox">
                    <input type="checkbox" id="selectAllKnowledge" onchange="toggleAllKnowledge(this)">
                    <span class="checkmark"></span>
                    <span>全选</span>
                </label>
                <select id="knowledgeCategory" style="padding: 4px 8px; border-radius: 4px;">
                    <option value="技术运维">技术运维</option>
                    <option value="心理学">心理学</option>
                    <option value="恋爱心理">恋爱心理</option>
                    <option value="文档">文档</option>
                    <option value="其他">其他</option>
                </select>
            </div>
            ${pending.slice(0, 50).map(f => `
                <div class="file-item knowledge-file" style="margin-bottom: 8px;">
                    <label class="checkbox">
                        <input type="checkbox" data-path="${f.path}" onchange="updateKnowledgeCount()">
                        <span class="checkmark"></span>
                    </label>
                    <div class="file-icon ${getFileIcon(f.name).class}">
                        <i class="fas ${getFileIcon(f.name).icon}"></i>
                    </div>
                    <div class="file-info">
                        <div class="file-name">${f.name}</div>
                        <div class="file-meta">${formatSize(f.size)} · ${f.category || '未分类'}</div>
                    </div>
                </div>
            `).join('')}
        `;

        if (pending.length > 50) {
            container.innerHTML += `<p style="text-align: center; color: var(--gray-400); padding: 12px;">还有 ${pending.length - 50} 个文件...</p>`;
        }
    } catch (e) {
        console.error('加载知识文件失败:', e);
    }
}

function toggleAllKnowledge(el) {
    document.querySelectorAll('#knowledgeFiles .knowledge-file input[type="checkbox"]').forEach(cb => {
        cb.checked = el.checked;
    });
    updateKnowledgeCount();
}

function updateKnowledgeCount() {
    const selected = document.querySelectorAll('#knowledgeFiles .knowledge-file input:checked').length;
    const total = document.querySelectorAll('#knowledgeFiles .knowledge-file input').length;
    document.getElementById('statPending').textContent = `${selected}/${total}`;
}

async function importAllFiles() {
    const files = document.querySelectorAll('#knowledgeFiles input:checked');
    if (files.length === 0) {
        showToast('请选择要导入的文件', 'warning');
        return;
    }

    const selectedFiles = Array.from(files).map(f => f.dataset.path);
    const category = document.getElementById('knowledgeCategory')?.value || '其他';

    try {
        const data = await api('/api/knowledge/import/batch', {
            method: 'POST',
            body: JSON.stringify({ files: selectedFiles, category })
        });

        showToast(`已提交 ${selectedFiles.length} 个文件的导入任务`, 'success');
        closeModal('knowledgeModal');

        // 刷新列表
        await loadKnowledgeFiles();
    } catch (e) {
        showToast('导入失败', 'error');
    }
}

// ========== 标签功能 ==========

async function addTag(path, tag) {
    try {
        await api('/api/files/tags', {
            method: 'POST',
            body: JSON.stringify({ path, tag })
        });
        showToast(`已添加标签: ${tag}`);
    } catch (e) {
        showToast('添加标签失败', 'error');
    }
}

async function removeTag(path, tag) {
    try {
        await api(`/api/files/tags?path=${encodeURIComponent(path)}&tag=${encodeURIComponent(tag)}`, {
            method: 'DELETE'
        });
        showToast(`已移除标签: ${tag}`);
    } catch (e) {
        showToast('移除标签失败', 'error');
    }
}

async function loadFileTags(path) {
    try {
        const data = await api(`/api/files/tags?path=${encodeURIComponent(path)}`);
        return data.tags || [];
    } catch (e) {
        return [];
    }
}

async function loadAllTags() {
    try {
        const data = await api('/api/tags');
        return data.tags || [];
    } catch (e) {
        return [];
    }
}

// ========== 批量操作 ==========

async function batchDelete() {
    if (state.selectedFiles.size === 0) return;

    if (!confirm(`确定删除 ${state.selectedFiles.size} 个文件？`)) return;

    try {
        const data = await api('/api/files/batch-delete', {
            method: 'POST',
            body: JSON.stringify({ paths: Array.from(state.selectedFiles) })
        });

        showToast(`已删除 ${data.deleted.length} 个文件`);
        state.selectedFiles.clear();
        await loadFiles();
    } catch (e) {
        showToast('删除失败', 'error');
    }
}

async function batchMove() {
    if (state.selectedFiles.size === 0) return;

    const targetDir = prompt('移动到哪个文件夹？');
    if (!targetDir) return;

    try {
        const data = await api('/api/files/batch-move', {
            method: 'POST',
            body: JSON.stringify({
                paths: Array.from(state.selectedFiles),
                target_dir: targetDir
            })
        });

        showToast(`已移动 ${data.moved.length} 个文件`);
        state.selectedFiles.clear();
        await loadFiles();
    } catch (e) {
        showToast('移动失败', 'error');
    }
}

// ========== 标签功能 ==========

async function openTagModal() {
    if (state.selectedFiles.size === 0) {
        showToast('请先选择文件', 'warning');
        return;
    }

    openModal('tagModal');
    await loadCurrentTags();
    await loadQuickTags();
}

async function loadCurrentTags() {
    const paths = Array.from(state.selectedFiles);
    if (paths.length === 0) return;

    const allTags = new Set();
    for (const path of paths) {
        const tags = await loadFileTags(path);
        tags.forEach(t => allTags.add(t));
    }

    const container = document.getElementById('currentTags');
    if (allTags.size === 0) {
        container.innerHTML = '<span style="color: var(--gray-400);">暂无标签</span>';
        return;
    }

    container.innerHTML = Array.from(allTags).map(tag => `
        <span class="tag-item">
            ${tag}
            <button onclick="removeTagFromSelected('${tag}')">&times;</button>
        </span>
    `).join('');
}

async function loadQuickTags() {
    const allTags = await loadAllTags();
    const quickTags = ['重要', '待处理', '已完成', '参考资料', '紧急', '复习'];

    const container = document.getElementById('quickTags');
    container.innerHTML = quickTags.map(tag => `
        <button class="quick-tag ${allTags.includes(tag) ? 'active' : ''}" onclick="addTagToSelected('${tag}')">
            ${tag}
        </button>
    `).join('');
}

async function addTagToSelected(tag) {
    for (const path of state.selectedFiles) {
        await addTag(path, tag);
    }
    showToast(`已添加标签: ${tag}`);
    await loadCurrentTags();
    await loadQuickTags();
}

async function removeTagFromSelected(tag) {
    for (const path of state.selectedFiles) {
        await removeTag(path, tag);
    }
    showToast(`已移除标签: ${tag}`);
    await loadCurrentTags();
}

// ========== 存储统计 ==========

async function loadStorageStats() {
    try {
        const data = await api('/api/storage/stats');
        return data;
    } catch (e) {
        return null;
    }
}

// ========== 转写功能 ==========

let currentTranscribeFile = null;

function initTranscribe() {
    const dropzone = document.getElementById('transcribeDropzone');
    const fileInput = document.getElementById('audioInput');
    const selectBtn = document.getElementById('btnSelectAudio');
    const startBtn = document.getElementById('btnStartTranscribe');

    selectBtn?.addEventListener('click', () => fileInput?.click());

    fileInput?.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            selectTranscribeFile(e.target.files[0]);
        }
    });

    dropzone?.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone?.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone?.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            selectTranscribeFile(e.dataTransfer.files[0]);
        }
    });

    startBtn?.addEventListener('click', startTranscribe);
}

function selectTranscribeFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    const validExts = ['mp3', 'wav', 'm4a', 'ogg', 'flac', 'aac', 'wma'];
    if (!validExts.includes(ext)) {
        showToast('不支持的音频格式', 'error');
        return;
    }

    currentTranscribeFile = file;
    document.getElementById('btnStartTranscribe').disabled = false;
    document.getElementById('transcribeDropzone').innerHTML = `
        <i class="fas fa-music"></i>
        <p><strong>${file.name}</strong></p>
        <p class="upload-hint">${formatSize(file.size)}</p>
        <button class="btn btn-secondary" onclick="clearTranscribeFile()">清除</button>
    `;
}

function clearTranscribeFile() {
    currentTranscribeFile = null;
    document.getElementById('btnStartTranscribe').disabled = true;
    document.getElementById('audioInput').value = '';
    initTranscribePanel();
}

async function startTranscribe() {
    if (!currentTranscribeFile) {
        showToast('请先选择音视频文件', 'warning');
        return;
    }

    const lang = document.getElementById('transcribeLang')?.value || 'zh';
    const formData = new FormData();
    formData.append('file', currentTranscribeFile);
    formData.append('language', lang);

    // 显示进度
    const uploadPanel = document.querySelector('.transcribe-upload');
    const progressPanel = document.getElementById('transcribeProgress');
    const fileNameEl = document.getElementById('transcribeFileName');
    const statusEl = document.getElementById('transcribeStatus');

    if (uploadPanel) uploadPanel.style.display = 'none';
    if (progressPanel) progressPanel.style.display = 'block';
    if (fileNameEl) fileNameEl.textContent = currentTranscribeFile.name;
    if (statusEl) statusEl.textContent = '上传中...';

    try {
        // 先上传文件
        const uploadResp = await fetch('/api/transcribe/upload', {
            method: 'POST',
            body: formData
        });

        if (!uploadResp.ok) throw new Error('上传失败');
        const uploadData = await uploadResp.json();

        // 初始化转写任务（包含模型大小）
        document.getElementById('transcribeStatus').textContent = '开始转写...';
        const modelSize = document.getElementById('transcribeModel')?.value || 'small';
        const initForm = new FormData();
        initForm.append('source_file', uploadData.path);
        initForm.append('language', lang);
        initForm.append('model_size', modelSize);
        const initResp = await fetch('/api/transcribe/init', {
            method: 'POST',
            body: initForm
        }).then(r => r.json());

        // 轮询状态
        await pollTranscribeStatus(initResp.task_id);
    } catch (e) {
        showToast('转写失败: ' + e.message, 'error');
        initTranscribePanel();
    }
}

async function pollTranscribeStatus(taskId) {
    const maxAttempts = 120;
    let attempts = 0;

    const poll = async () => {
        if (attempts >= maxAttempts) {
            showToast('转写超时', 'error');
            initTranscribePanel();
            return;
        }

        try {
            const data = await api(`/api/transcribe/status/${taskId}`);

            if (data.status === 'completed') {
                showTranscribeResult(data.result?.text || data.text || '');
                return;
            } else if (data.status === 'error') {
                showToast('转写失败: ' + (data.error || '未知错误'), 'error');
                initTranscribePanel();
                return;
            }

            const statusEl = document.getElementById('transcribeStatus');
            const fillEl = document.getElementById('transcribeFill');
            const percentEl = document.getElementById('transcribePercent');
            if (statusEl) statusEl.textContent = '转写中... ' + data.progress + '%';
            if (fillEl) fillEl.style.width = (data.progress || 0) + '%';
            if (percentEl) percentEl.textContent = (data.progress || 0) + '%';

            attempts++;
            setTimeout(poll, 2000);
        } catch (e) {
            attempts++;
            setTimeout(poll, 3000);
        }
    };

    poll();
}

function showTranscribeResult(text) {
    document.getElementById('transcribeProgress').style.display = 'none';
    document.getElementById('transcribeResult').style.display = 'block';
    document.getElementById('transcribeText').value = text;

    document.getElementById('btnCopyText')?.addEventListener('click', () => {
        navigator.clipboard.writeText(text);
        showToast('已复制到剪贴板');
    });

    document.getElementById('btnDownloadSrt')?.addEventListener('click', () => {
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `transcript_${Date.now()}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    });
}

async function loadTranscribeHistory() {
    try {
        const data = await api('/api/transcribes');
        const list = data.tasks || [];

        const container = document.getElementById('transcribeHistoryList');
        if (list.length === 0) {
            container.innerHTML = '<p style="color: var(--gray-400);">暂无转写记录</p>';
            return;
        }

        container.innerHTML = list.slice(0, 10).map(t => `
            <div class="history-item" onclick="loadTranscribeResult('${t.task_id}')">
                <span class="history-name">${t.source_file?.split('/').pop() || '未知文件'}</span>
                <span class="history-status ${t.status}">${t.status === 'completed' ? '已完成' : t.status === 'processing' ? '处理中' : '失败'}</span>
                <span class="history-time">${formatTime(t.created_at)}</span>
            </div>
        `).join('');
    } catch (e) {
        console.error('加载转写历史失败:', e);
    }
}

async function loadTranscribeResult(taskId) {
    try {
        const data = await api(`/api/transcribe/status/${taskId}`);
        if (data.status === 'completed') {
            showTranscribeResult(data.result?.text || data.text || '');
        } else {
            showToast('转写尚未完成', 'warning');
        }
    } catch (e) {
        showToast('加载失败', 'error');
    }
}

function initTranscribePanel() {
    const uploadPanel = document.querySelector('.transcribe-upload');
    const progressPanel = document.getElementById('transcribeProgress');
    const resultPanel = document.getElementById('transcribeResult');
    const dropzone = document.getElementById('transcribeDropzone');

    if (uploadPanel) uploadPanel.style.display = 'block';
    if (progressPanel) progressPanel.style.display = 'none';
    if (resultPanel) resultPanel.style.display = 'none';
    if (dropzone) {
        dropzone.innerHTML = `
            <i class="fas fa-music"></i>
            <p>拖拽音频文件或点击选择</p>
            <p class="upload-hint">支持 mp3, wav, m4a, ogg, flac</p>
            <button class="btn btn-primary" id="btnSelectAudio">选择音频</button>
            <input type="file" id="audioInput" accept="audio/*" hidden>
        `;
    }
    currentTranscribeFile = null;
    const startBtn = document.getElementById('btnStartTranscribe');
    if (startBtn) startBtn.disabled = true;
    initTranscribe();
    loadTranscribeHistory();
}

// ========== RAG 搜索功能 (已禁用，保留代码供未来恢复) ==========
//
// async function checkRAGHealth() {
//     try {
//         const data = await api('/api/rag/health');
//         return data;
//     } catch (e) {
//         return { status: 'unavailable' };
//     }
// }
//
// async function loadRAGDatasets() {
//     try {
//         const data = await api('/api/rag/datasets');
//         return data.datasets || [];
//     } catch (e) {
//         return [];
//     }
// }
//
// async function searchRAG(query, dataset = 'all') {
//     const container = document.getElementById('ragSearchResults');
//     container.innerHTML = '<div class="loading-state"><div class="spinner"></div><span>搜索中...</span></div>';
//
//     try {
//         const data = await api('/api/rag/search', {
//             method: 'POST',
//             body: JSON.stringify({ query, dataset, top_k: 10 })
//         });
//
//         const results = data.results || [];
//         document.getElementById('ragSearchInfo').textContent = `找到 ${results.length} 条相关结果`;
//
//         if (results.length === 0) {
//             container.innerHTML = `
//                 <div class="empty-state">
//                     <i class="fas fa-search"></i>
//                     <p>未找到相关内容</p>
//                 </div>
//             `;
//             return;
//         }
//
//         container.innerHTML = results.map((r, i) => `
//             <div class="rag-result-item" data-index="${i}">
//                 <div class="rag-result-header">
//                     <span class="rag-result-score">${((r.similarity || 0.8) * 100).toFixed(1)}%</span>
//                     <span class="rag-result-source">${r.source || '未知来源'}</span>
//                 </div>
//                 <div class="rag-result-content">${highlightText(r.content || r.text || '', query)}</div>
//             </div>
//         `).join('');
//     } catch (e) {
//         container.innerHTML = `
//             <div class="empty-state">
//                 <i class="fas fa-exclamation-triangle"></i>
//                 <p>搜索失败: ${e.message}</p>
//                 <p class="upload-hint">请确保 RAGFlow 服务已启动</p>
//             </div>
//         `;
//     }
// }
//
// function highlightText(text, query) {
//     if (!query) return text;
//     const regex = new RegExp(`(${query})`, 'gi');
//     return text.replace(regex, '<mark>$1</mark>');
// }
//
// // ========== RAG 对话功能 ==========
//
// let ragChatHistory = [];
//
// async function sendRAGChat(question, dataset = 'all') {
//     const messagesContainer = document.getElementById('ragChatMessages');
//
//     // 添加用户消息
//     ragChatHistory.push({ role: 'user', content: question });
//     renderRAGChatMessages();
//
//     // 显示加载
//     const loadingId = 'rag-loading-' + Date.now();
//     messagesContainer.innerHTML += `
//         <div class="rag-message rag-message-assistant" id="${loadingId}">
//             <div class="spinner"></div>
//             <span>思考中...</span>
//         </div>
//     `;
//     messagesContainer.scrollTop = messagesContainer.scrollHeight;
//
//     try {
//         const data = await api('/api/rag/chat', {
//             method: 'POST',
//             body: JSON.stringify({ question, dataset })
//         });
//
//         // 移除加载状态
//         document.getElementById(loadingId)?.remove();
//
//         const answer = data.answer || data.data?.answer || '抱歉，暂无回答';
//         ragChatHistory.push({ role: 'assistant', content: answer });
//         renderRAGChatMessages();
//     } catch (e) {
//         document.getElementById(loadingId)?.remove();
//         ragChatHistory.push({ role: 'assistant', content: '抱歉，服务暂不可用。' });
//         renderRAGChatMessages();
//     }
// }
//
// function renderRAGChatMessages() {
//     const container = document.getElementById('ragChatMessages');
//     container.innerHTML = ragChatHistory.map(m => `
//         <div class="rag-message rag-message-${m.role}">
//             <div class="rag-message-avatar">
//                 ${m.role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>'}
//             </div>
//             <div class="rag-message-content">${m.content}</div>
//         </div>
//     `).join('');
//     container.scrollTop = container.scrollHeight;
// }
//
// // ========== RAG 模态框初始化 ==========
//
// function initRAGSearch() {
//     const searchBtn = document.getElementById('btnRagSearch');
//     const searchInput = document.getElementById('ragSearchInput');
//
//     searchBtn?.addEventListener('click', () => {
//         const query = searchInput?.value?.trim();
//         const dataset = document.getElementById('ragSearchDataset')?.value || 'all';
//         if (query) searchRAG(query, dataset);
//     });
//
//     searchInput?.addEventListener('keypress', (e) => {
//         if (e.key === 'Enter') {
//             searchBtn?.click();
//         }
//     });
// }
//
// function initRAGChat() {
//     const sendBtn = document.getElementById('btnRagChat');
//     const chatInput = document.getElementById('ragChatInput');
//
//     sendBtn?.addEventListener('click', () => {
//         const question = chatInput?.value?.trim();
//         const dataset = document.getElementById('ragChatDataset')?.value || 'all';
//         if (question) {
//             sendRAGChat(question, dataset);
//             chatInput.value = '';
//         }
//     });
//
//     chatInput?.addEventListener('keypress', (e) => {
//         if (e.key === 'Enter' && !e.shiftKey) {
//             e.preventDefault();
//             sendBtn?.click();
//         }
//     });
// }

// ========== 上传功能 ==========

function initUpload() {
    const dropzone = document.getElementById('uploadDropzone');
    const fileInput = document.getElementById('fileInput');

    // 点击选择
    dropzone.addEventListener('click', () => fileInput.click());

    // 文件选择
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleFiles(e.target.files);
        }
    });

    // 拖拽
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFiles(e.dataTransfer.files);
        }
    });
}

function handleFiles(files) {
    const queue = document.getElementById('uploadQueue');
    queue.innerHTML = '';

    Array.from(files).forEach(file => {
        const item = document.createElement('div');
        item.className = 'upload-item';
        item.innerHTML = `
            <div class="upload-item-info">
                <div class="upload-item-name">${file.name}</div>
                <div class="upload-item-size">${formatSize(file.size)}</div>
                <div class="upload-item-progress">
                    <div class="upload-item-fill" style="width: 0%"></div>
                </div>
            </div>
            <button class="icon-btn" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        queue.appendChild(item);

        // 开始上传
        uploadFile(file, item.querySelector('.upload-item-fill'));
    });
}

async function uploadFile(file, progressBar) {
    const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

    try {
        // 初始化
        const initRes = await fetch(`${API_BASE}/api/upload/init`, {
            method: 'POST',
            body: new URLSearchParams({
                file_name: file.name,
                file_size: file.size
            })
        });
        const initData = await initRes.json();

        if (initData.error) {
            showToast('上传失败: ' + initData.error, 'error');
            return;
        }

        const taskId = initData.task_id;
        const uploadedChunks = new Set(initData.uploaded_chunks || []);

        // 上传分片
        for (let i = 0; i < totalChunks; i++) {
            if (uploadedChunks.has(i)) continue;

            const start = i * CHUNK_SIZE;
            const end = Math.min(start + CHUNK_SIZE, file.size);
            const chunk = file.slice(start, end);

            const formData = new FormData();
            formData.append('task_id', taskId);
            formData.append('chunk_index', i);
            formData.append('chunk', chunk);

            await fetch(`${API_BASE}/api/upload/chunk`, {
                method: 'POST',
                body: formData
            });

            const percent = ((i + 1) / totalChunks * 100).toFixed(0);
            progressBar.style.width = percent + '%';
        }

        // 合并
        await fetch(`${API_BASE}/api/upload/merge`, {
            method: 'POST',
            body: new URLSearchParams({ task_id: taskId })
        });

        progressBar.style.width = '100%';
        showToast(`${file.name} 上传完成`);
        await loadFiles();

    } catch (e) {
        showToast('上传失败', 'error');
    }
}

// ========== 新建文件夹 ==========

async function createFolder() {
    const name = prompt('请输入文件夹名称:');
    if (!name) return;

    try {
        await api('/api/files/folder', {
            method: 'POST',
            body: JSON.stringify({ name, path: state.currentPath })
        });
        showToast('文件夹已创建');
        await loadFiles();
    } catch (e) {
        showToast('创建失败', 'error');
    }
}

// ========== 搜索功能 ==========

async function searchFiles(query) {
    if (!query) {
        await loadFiles();
        return;
    }

    try {
        let url = `/api/files/search?q=${encodeURIComponent(query)}`;
        if (state.currentSource === 'uploads') {
            url += '&source=uploads';
        } else if (state.currentSource === 'downloads') {
            url += '&source=downloads';
        }
        const data = await api(url);
        state.files = data.results || data.items || [];
        renderFiles();
    } catch (e) {
        const filtered = state.files.filter(f =>
            f.name.toLowerCase().includes(query.toLowerCase())
        );
        state.files = filtered;
        renderFiles();
    }
}

// ========== 侧边栏导航 ==========

async function switchView(view, category) {
    // 更新导航状态
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    if (view === 'category' && category) {
        const navEl = document.querySelector(`[data-view="category"][data-category="${category}"]`);
        if (navEl) navEl.classList.add('active');
    } else {
        document.querySelector(`[data-view="${view}"]`)?.classList.add('active');
    }

    const titles = {
        all: '全部文件',
        upload: '上传文件',
        uploads: '上传记录',
        downloads: '下载目录',
        category: category || '分类',
        transcribe: '音频转写',
        knowledge: '知识导入',
        extract: '文本提取',
        cloud: '云盘管理',
        logs: '系统日志',
        openviking: 'OpenViking专区',
        settings: '设置',
        'love-zone': '❤️ 恋爱专区'
    };

    document.getElementById('currentPath').innerHTML = `
        <i class="fas fa-folder"></i>
        ${titles[view] || view}
    `;

    // 设置视图状态
    state.currentNavView = view;
    state.currentCategory = category || '';

    if (view === 'uploads') {
        state.currentSource = 'uploads';
    } else if (view === 'downloads') {
        state.currentSource = 'downloads';
    } else if (view === 'category') {
        state.currentSource = 'downloads';
    } else {
        state.currentSource = 'all';
    }

    state.currentPath = (view === 'category' && category) ? category : '/';
    state.selectedFiles.clear();

    if (view === 'upload') {
        openUploadModal();
    } else if (view === 'cloud') {
        openCloudModal();
    } else if (view === 'knowledge') {
        openKnowledgeModal();
    } else if (view === 'transcribe') {
        openModal('transcribeModal');
        initTranscribePanel();
    // } else if (view === 'rag-search') {
    //     openModal('ragSearchModal');
    //     initRAGSearch();
    // } else if (view === 'rag-chat') {
    //     openModal('ragChatModal');
    //     initRAGChat();
    } else if (view === 'love-zone') {
        document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
        const backBtn2 = document.getElementById('btnBack');
        if (backBtn2) backBtn2.style.display = 'none';
        state.currentSource = 'uploads';
        state.currentPath = '/';
        await loadLoveZoneFiles();
    } else if (view === 'extract') {
        showExtractModal();
    } else if (view === 'logs') {
        showLogsModal();
    } else if (view === 'openviking') {
        showOpenVikingModal();
    } else {
        document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
        const backBtn2 = document.getElementById('btnBack');
        if (backBtn2) backBtn2.style.display = 'none';
        await loadFiles();
    }
}

// ========== 视图切换 ==========

function setView(view) {
    state.currentView = view;

    document.querySelectorAll('.view-toggle .icon-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });

    renderFiles();
}

// ========== 加载状态 ==========

function showLoading(show) {
    const el = document.getElementById('loadingState');
    if (el) el.style.display = show ? 'flex' : 'none';
}

// ========== 存储信息 ==========

async function updateNavCounts() {
    try {
        if (state.currentNavView === 'all') {
            const navCountEl = document.getElementById('navAllCount');
            if (navCountEl) navCountEl.textContent = state.files.length;
        }
        const data = await api('/api/storage/stats');
        const storageUsedEl = document.getElementById('storageUsed');
        const storageFillEl = document.getElementById('storageFill');
        const used = (data.uploads_size || 0) + (data.db_total_size || 0);
        const totalStorage = 100 * 1024 * 1024 * 1024;
        const percent = Math.min((used / totalStorage * 100), 100).toFixed(1);
        if (storageUsedEl) storageUsedEl.textContent = `${formatSize(used)} / 100 GB`;
        if (storageFillEl) storageFillEl.style.width = percent + '%';
    } catch (e) {
        console.error('更新存储信息失败:', e);
    }
}

// ========== 事件绑定 ==========

document.addEventListener('DOMContentLoaded', async () => {
    // 初始化上传队列管理器
    await UploadQueueManager.init();
    
    // 初始化上传
    initUpload();

    // 加载数据
    loadFiles();
    
    // 检查未完成的上传任务
    await checkPendingUploads();

    // 视图切换
    document.querySelectorAll('.view-toggle .icon-btn').forEach(btn => {
        btn.addEventListener('click', () => setView(btn.dataset.view));
    });

    // 全选
    document.getElementById('selectAll')?.addEventListener('change', (e) => {
        if (e.target.checked) {
            state.files.forEach(f => state.selectedFiles.add(f.path));
        } else {
            state.selectedFiles.clear();
        }
        updateToolbar();
        renderFiles();
    });

    // 顶部搜索
    document.getElementById('topSearchInput')?.addEventListener('input', (e) => {
        searchFiles(e.target.value);
    });

    // 侧边搜索
    document.getElementById('searchInput')?.addEventListener('input', (e) => {
        searchFiles(e.target.value);
    });

    // 导航点击
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = item.dataset.view;
            const category = item.dataset.category;
            switchView(view, category);
        });
    });

    // 工具栏按钮
    document.getElementById('btnUpload')?.addEventListener('click', openUploadModal);
    document.getElementById('btnNewFolder')?.addEventListener('click', createFolder);
    document.getElementById('btnDelete')?.addEventListener('click', deleteSelectedFiles);

    // cloud nav handled by nav-item listener
    document.getElementById('btnDownload')?.addEventListener('click', () => {
        state.selectedFiles.forEach(path => downloadFile(path));
    });
    document.getElementById('btnShare')?.addEventListener('click', () => {
        if (state.selectedFiles.size === 1) {
            showShareModal(Array.from(state.selectedFiles)[0]);
        }
    });
    document.getElementById('btnKnowledge')?.addEventListener('click', openKnowledgeModal);
    document.getElementById('btnMove')?.addEventListener('click', batchMove);
    document.getElementById('btnTag')?.addEventListener('click', openTagModal);

    // transcribe nav handled by nav-item listener

    // rag-search nav handled by nav-item listener

    // rag-chat nav handled by nav-item listener

    // RAG 模态框关闭
    document.getElementById('btnCloseRagSearch')?.addEventListener('click', () => closeModal('ragSearchModal'));
    document.getElementById('btnCloseRagChat')?.addEventListener('click', () => closeModal('ragChatModal'));

    // 返回按钮
    document.getElementById('btnBack')?.addEventListener('click', () => {
        const parts = state.currentPath.split('/').filter(Boolean);
        if (parts.length > 1) {
            parts.pop();
            navigateTo('/' + parts.join('/'));
        } else {
            navigateTo('/');
        }
    });

    // 模态框关闭按钮
    document.getElementById('btnCloseUpload')?.addEventListener('click', closeUploadModal);
    document.getElementById('btnCloseCloud')?.addEventListener('click', closeCloudModal);
    document.getElementById('btnCloseKnowledge')?.addEventListener('click', closeKnowledgeModal);
    document.getElementById('btnCloseShare')?.addEventListener('click', () => closeModal('shareModal'));
    document.getElementById('btnCloseDetail')?.addEventListener('click', closeDetail);
    document.getElementById('btnCloseTranscribe')?.addEventListener('click', () => closeModal('transcribeModal'));
    document.getElementById('btnCloseTag')?.addEventListener('click', () => closeModal('tagModal'));
    document.getElementById('btnAddNewTag')?.addEventListener('click', async () => {
        const tag = document.getElementById('newTagInput')?.value?.trim();
        if (tag) {
            await addTagToSelected(tag);
            document.getElementById('newTagInput').value = '';
        }
    });

    // 云盘标签切换
    document.querySelectorAll('.cloud-tab').forEach(tab => {
        tab.addEventListener('click', () => showCloudTab(tab.dataset.tab));
    });

    // 添加云盘
    document.getElementById('btnAddDisk')?.addEventListener('click', addDisk);

    // 知识导入
    document.getElementById('btnImportAll')?.addEventListener('click', importAllFiles);
    document.getElementById('btnScanKnowledge')?.addEventListener('click', loadKnowledgeFiles);

    // 文本提取
    document.getElementById('btnCloseExtract')?.addEventListener('click', closeExtractModal);
    document.getElementById('btnSelectExtract')?.addEventListener('click', () => document.getElementById('extractInput')?.click());
    document.getElementById('btnSelectFolder')?.addEventListener('click', () => document.getElementById('folderInput')?.click());
    document.getElementById('extractInput')?.addEventListener('change', handleExtractFileSelect);
    document.getElementById('folderInput')?.addEventListener('change', handleFolderSelect);

    // 文本提取拖拽
    const extractDropzone = document.getElementById('extractDropzone');
    if (extractDropzone) {
        extractDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            extractDropzone.classList.add('dragover');
        });
        extractDropzone.addEventListener('dragleave', () => extractDropzone.classList.remove('dragover'));
        extractDropzone.addEventListener('drop', handleExtractDrop);
    }

    // 分享
    document.getElementById('btnCreateShare')?.addEventListener('click', createShareLink);
    document.getElementById('btnCopyLink')?.addEventListener('click', copyShareLink);

    // 点击模态框背景关闭
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });

    // ESC键关闭模态框
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal.active').forEach(modal => {
                modal.classList.remove('active');
            });
        }
    });
});

// ========== 文本提取 ==========

function showExtractModal() {
    document.getElementById('extractModal')?.classList.add('active');
    loadExtractStatus();
}

function closeExtractModal() {
    document.getElementById('extractModal')?.classList.remove('active');
}

async function loadExtractStatus() {
    try {
        const [statsRes, listRes] = await Promise.all([
            fetch('/api/extract/status'),
            fetch('/api/extract/list')
        ]);
        
        if (!statsRes.ok || !listRes.ok) return;
        
        const stats = await statsRes.json();
        const list = await listRes.json();
        
        // 更新统计
        document.getElementById('extractTotal').textContent = stats.total || 0;
        document.getElementById('extractCompleted').textContent = stats.completed || 0;
        document.getElementById('extractPending').textContent = stats.pending || 0;
        document.getElementById('extractError').textContent = stats.error || 0;
        
        // 分类显示
        const pending = list.filter(t => t.status === 'pending' || t.status === 'processing');
        const history = list.filter(t => t.status === 'completed' || t.status === 'error');
        
        document.getElementById('pendingCount').textContent = `(${pending.length})`;
        document.getElementById('historyCount').textContent = `(${history.length})`;
        
        renderExtractPendingList(pending);
        renderExtractHistoryList(history);
    } catch (e) {
        console.error('加载提取状态失败:', e);
    }
}

function renderExtractPendingList(tasks) {
    const container = document.getElementById('extractPendingList');
    if (!container) return;
    
    if (!tasks.length) {
        container.innerHTML = '<div class="empty-hint">暂无待处理文件</div>';
        return;
    }
    
    container.innerHTML = tasks.map(task => `
        <div class="file-item extract-item" data-id="${task.id}">
            <div class="file-info">
                <i class="fas fa-${getFileIcon(task.file_ext || task.file_name)}"></i>
                <span class="file-name">${task.file_name}</span>
                <span class="file-status status-${task.status}">${getStatusText(task.status)}</span>
            </div>
            <div class="file-actions">
                ${task.status === 'processing' ? '<span class="loading"><i class="fas fa-spinner fa-spin"></i></span>' : ''}
                ${task.status === 'pending' ? `<button class="btn btn-sm btn-primary" onclick="manualExtract(${task.id})">提取</button>` : ''}
            </div>
        </div>
    `).join('');
}

function renderExtractHistoryList(tasks) {
    const container = document.getElementById('extractHistoryList');
    if (!container) return;
    
    if (!tasks.length) {
        container.innerHTML = '<div class="empty-hint">暂无已处理记录</div>';
        return;
    }
    
    container.innerHTML = tasks.map(task => `
        <div class="file-item extract-item ${task.status}" data-id="${task.id}">
            <div class="file-info">
                <i class="fas fa-${getFileIcon(task.file_ext || task.file_name)}"></i>
                <span class="file-name">${task.file_name}</span>
                <span class="file-status status-${task.status}">${getStatusText(task.status)}</span>
                <span class="file-chars">${task.char_count ? task.char_count + '字' : ''}</span>
            </div>
            <div class="file-actions">
                ${task.status === 'completed' && task.text_content ? `<button class="btn btn-sm" onclick="viewExtractContent(${task.id})">查看</button>` : ''}
                ${task.status === 'error' ? `<span class="error-msg">${task.error_message || '失败'}</span>` : ''}
            </div>
        </div>
    `).join('');
}

async function handleExtractDrop(e) {
    e.preventDefault();
    e.target.closest('.upload-dropzone')?.classList.remove('dragover');
    const files = Array.from(e.dataTransfer.files);
    if (files.length) await uploadExtractFiles(files);
}

async function handleExtractFileSelect(e) {
    const files = Array.from(e.target.files);
    if (files.length) await uploadExtractFiles(files);
    e.target.value = '';
}

async function handleFolderSelect(e) {
    const files = Array.from(e.target.files);
    if (files.length) {
        clientLog('info', '选择文件夹上传', {
            fileCount: files.length,
            firstFile: files[0]?.webkitRelativePath || files[0]?.name
        });
        await uploadExtractFiles(files);
    }
    e.target.value = '';
}

async function uploadExtractFiles(files) {
    const targetDir = document.getElementById('extractTargetDir')?.value || '';
    const LARGE_SIZE = 5 * 1024 * 1024; // 5MB以上用断点上传

    for (const file of files) {
        if (file.size > LARGE_SIZE) {
            await chunkedExtractUpload(file, targetDir);
        } else {
            await simpleExtractUpload([file], targetDir);
        }
    }
    loadExtractStatus();
}

async function simpleExtractUpload(files, targetDir) {
    const fileNames = files.map(f => f.name).join(', ');
    const fileSizes = files.map(f => `${f.name}(${(f.size / 1024).toFixed(2)}KB)`).join(', ');
    
    clientLog('info', '开始上传文件', {
        files: fileNames,
        sizes: fileSizes,
        targetDir: targetDir || '根目录',
        totalFiles: files.length
    });

    // 将文件添加到上传队列
    for (const file of files) {
        await UploadQueueManager.addUpload({
            file: file,
            targetDir: targetDir
        });
    }

    // 显示进度条
    showUploadProgress(fileNames, '已加入上传队列');

    // 开始处理队列
    await processUploadQueue();
}

async function processUploadQueue() {
    const pendingUploads = await UploadQueueManager.getPendingUploads();
    
    if (pendingUploads.length === 0) {
        hideUploadProgress();
        return;
    }

    for (const upload of pendingUploads) {
        if (upload.file instanceof File) {
            // 继续上传
            await uploadSingleFile(upload);
        } else {
            // File对象丢失（页面刷新），需要重新选择文件
            await UploadQueueManager.updateUpload(upload.id, {
                status: 'failed',
                error: 'File对象丢失，请重新选择文件'
            });
        }
    }

    // 清理已完成的任务
    await UploadQueueManager.clearCompleted();
    
    // 更新队列徽章
    updateQueueBadge();
    
    // 刷新状态
    loadExtractStatus();
}

async function uploadSingleFile(upload) {
    const formData = new FormData();
    formData.append('file', upload.file);
    if (upload.targetDir) formData.append('target_dir', upload.targetDir);

    await UploadQueueManager.updateUpload(upload.id, { status: 'uploading' });
    showUploadProgress(upload.fileName, '上传中...');

    try {
        const startTime = Date.now();
        
        // 使用XMLHttpRequest以获取上传进度
        const xhr = new XMLHttpRequest();
        const uploadPromise = new Promise((resolve, reject) => {
            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    const speed = e.loaded / ((Date.now() - startTime) / 1000);
                    const timeLeft = (e.total - e.loaded) / speed;
                    updateUploadProgress(percent, `上传中 ${percent}%`, null, formatSpeed(speed), formatTime(timeLeft));
                    UploadQueueManager.updateUpload(upload.id, { progress: percent });
                }
            };
            
            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    reject(new Error('上传失败: ' + xhr.status));
                }
            };
            
            xhr.onerror = () => reject(new Error('网络错误'));
            
            xhr.open('POST', '/api/extract/upload');
            xhr.send(formData);
        });
        
        const data = await uploadPromise;
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
        
        await UploadQueueManager.updateUpload(upload.id, {
            status: 'completed',
            taskId: data.task_id,
            progress: 100
        });
        
        clientLog('info', '文件上传成功', {
            fileName: upload.fileName,
            taskId: data.task_id,
            fileType: data.file_type,
            charCount: data.char_count,
            elapsed: elapsed + 's'
        });
        
        showUploadProgress(upload.fileName, '上传完成', 'success');
        showToast(`${upload.fileName} 上传成功`, 'success');
        
        // 触发文本提取
        if (data.file_path) {
            await triggerExtractByPath(data.file_path, upload.fileName, upload.targetDir);
        }
    } catch (e) {
        await UploadQueueManager.updateUpload(upload.id, {
            status: 'failed',
            error: e.message
        });
        
        clientLog('error', '文件上传异常', {
            fileName: upload.fileName,
            error: e.message,
            stack: e.stack
        });
        showUploadProgress(upload.fileName, '上传失败: ' + e.message, 'error');
        showToast('上传失败: ' + e.message, 'error');
    }
}

async function chunkedExtractUpload(file, targetDir) {
    const CHUNK_SIZE = 5 * 1024 * 1024;
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

    // 将文件添加到上传队列
    const upload = await UploadQueueManager.addUpload({
        file: file,
        targetDir: targetDir
    });

    clientLog('info', '开始分片上传', {
        fileName: file.name,
        fileSize: (file.size / 1024 / 1024).toFixed(2) + 'MB',
        totalChunks: totalChunks,
        uploadId: upload.id,
        targetDir: targetDir || '根目录'
    });

    // 显示进度条
    showUploadProgress(file.name, `准备上传 (${totalChunks}分片)...`);

    try {
        // 1. 初始化
        const startTime = Date.now();
        const initFormData = new FormData();
        initFormData.append('file_name', file.name);
        initFormData.append('file_size', file.size);
        if (targetDir) initFormData.append('target_dir', targetDir);
        
        const initRes = await fetch('/api/upload/init', {
            method: 'POST',
            body: initFormData
        });
        
        if (!initRes.ok) {
            const errorText = await initRes.text();
            clientLog('error', '分片上传初始化失败', {
                uploadId: upload.id,
                status: initRes.status,
                error: errorText
            });
            throw new Error('初始化失败: ' + errorText);
        }
        
        const initData = await initRes.json();
        await UploadQueueManager.updateUpload(upload.id, { 
            status: 'uploading',
            taskId: initData.task_id 
        });
        
        clientLog('info', '分片上传初始化成功', { uploadId: upload.id, taskId: initData.task_id });
        updateUploadProgress(0, '初始化完成');

        // 2. 分片上传
        let uploadedSize = 0;
        for (let i = 0; i < totalChunks; i++) {
            const start = i * CHUNK_SIZE;
            const chunk = file.slice(start, start + CHUNK_SIZE);
            const formData = new FormData();
            formData.append('task_id', initData.task_id);
            formData.append('chunk_index', i);
            formData.append('chunk', chunk);

            const chunkStartTime = Date.now();
            const chunkRes = await fetch('/api/upload/chunk', { method: 'POST', body: formData });
            const chunkElapsed = ((Date.now() - chunkStartTime) / 1000).toFixed(2);
            
            if (!chunkRes.ok) {
                const errorText = await chunkRes.text();
                clientLog('error', '分片上传失败', {
                    uploadId: upload.id,
                    chunkIndex: i,
                    status: chunkRes.status,
                    error: errorText
                });
                throw new Error(`分片${i+1}失败: ${errorText}`);
            }
            
            uploadedSize += chunk.size;
            const progress = Math.round((i + 1) / totalChunks * 100);
            const speed = uploadedSize / ((Date.now() - startTime) / 1000);
            const timeLeft = (file.size - uploadedSize) / speed;
            
            updateUploadProgress(progress, `上传分片 ${i+1}/${totalChunks}`, null, formatSpeed(speed), formatTime(timeLeft));
            await UploadQueueManager.updateUpload(upload.id, { progress: progress });
            
            clientLog('info', '分片上传进度', {
                uploadId: upload.id,
                chunkIndex: i,
                progress: progress + '%',
                chunkTime: chunkElapsed + 's'
            });
        }

        // 3. 合并
        updateUploadProgress(100, '合并文件中...');
        const mergeStartTime = Date.now();
        const mergeFormData = new FormData();
        mergeFormData.append('task_id', initData.task_id);
        
        const mergeRes = await fetch('/api/upload/merge', {
            method: 'POST',
            body: mergeFormData
        });

        const mergeElapsed = ((Date.now() - mergeStartTime) / 1000).toFixed(2);

        if (mergeRes.ok) {
            const data = await mergeRes.json();
            const totalElapsed = ((Date.now() - startTime) / 1000).toFixed(2);
            
            await UploadQueueManager.updateUpload(upload.id, {
                status: 'completed',
                progress: 100
            });
            
            clientLog('info', '分片上传完成', {
                uploadId: upload.id,
                fileName: file.name,
                filePath: data.file_path,
                mergeTime: mergeElapsed + 's',
                totalTime: totalElapsed + 's'
            });
            
            showUploadProgress(file.name, '上传完成', 'success');
            showToast(`上传完成: ${file.name}`, 'success');
            
            // 4. 触发提取
            if (data.file_path) {
                await triggerExtractByPath(data.file_path, file.name, targetDir);
            }
        } else {
            const errorText = await mergeRes.text();
            clientLog('error', '分片合并失败', {
                uploadId: upload.id,
                status: mergeRes.status,
                error: errorText
            });
            throw new Error('合并失败: ' + errorText);
        }
    } catch (e) {
        await UploadQueueManager.updateUpload(upload.id, {
            status: 'failed',
            error: e.message
        });
        
        clientLog('error', '分片上传异常', {
            uploadId: upload.id,
            fileName: file.name,
            error: e.message,
            stack: e.stack
        });
        showUploadProgress(file.name, '上传失败: ' + e.message, 'error');
        showToast('上传失败: ' + e.message, 'error');
    }
}

async function checkPendingUploads() {
    try {
        const pending = await UploadQueueManager.getPendingUploads();
        if (pending.length > 0) {
            console.log(`发现 ${pending.length} 个未完成的上传任务`);
            showToast(`发现 ${pending.length} 个未完成的上传任务`, 'info');
            
            // 显示待恢复的上传列表
            const fileList = pending.map(u => `• ${u.fileName} (${u.progress || 0}%)`).join('\n');
            if (confirm(`以下上传任务未完成，是否继续？\n\n${fileList}\n\n点击"确定"继续上传`)) {
                processUploadQueue();
            }
        }
    } catch (e) {
        console.error('检查未完成上传失败:', e);
    }
}

function updateQueueBadge() {
    const badge = document.getElementById('uploadQueueBadge');
    if (!badge) return;
    
    const pending = UploadQueueManager.uploads.filter(u => u.status === 'pending' || u.status === 'uploading');
    if (pending.length > 0) {
        badge.textContent = pending.length;
        badge.style.display = 'flex';
    } else {
        badge.style.display = 'none';
    }
}

async function triggerExtractByPath(filePath, fileName, targetDir) {
    clientLog('info', '触发文本提取', {
        filePath: filePath,
        fileName: fileName,
        targetDir: targetDir || '根目录'
    });
    
    try {
        const startTime = Date.now();
        const res = await fetch('/api/extract/process', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                file_path: filePath,
                file_name: fileName,
                target_dir: targetDir
            })
        });
        
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
        
        if (res.ok) {
            const data = await res.json();
            clientLog('info', '文本提取触发成功', {
                fileName: fileName,
                taskId: data.task_id,
                elapsed: elapsed + 's'
            });
            showToast('已开始提取...', 'info');
        } else {
            const errorData = await res.json().catch(() => ({}));
            clientLog('error', '文本提取触发失败', {
                fileName: fileName,
                status: res.status,
                error: errorData.detail || '未知错误'
            });
            showToast('提取失败', 'error');
        }
    } catch (e) {
        clientLog('error', '文本提取触发异常', {
            fileName: fileName,
            error: e.message,
            stack: e.stack
        });
        console.error('触发提取失败:', e);
    }
}

async function manualExtract(id) {
    clientLog('info', '手动触发提取', { taskId: id });
    
    try {
        const startTime = Date.now();
        const res = await fetch(`/api/extract/process/${id}`, { method: 'POST' });
        const data = await res.json();
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
        
        if (res.ok) {
            clientLog('info', '手动提取触发成功', {
                taskId: id,
                elapsed: elapsed + 's'
            });
            showToast('已开始提取', 'success');
            // 轮询状态
            pollExtractStatus(id);
        } else {
            clientLog('error', '手动提取触发失败', {
                taskId: id,
                status: res.status,
                error: data.detail || '未知错误'
            });
            showToast(data.detail || '提取失败', 'error');
        }
    } catch (e) {
        clientLog('error', '手动提取触发异常', {
            taskId: id,
            error: e.message,
            stack: e.stack
        });
        showToast('提取失败: ' + e.message, 'error');
    }
}

async function pollExtractStatus(id) {
    const maxAttempts = 60;
    let attempts = 0;
    
    const poll = async () => {
        if (attempts++ >= maxAttempts) return;
        
        try {
            const res = await fetch('/api/extract/list');
            const list = await res.json();
            const task = list.find(t => t.id === id);
            
            if (task) {
                if (task.status === 'completed') {
                    showToast('提取完成', 'success');
                    loadExtractStatus();
                } else if (task.status === 'error') {
                    showToast('提取失败: ' + (task.error_message || '未知错误'), 'error');
                    loadExtractStatus();
                } else {
                    setTimeout(poll, 2000);
                }
            }
        } catch (e) {
            setTimeout(poll, 5000);
        }
    };
    
    poll();
}

async function viewExtractContent(id) {
    try {
        const res = await fetch('/api/extract/list');
        const list = await res.json();
        const task = list.find(t => t.id === id);
        
        if (task && task.text_content) {
            showTextPreview(task.file_name, task.text_content);
        }
    } catch (e) {
        showToast('加载失败', 'error');
    }
}

function showTextPreview(title, content) {
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.innerHTML = `
        <div class="modal-content modal-large">
            <div class="modal-header">
                <h3><i class="fas fa-file-alt"></i> ${title}</h3>
                <button class="icon-btn" onclick="this.closest('.modal').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <pre class="text-preview">${escapeHtml(content)}</pre>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getStatusText(status) {
    const map = { pending: '待处理', processing: '处理中', completed: '已完成', error: '失败' };
    return map[status] || status;
}

// ========== 系统日志 ==========

let logsAutoRefreshInterval = null;

function showLogsModal() {
    document.getElementById('logsModal')?.classList.add('active');
    loadLogs();
    initLogsEvents();
}

function closeLogsModal() {
    document.getElementById('logsModal')?.classList.remove('active');
    stopLogsAutoRefresh();
}

function initLogsEvents() {
    document.getElementById('btnCloseLogs')?.addEventListener('click', closeLogsModal);
    document.getElementById('btnRefreshLogs')?.addEventListener('click', loadLogs);
    document.getElementById('btnAutoRefresh')?.addEventListener('click', toggleLogsAutoRefresh);
    document.getElementById('btnClearLogs')?.addEventListener('click', clearLogsDisplay);
    document.getElementById('logsLevelFilter')?.addEventListener('change', loadLogs);
    document.getElementById('logsLimit')?.addEventListener('change', loadLogs);
}

async function loadLogs() {
    const container = document.getElementById('logsContainer');
    if (!container) return;
    
    const level = document.getElementById('logsLevelFilter')?.value || '';
    const limit = document.getElementById('logsLimit')?.value || 100;
    
    clientLog('info', '加载系统日志', { level: level || '全部', limit: limit });
    
    try {
        const res = await fetch(`/api/client/logs?limit=${limit}&level=${level}`);
        const data = await res.json();
        
        if (data.logs && data.logs.length > 0) {
            renderLogs(data.logs);
            document.getElementById('logsCount').textContent = `共 ${data.total} 条日志`;
            document.getElementById('logsLastUpdate').textContent = `最后更新: ${new Date().toLocaleTimeString()}`;
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-list-alt"></i>
                    <p>暂无日志记录</p>
                </div>
            `;
        }
    } catch (e) {
        clientLog('error', '加载日志失败', { error: e.message });
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>加载日志失败: ${e.message}</p>
            </div>
        `;
    }
}

function renderLogs(logs) {
    const container = document.getElementById('logsContainer');
    if (!container) return;
    
    container.innerHTML = logs.map(log => {
        const levelClass = log.level || 'info';
        const timestamp = log.timestamp || '';
        const message = escapeHtml(log.message || log.raw || '');
        
        return `
            <div class="log-entry ${levelClass}">
                <span class="log-timestamp">${timestamp}</span>
                <span class="log-level ${levelClass}">${levelClass}</span>
                <span class="log-message">${message}</span>
            </div>
        `;
    }).join('');
    
    // 滚动到底部
    container.scrollTop = container.scrollHeight;
}

function toggleLogsAutoRefresh() {
    const btn = document.getElementById('btnAutoRefresh');
    if (logsAutoRefreshInterval) {
        stopLogsAutoRefresh();
        btn.innerHTML = '<i class="fas fa-play"></i> 自动刷新';
        btn.classList.remove('active');
    } else {
        logsAutoRefreshInterval = setInterval(loadLogs, 3000);
        btn.innerHTML = '<i class="fas fa-pause"></i> 停止刷新';
        btn.classList.add('active');
        clientLog('info', '开启日志自动刷新');
    }
}

function stopLogsAutoRefresh() {
    if (logsAutoRefreshInterval) {
        clearInterval(logsAutoRefreshInterval);
        logsAutoRefreshInterval = null;
    }
}

function clearLogsDisplay() {
    const container = document.getElementById('logsContainer');
    if (container) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-list-alt"></i>
                <p>日志已清空</p>
            </div>
        `;
    }
    document.getElementById('logsCount').textContent = '共 0 条日志';
    document.getElementById('logsLastUpdate').textContent = `最后更新: ${new Date().toLocaleTimeString()}`;
}

// ========== 上传进度条 ==========

function showUploadProgress(fileName, status, type = 'info') {
    const progressEl = document.getElementById('uploadProgress');
    const fileNameEl = document.getElementById('uploadFileName');
    const statusEl = document.getElementById('uploadStatus');
    const fillEl = document.getElementById('uploadFill');
    const percentEl = document.getElementById('uploadPercent');
    
    if (!progressEl) return;
    
    progressEl.style.display = 'block';
    progressEl.className = 'upload-progress ' + (type || '');
    fileNameEl.textContent = fileName;
    statusEl.textContent = status;
    fillEl.style.width = '0%';
    percentEl.textContent = '0%';
}

function updateUploadProgress(percent, status, type = null, speed = null, timeLeft = null) {
    const progressEl = document.getElementById('uploadProgress');
    const statusEl = document.getElementById('uploadStatus');
    const fillEl = document.getElementById('uploadFill');
    const percentEl = document.getElementById('uploadPercent');
    const speedEl = document.getElementById('uploadSpeed');
    const timeLeftEl = document.getElementById('uploadTimeLeft');
    
    if (!progressEl) return;
    
    if (type) progressEl.className = 'upload-progress ' + type;
    if (status) statusEl.textContent = status;
    
    fillEl.style.width = percent + '%';
    percentEl.textContent = percent + '%';
    
    if (speedEl && speed) speedEl.textContent = speed;
    if (timeLeftEl && timeLeft) timeLeftEl.textContent = timeLeft;
}

function hideUploadProgress() {
    const progressEl = document.getElementById('uploadProgress');
    if (progressEl) {
        progressEl.style.display = 'none';
    }
}

function formatSpeed(bytesPerSecond) {
    if (bytesPerSecond < 1024) {
        return bytesPerSecond.toFixed(1) + ' B/s';
    } else if (bytesPerSecond < 1024 * 1024) {
        return (bytesPerSecond / 1024).toFixed(1) + ' KB/s';
    } else {
        return (bytesPerSecond / (1024 * 1024)).toFixed(1) + ' MB/s';
    }
}

function formatTime(seconds) {
    if (!seconds || seconds < 0) return '-';
    if (seconds < 60) {
        return Math.round(seconds) + '秒';
    } else if (seconds < 3600) {
        return Math.round(seconds / 60) + '分钟';
    } else {
        return (seconds / 3600).toFixed(1) + '小时';
    }
}

// ========== OpenViking 专区 ==========

const OV_CONFIG = {
    baseUrl: 'http://localhost:1933',
    apiKey: 'openviking-root-key-2026',
    account: 'default',
    user: 'shared'
};

function showOpenVikingModal() {
    document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
    const modal = document.getElementById('openvikingModal');
    if (modal) {
        modal.classList.add('active');
        initOpenViking();
    }
}

function initOpenViking() {
    // 绑定关闭按钮
    document.getElementById('btnCloseOpenViking')?.addEventListener('click', () => {
        document.getElementById('openvikingModal')?.classList.remove('active');
    });
    
    // 绑定标签页切换
    document.querySelectorAll('.openviking-tabs .tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.openviking-tabs .tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab)?.classList.add('active');
        });
    });
    
    // 绑定搜索
    document.getElementById('btnOvSearch')?.addEventListener('click', ovSearch);
    document.getElementById('ovSearchInput')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') ovSearch();
    });
    
    // 绑定写入
    document.getElementById('btnOvWrite')?.addEventListener('click', ovWrite);
    
    // 绑定浏览
    document.getElementById('btnOvBrowse')?.addEventListener('click', ovBrowse);
    
    // 绑定状态刷新
    document.getElementById('btnOvRefreshStatus')?.addEventListener('click', ovRefreshStatus);
    
    // 初始加载状态
    ovRefreshStatus();
}

async function ovSearch() {
    const query = document.getElementById('ovSearchInput')?.value?.trim();
    if (!query) {
        showToast('请输入搜索关键词', 'warning');
        return;
    }
    
    const limit = parseInt(document.getElementById('ovSearchLimit')?.value || '10');
    const mode = document.getElementById('ovSearchMode')?.value || 'auto';
    const resultsEl = document.getElementById('ovSearchResults');
    
    resultsEl.innerHTML = '<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>搜索中...</p></div>';
    
    try {
        // 使用MCP协议搜索
        const sessionId = await ovInitMcp();
        const result = await ovMcpCall(sessionId, 'tools/call', {
            name: 'search',
            arguments: { query, limit, mode }
        });
        
        if (result && result.content) {
            const items = result.content;
            if (items.length === 0) {
                resultsEl.innerHTML = '<div class="empty-state"><i class="fas fa-search"></i><p>未找到相关记忆</p></div>';
                return;
            }
            
            resultsEl.innerHTML = items.map(item => `
                <div class="ov-result-item">
                    <div class="ov-result-header">
                        <span class="ov-result-uri">${item.uri || 'N/A'}</span>
                        <span class="ov-result-score">${item.score ? (item.score * 100).toFixed(1) + '%' : '-'}</span>
                    </div>
                    <div class="ov-result-content">${escapeHtml(item.content || item.text || '')}</div>
                    <div class="ov-result-meta">
                        ${item.tags ? item.tags.map(t => `<span class="tag">${t}</span>`).join('') : ''}
                    </div>
                </div>
            `).join('');
        } else {
            resultsEl.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>搜索返回格式异常</p></div>';
        }
    } catch (e) {
        resultsEl.innerHTML = `<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>搜索失败: ${escapeHtml(e.message)}</p></div>`;
    }
}

async function ovWrite() {
    const content = document.getElementById('ovWriteContent')?.value?.trim();
    if (!content) {
        showToast('请输入记忆内容', 'warning');
        return;
    }
    
    const tags = document.getElementById('ovWriteTags')?.value?.split(',').map(t => t.trim()).filter(Boolean) || [];
    const userId = document.getElementById('ovWriteUserId')?.value?.trim() || 'shared';
    const resultEl = document.getElementById('ovWriteResult');
    
    try {
        const sessionId = await ovInitMcp();
        const result = await ovMcpCall(sessionId, 'tools/call', {
            name: 'remember',
            arguments: { content, tags, user_id: userId }
        });
        
        resultEl.innerHTML = '<div class="ov-success"><i class="fas fa-check-circle"></i> 记忆保存成功</div>';
        document.getElementById('ovWriteContent').value = '';
        document.getElementById('ovWriteTags').value = '';
        showToast('记忆保存成功', 'success');
    } catch (e) {
        resultEl.innerHTML = `<div class="ov-error"><i class="fas fa-times-circle"></i> 保存失败: ${escapeHtml(e.message)}</div>`;
    }
}

async function ovBrowse() {
    const uri = document.getElementById('ovBrowseUri')?.value?.trim();
    if (!uri) {
        showToast('请输入URI路径', 'warning');
        return;
    }
    
    const resultsEl = document.getElementById('ovBrowseResults');
    resultsEl.innerHTML = '<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>加载中...</p></div>';
    
    try {
        const sessionId = await ovInitMcp();
        const result = await ovMcpCall(sessionId, 'tools/call', {
            name: 'read',
            arguments: { uri }
        });
        
        if (result && result.content) {
            const items = Array.isArray(result.content) ? result.content : [result.content];
            resultsEl.innerHTML = items.map(item => `
                <div class="ov-browse-item">
                    <div class="ov-browse-uri">${escapeHtml(item.uri || uri)}</div>
                    <div class="ov-browse-content"><pre>${escapeHtml(typeof item === 'string' ? item : JSON.stringify(item, null, 2))}</pre></div>
                </div>
            `).join('');
        } else {
            resultsEl.innerHTML = '<div class="empty-state"><i class="fas fa-folder-open"></i><p>目录为空或不存在</p></div>';
        }
    } catch (e) {
        resultsEl.innerHTML = `<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>加载失败: ${escapeHtml(e.message)}</p></div>`;
    }
}

async function ovRefreshStatus() {
    const healthEl = document.getElementById('ovStatusHealth');
    const versionEl = document.getElementById('ovStatusVersion');
    const authEl = document.getElementById('OVConfig');
    
    try {
        const resp = await fetch(`${OV_CONFIG.baseUrl}/health`, {
            headers: { 'x-api-key': OV_CONFIG.apiKey }
        });
        const data = await resp.json();
        
        if (data.status === 'ok') {
            healthEl.innerHTML = '<span class="status-ok"><i class="fas fa-check-circle"></i> 正常</span>';
            versionEl.textContent = data.version || '-';
            authEl.textContent = data.auth_mode || '-';
        } else {
            healthEl.innerHTML = '<span class="status-error"><i class="fas fa-times-circle"></i> 异常</span>';
        }
    } catch (e) {
        healthEl.innerHTML = '<span class="status-error"><i class="fas fa-times-circle"></i> 连接失败</span>';
        versionEl.textContent = '-';
        authEl.textContent = '-';
    }
}

// MCP 会话管理
let _ovMcpSessionId = null;

async function ovInitMcp() {
    if (_ovMcpSessionId) return _ovMcpSessionId;
    
    const resp = await fetch(`${OV_CONFIG.baseUrl}/mcp`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
            'X-OpenViking-Account': OV_CONFIG.account,
            'X-OpenViking-User': OV_CONFIG.user,
            'x-api-key': OV_CONFIG.apiKey
        },
        body: JSON.stringify({
            jsonrpc: '2.0',
            id: 1,
            method: 'initialize',
            params: {
                protocolVersion: '2024-11-05',
                capabilities: {},
                clientInfo: { name: 'fileapple-web', version: '1.0' }
            }
        })
    });
    
    _ovMcpSessionId = resp.headers.get('mcp-session-id');
    if (!_ovMcpSessionId) throw new Error('无法获取MCP会话ID');
    
    // 读取响应体
    await resp.text();
    
    return _ovMcpSessionId;
}

async function ovMcpCall(sessionId, method, params) {
    const resp = await fetch(`${OV_CONFIG.baseUrl}/mcp`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
            'X-OpenViking-Account': OV_CONFIG.account,
            'X-OpenViking-User': OV_CONFIG.user,
            'x-api-key': OV_CONFIG.apiKey,
            'mcp-session-id': sessionId
        },
        body: JSON.stringify({
            jsonrpc: '2.0',
            id: Date.now(),
            method,
            params
        })
    });
    
    const text = await resp.text();
    // 解析SSE格式响应
    const lines = text.split('\n');
    for (const line of lines) {
        if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            if (data.result) return data.result;
            if (data.error) throw new Error(data.error.message || JSON.stringify(data.error));
        }
    }
    throw new Error('无效的MCP响应');
}
