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

// ========== RAG 搜索功能 ==========

async function checkRAGHealth() {
    try {
        const data = await api('/api/rag/health');
        return data;
    } catch (e) {
        return { status: 'unavailable' };
    }
}

async function loadRAGDatasets() {
    try {
        const data = await api('/api/rag/datasets');
        return data.datasets || [];
    } catch (e) {
        return [];
    }
}

async function searchRAG(query, dataset = 'all') {
    const container = document.getElementById('ragSearchResults');
    container.innerHTML = '<div class="loading-state"><div class="spinner"></div><span>搜索中...</span></div>';

    try {
        const data = await api('/api/rag/search', {
            method: 'POST',
            body: JSON.stringify({ query, dataset, top_k: 10 })
        });

        const results = data.results || [];
        document.getElementById('ragSearchInfo').textContent = `找到 ${results.length} 条相关结果`;

        if (results.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-search"></i>
                    <p>未找到相关内容</p>
                </div>
            `;
            return;
        }

        container.innerHTML = results.map((r, i) => `
            <div class="rag-result-item" data-index="${i}">
                <div class="rag-result-header">
                    <span class="rag-result-score">${((r.similarity || 0.8) * 100).toFixed(1)}%</span>
                    <span class="rag-result-source">${r.source || '未知来源'}</span>
                </div>
                <div class="rag-result-content">${highlightText(r.content || r.text || '', query)}</div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>搜索失败: ${e.message}</p>
                <p class="upload-hint">请确保 RAGFlow 服务已启动</p>
            </div>
        `;
    }
}

function highlightText(text, query) {
    if (!query) return text;
    const regex = new RegExp(`(${query})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
}

// ========== RAG 对话功能 ==========

let ragChatHistory = [];

async function sendRAGChat(question, dataset = 'all') {
    const messagesContainer = document.getElementById('ragChatMessages');

    // 添加用户消息
    ragChatHistory.push({ role: 'user', content: question });
    renderRAGChatMessages();

    // 显示加载
    const loadingId = 'rag-loading-' + Date.now();
    messagesContainer.innerHTML += `
        <div class="rag-message rag-message-assistant" id="${loadingId}">
            <div class="spinner"></div>
            <span>思考中...</span>
        </div>
    `;
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    try {
        const data = await api('/api/rag/chat', {
            method: 'POST',
            body: JSON.stringify({ question, dataset })
        });

        // 移除加载状态
        document.getElementById(loadingId)?.remove();

        const answer = data.answer || data.data?.answer || '抱歉，暂无回答';
        ragChatHistory.push({ role: 'assistant', content: answer });
        renderRAGChatMessages();
    } catch (e) {
        document.getElementById(loadingId)?.remove();
        ragChatHistory.push({ role: 'assistant', content: '抱歉，服务暂不可用。' });
        renderRAGChatMessages();
    }
}

function renderRAGChatMessages() {
    const container = document.getElementById('ragChatMessages');
    container.innerHTML = ragChatHistory.map(m => `
        <div class="rag-message rag-message-${m.role}">
            <div class="rag-message-avatar">
                ${m.role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>'}
            </div>
            <div class="rag-message-content">${m.content}</div>
        </div>
    `).join('');
    container.scrollTop = container.scrollHeight;
}

// ========== RAG 模态框初始化 ==========

function initRAGSearch() {
    const searchBtn = document.getElementById('btnRagSearch');
    const searchInput = document.getElementById('ragSearchInput');

    searchBtn?.addEventListener('click', () => {
        const query = searchInput?.value?.trim();
        const dataset = document.getElementById('ragSearchDataset')?.value || 'all';
        if (query) searchRAG(query, dataset);
    });

    searchInput?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            searchBtn?.click();
        }
    });
}

function initRAGChat() {
    const sendBtn = document.getElementById('btnRagChat');
    const chatInput = document.getElementById('ragChatInput');

    sendBtn?.addEventListener('click', () => {
        const question = chatInput?.value?.trim();
        const dataset = document.getElementById('ragChatDataset')?.value || 'all';
        if (question) {
            sendRAGChat(question, dataset);
            chatInput.value = '';
        }
    });

    chatInput?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendBtn?.click();
        }
    });
}

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
        uploads: '上传记录',
        downloads: '下载目录',
        category: category || '分类',
        transcribe: '音频转写',
        knowledge: '知识导入',
        cloud: '云盘管理',
        settings: '设置'
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

    if (view === 'cloud') {
        openCloudModal();
    } else if (view === 'knowledge') {
        openKnowledgeModal();
    } else if (view === 'transcribe') {
        openModal('transcribeModal');
        initTranscribePanel();
    } else if (view === 'rag-search') {
        openModal('ragSearchModal');
        initRAGSearch();
    } else if (view === 'rag-chat') {
        openModal('ragChatModal');
        initRAGChat();
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

document.addEventListener('DOMContentLoaded', () => {
    // 初始化上传
    initUpload();

    // 加载数据
    loadFiles();

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
