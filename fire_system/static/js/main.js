let socket = null;

document.addEventListener('DOMContentLoaded', function() {
    socket = io({
        transports: ['websocket', 'polling']
    });

    socket.on('connect', function() {
        console.log('Socket connected');
    });

    socket.on('new_incident', function(data) {
        showNotification(`Ново произшествие: ${data.code} - ${data.type}`, 'warning');
    });

    socket.on('incident_update', function(data) {
        showNotification(`Произшествие ${data.code}: статус ${data.status}`, 'info');
    });

    socket.on('sos_alert', function(data) {
        showNotification(`SOS сигнал от ${data.employee}!`, 'danger');
    });

    socket.on('sos_resolved', function(data) {
        showNotification('SOS сигналът е разрешен', 'success');
    });

    socket.on('new_task', function(data) {
        showNotification(`Нова задача: ${data.title}`, 'info');
    });

    socket.on('chat_message', function(data) {
        const container = document.getElementById('chatMessages');
        if (!container) return;
        let own = data.sender_id === (window.currentUserId || -1);
        let div = document.createElement('div');
        div.className = 'chat-message' + (own ? ' chat-message-own' : '');
        let html = `<div class="msg-sender">${data.sender}</div>`;
        if (data.image_url) html += `<img src="${data.image_url}" class="msg-image" alt="Image">`;
        if (data.content) html += `<div class="msg-content">${data.content}</div>`;
        html += `<div class="msg-time">${new Date(data.created_at).toLocaleTimeString('bg-BG', {hour:'2-digit', minute:'2-digit'})}</div>`;
        div.innerHTML = html;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    });

    socket.on('video_call_started', function(data) {
        showNotification(`Видео връзка от ${data.initiator}`, 'info');
    });
});

function showNotification(message, type) {
    type = type || 'info';
    const area = document.getElementById('notification-area');
    if (!area) return;

    const notif = document.createElement('div');
    notif.className = `notification ${type}`;
    notif.textContent = message;
    area.appendChild(notif);

    setTimeout(function() {
        notif.style.opacity = '0';
        notif.style.transform = 'translateX(100%)';
        notif.style.transition = 'all 0.3s ease';
        setTimeout(function() { notif.remove(); }, 300);
    }, 5000);
}

function toast(message, type) {
    showNotification(message, type);
}

function toggleNav() {
    document.querySelector('.nav-menu').classList.toggle('open');
}

document.addEventListener('click', function(e) {
    if (e.target.closest('.alert-dismissible .close')) {
        e.target.closest('.alert').style.display = 'none';
    }
});

window.addEventListener('load', function() {
    if (window.Leaflet) {
        L.Icon.Default.imagePath = 'https://unpkg.com/leaflet@1.9.4/dist/images/';
    }
});
