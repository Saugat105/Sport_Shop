/* ═══════════════════════════════════════════════════════════════
   SPORT SHOP NEPAL — main.js
   Global utilities used across all pages
════════════════════════════════════════════════════════════════ */

// ── CSRF Helper ───────────────────────────────────────────────
function getCsrfToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]')?.value
    || document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='))?.split('=')[1]
    || '';
}

// ── API Fetch Helper ──────────────────────────────────────────
async function apiPost(url, data) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(data),
  });
  return res.json();
}

// ── Format Currency ───────────────────────────────────────────
function formatNPR(amount) {
  return 'Rs. ' + Number(amount).toLocaleString('en-NP');
}

// ── Sidebar Toggle ────────────────────────────────────────────
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const main    = document.querySelector('.main-content');
  if (window.innerWidth <= 768) {
    sidebar.classList.toggle('mobile-open');
  } else {
    sidebar.classList.toggle('collapsed');
    main.classList.toggle('sidebar-collapsed');
  }
}

// Close sidebar on mobile when clicking outside
document.addEventListener('click', function (e) {
  if (window.innerWidth <= 768) {
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebarToggle');
    if (sidebar && !sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
      sidebar.classList.remove('mobile-open');
    }
  }
});

// ── Confirm Delete ────────────────────────────────────────────
function confirmDelete(formId, productName) {
  if (confirm(`Are you sure you want to delete "${productName}"?\n\nThis action cannot be undone.`)) {
    document.getElementById(formId).submit();
  }
}

// ── Stock Badge Helper ────────────────────────────────────────
function stockBadge(qty, threshold) {
  if (qty === 0) return `<span class="badge-pill badge-danger"><i class="bi bi-x-circle-fill"></i> Out of Stock</span>`;
  if (qty <= threshold) return `<span class="badge-pill badge-warning"><i class="bi bi-exclamation-triangle-fill"></i> Low (${qty})</span>`;
  return `<span class="badge-pill badge-success"><i class="bi bi-check-circle-fill"></i> ${qty} units</span>`;
}

// ── Search Filter (client-side) ───────────────────────────────
function setupTableSearch(inputId, tableId) {
  const input = document.getElementById(inputId);
  if (!input) return;

  input.addEventListener('input', function () {
    const q = this.value.toLowerCase().trim();
    const rows = document.querySelectorAll(`#${tableId} tbody tr`);

    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = !q || text.includes(q) ? '' : 'none';
    });
  });
}

// ── Modal Helpers ─────────────────────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
  document.body.style.overflow = '';
}

// Close on overlay click
document.addEventListener('click', function (e) {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
    document.body.style.overflow = '';
  }
});

// Close on Escape key
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(m => {
      m.classList.remove('open');
      document.body.style.overflow = '';
    });
  }
});

// ── Toast Notification ─────────────────────────────────────────
function showToast(message, type = 'success') {
  const icons = { success: 'bi-check-circle-fill', error: 'bi-x-circle-fill', warning: 'bi-exclamation-triangle-fill' };
  const toast = document.createElement('div');
  toast.className = `flash flash-${type}`;
  toast.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;min-width:280px;animation:slideUp 0.3s ease;';
  toast.innerHTML = `<i class="bi ${icons[type] || icons.success}"></i><span>${message}</span><button onclick="this.parentElement.remove()"><i class="bi bi-x"></i></button>`;

  const style = document.createElement('style');
  style.textContent = '@keyframes slideUp{from{transform:translateY(16px);opacity:0}to{transform:translateY(0);opacity:1}}';
  document.head.appendChild(style);
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 400); }, 4000);
}