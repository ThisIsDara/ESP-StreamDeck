const ACTIONS = {
    'PLAY_PAUSE':  { label: 'Play/Pause',         icon: '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>' },
    'NEXT_TRACK':  { label: 'Next Track',          icon: '<svg viewBox="0 0 24 24"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>' },
    'PREV_TRACK':  { label: 'Previous Track',      icon: '<svg viewBox="0 0 24 24"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>' },
    'VOL_UP':      { label: 'Volume Up',           icon: '<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>' },
    'VOL_DOWN':    { label: 'Volume Down',         icon: '<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/></svg>' },
    'MUTE':        { label: 'Mute',                icon: '<svg viewBox="0 0 24 24"><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/></svg>' },
    'KEY_COMBO':   { label: 'Keyboard Shortcut',   icon: '<svg viewBox="0 0 24 24"><path d="M20 5H4c-1.1 0-1.99.9-1.99 2L2 17c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm-9 3h2v2h-2V8zm0 3h2v2h-2v-2zM8 8h2v2H8V8zm0 3h2v2H8v-2zm-1 2H5v-2h2v2zm0-3H5V8h2v2zm9 7H8v-2h8v2zm0-4h-2v-2h2v2zm0-3h-2V8h2v2zm3 3h-2v-2h2v2zm0-3h-2V8h2v2z"/></svg>' },
    'OPEN_APP':    { label: 'Launch App',          icon: '<svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM5 19V5h6v14H5zm14 0h-6v-7h6v7zm0-9h-6V5h6v5z"/></svg>' },
    'TYPE_TEXT':    { label: 'Type Text',           icon: '<svg viewBox="0 0 24 24"><path d="M2.5 4v3h5v12h3V7h5V4h-13zm19 5h-9v3h3v7h3v-7h3V9z"/></svg>' },
};

const ACTION_KEYS = Object.keys(ACTIONS);

let buttons = [];
let ws = null;
let wsReconnectTimer = null;

function toast(msg) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(el._hide);
    el._hide = setTimeout(() => el.classList.remove('show'), 2000);
}

function setOnline(online) {
    const dot = document.getElementById('status-dot');
    if (dot) dot.classList.toggle('online', online);
}

function connectWS() {
    if (ws && ws.readyState === WebSocket.OPEN) return;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws`);
    ws.onopen = () => {
        setOnline(true);
        wsReconnectTimer = null;
    };
    ws.onclose = () => {
        setOnline(false);
        if (!wsReconnectTimer) {
            wsReconnectTimer = setTimeout(connectWS, 3000);
        }
    };
    ws.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.buttons) {
                buttons = data.buttons;
                renderGrid();
            }
        } catch {}
    };
}

function sendPress(id) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'press', id: id }));
    } else {
        fetch('/api/press?id=' + id).catch(() => {});
    }
}

function setupVolumeSlider() {
    const slider = document.getElementById('vol-slider');
    const label = document.getElementById('vol-label');
    if (!slider) return;
    let timeout = null;
    slider.addEventListener('input', () => {
        label.textContent = slider.value + '%';
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            const val = parseInt(slider.value);
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'set_volume', value: val }));
            }
        }, 30);
    });
}

function renderGrid() {
    const grid = document.getElementById('grid');
    if (!grid) return;
    grid.innerHTML = '';
    buttons.forEach((b, idx) => {
        const el = document.createElement('button');
        el.className = 'btn';
        el.style.background = b.color || '#333';
        const icon = ACTIONS[b.action] ? ACTIONS[b.action].icon : '';
        const label = b.label || (ACTIONS[b.action] ? ACTIONS[b.action].label : b.action);
        el.innerHTML = `<div class="icon">${icon}</div><div class="label">${label}</div>`;

        let holdTimer = null;
        let repeatTimer = null;

        function sendPress_() { sendPress(b.id); }

        el.addEventListener('pointerdown', (e) => {
            e.preventDefault();
            el.classList.add('pressed');
            sendPress_();
            holdTimer = setTimeout(() => {
                repeatTimer = setInterval(sendPress_, 80);
            }, 350);
        });

        el.addEventListener('pointerup', () => {
            el.classList.remove('pressed');
            clearTimeout(holdTimer);
            clearInterval(repeatTimer);
        });

        el.addEventListener('pointerleave', () => {
            el.classList.remove('pressed');
            clearTimeout(holdTimer);
            clearInterval(repeatTimer);
        });

        grid.appendChild(el);
    });
}

function openConfig() {
    document.getElementById('config-overlay').classList.remove('hidden');
    renderConfig();
}

function closeConfig(e) {
    if (e && e.target !== e.currentTarget) return;
    document.getElementById('config-overlay').classList.add('hidden');
}

function renderConfig() {
    const list = document.getElementById('config-list');
    if (!list) return;
    list.innerHTML = '';
    const previews = list.querySelectorAll('.preview');

    buttons.forEach((b, i) => {
        const card = document.createElement('div');
        card.className = 'config-card';
        const needsValue = b.action === 'KEY_COMBO' || b.action === 'OPEN_APP' || b.action === 'TYPE_TEXT';
        const valuePlaceholder = b.action === 'KEY_COMBO' ? 'e.g. Ctrl+Shift+S' :
                                 b.action === 'OPEN_APP' ? 'e.g. notepad.exe' :
                                 'e.g. Hello world';

        card.innerHTML = `
            <div class="row">
                <div class="preview" style="background:${b.color || '#555'}"></div>
                <div class="field-group">
                    <label>Label</label>
                    <input type="text" class="cfg-label" value="${escHtml(b.label || '')}" placeholder="Button label">
                </div>
                <button class="del-btn" onclick="deleteButton(${i})" title="Delete">✕</button>
            </div>
            <div class="row">
                <div class="field-group">
                    <label>Action</label>
                    <select class="cfg-action" onchange="onActionChange(this)">
                        ${ACTION_KEYS.map(k =>
                            `<option value="${k}" ${k === b.action ? 'selected' : ''}>${ACTIONS[k].label}</option>`
                        ).join('')}
                    </select>
                </div>
                <div>
                    <label>Color</label>
                    <input type="color" class="cfg-color" value="${b.color || '#555'}">
                </div>
            </div>
            <div class="row extra-field ${needsValue ? 'show' : ''}">
                <div class="field-group">
                    <label>${b.action === 'KEY_COMBO' ? 'Shortcut' : b.action === 'OPEN_APP' ? 'App Path' : 'Text'}</label>
                    <input type="text" class="cfg-value" value="${escHtml(b.value || '')}" placeholder="${valuePlaceholder}">
                </div>
            </div>
        `;
        list.appendChild(card);
    });
}

function onActionChange(select) {
    const card = select.closest('.config-card');
    const extra = card.querySelector('.extra-field');
    const action = select.value;
    const needsValue = action === 'KEY_COMBO' || action === 'OPEN_APP' || action === 'TYPE_TEXT';
    extra.classList.toggle('show', needsValue);
    const input = extra.querySelector('.cfg-value');
    if (input) {
        input.placeholder = action === 'KEY_COMBO' ? 'e.g. Ctrl+Shift+S' :
                            action === 'OPEN_APP' ? 'e.g. notepad.exe' : 'e.g. Hello world';
    }
}

function escHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function collectConfig() {
    const cards = document.querySelectorAll('.config-card');
    return Array.from(cards).map((card, i) => {
        const label = card.querySelector('.cfg-label').value.trim();
        const action = card.querySelector('.cfg-action').value;
        const color = card.querySelector('.cfg-color').value;
        const valueInput = card.querySelector('.cfg-value');
        const value = valueInput ? valueInput.value.trim() : '';
        return {
            id: i,
            label: label || ACTIONS[action].label,
            action: action,
            value: value,
            color: color
        };
    });
}

function addButton() {
    const list = collectConfig();
    list.push({
        id: list.length,
        label: 'New Button',
        action: 'PLAY_PAUSE',
        value: '',
        color: '#5b6ef5'
    });
    renderTempConfig(list);
}

function deleteButton(idx) {
    const list = collectConfig();
    list.splice(idx, 1);
    list.forEach((b, i) => b.id = i);
    renderTempConfig(list);
}

function renderTempConfig(list) {
    buttons = list;
    renderConfig();
}

function saveConfig() {
    const list = collectConfig();
    const data = { buttons: list };
    const status = document.getElementById('config-status');
    if (status) status.classList.remove('show');

    wsSend({ type: 'save', buttons: list });

    fetch('/api/buttons', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(res => {
        if (res.ok) {
            buttons = list;
            renderGrid();
            if (status) {
                status.textContent = '✓ Saved';
                status.classList.add('show');
                setTimeout(() => status.classList.remove('show'), 2000);
            }
            toast('Config saved');
        }
    }).catch(() => {
        toast('Save failed');
    });
}

function restartESP() {
    if (confirm('Restart the ESP32?')) {
        fetch('/api/restart', { method: 'POST' }).catch(() => {});
        toast('Restarting...');
        setTimeout(() => {
            document.getElementById('config-overlay').classList.add('hidden');
        }, 500);
    }
}

async function loadButtons() {
    try {
        const res = await fetch('/api/buttons');
        const data = await res.json();
        buttons = data.buttons || [];
    } catch {
        buttons = [];
    }
    renderGrid();
}

document.addEventListener('DOMContentLoaded', () => {
    loadButtons();
    connectWS();
    setupVolumeSlider();
});
