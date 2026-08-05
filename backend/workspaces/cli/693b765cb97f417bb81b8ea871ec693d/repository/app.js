/* ===== BudgetLoop SPA - app.js ===== */

const STORAGE_KEY = 'budgetloop_entries';

const state = {
  entries: [],
  filterType: 'all',
  filterCategory: 'all',
};

/* ===== Persistence ===== */
function loadEntries() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveEntries() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.entries));
}

/* ===== Entry Model ===== */
function createEntry(description, amount, type, category) {
  return {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 8),
    description: description.trim(),
    amount: Math.round(parseFloat(amount) * 100) / 100,
    type,
    category,
    createdAt: new Date().toISOString(),
  };
}

/* ===== Computed Values ===== */
function getFilteredEntries() {
  let entries = state.entries;
  if (state.filterType !== 'all') {
    entries = entries.filter(e => e.type === state.filterType);
  }
  if (state.filterCategory !== 'all') {
    entries = entries.filter(e => e.category === state.filterCategory);
  }
  return entries.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
}

function getBalance() {
  const income = state.entries
    .filter(e => e.type === 'income')
    .reduce((sum, e) => sum + e.amount, 0);
  const expense = state.entries
    .filter(e => e.type === 'expense')
    .reduce((sum, e) => sum + e.amount, 0);
  return { income, expense, balance: income - expense };
}

function getCategoryStats() {
  const map = {};
  for (const e of state.entries) {
    if (!map[e.category]) {
      map[e.category] = { income: 0, expense: 0 };
    }
    map[e.category][e.type] += e.amount;
  }
  return map;
}

/* ===== Formatting ===== */
function formatCurrency(n) {
  return '¥' + n.toFixed(2);
}

/* ===== Rendering ===== */
function renderBalance() {
  const { income, expense, balance } = getBalance();
  document.getElementById('balance').textContent = formatCurrency(balance);
  document.getElementById('totalIncome').textContent = formatCurrency(income);
  document.getElementById('totalExpense').textContent = formatCurrency(expense);
}

function renderEntries() {
  const list = document.getElementById('entriesList');
  const filtered = getFilteredEntries();
  document.getElementById('entryCount').textContent = filtered.length;

  if (filtered.length === 0) {
    list.innerHTML = '<p class="empty-state">还没有记录，添加一条吧 ✨</p>';
    return;
  }

  list.innerHTML = filtered.map(e => `
    <div class="entry-item" data-id="${e.id}">
      <span class="entry-category cat-${e.type}">${esc(e.category)}</span>
      <span class="entry-desc">${esc(e.description)}</span>
      <span class="entry-amount amount-${e.type}">
        ${e.type === 'income' ? '+' : '-'}${formatCurrency(e.amount)}
      </span>
      <button class="btn btn-sm btn-danger" onclick="deleteEntry('${e.id}')" title="删除">
        ✕
      </button>
    </div>
  `).join('');
}

function renderStats() {
  const grid = document.getElementById('statsGrid');
  const stats = getCategoryStats();
  const categories = Object.keys(stats);

  if (categories.length === 0) {
    grid.innerHTML = '<p class="empty-state">暂无数据</p>';
    return;
  }

  grid.innerHTML = categories
    .sort((a, b) => {
      const totalA = stats[a].income + stats[a].expense;
      const totalB = stats[b].income + stats[b].expense;
      return totalB - totalA;
    })
    .map(cat => `
      <div class="stat-card">
        <span class="stat-name">${esc(cat)}</span>
        <div class="stat-values">
          ${stats[cat].income > 0
            ? `<span class="income-color">+${formatCurrency(stats[cat].income)}</span>`
            : ''}
          ${stats[cat].expense > 0
            ? `<span class="expense-color">-${formatCurrency(stats[cat].expense)}</span>`
            : ''}
        </div>
      </div>
    `).join('');
}

function renderCategoryFilter() {
  const select = document.getElementById('filterCategory');
  const stats = getCategoryStats();
  const categories = Object.keys(stats);

  select.innerHTML = '<option value="all">全部分类</option>' +
    categories.map(c => `<option value="${escAttr(c)}">${esc(c)}</option>`).join('');
  select.value = state.filterCategory;
}

function renderAll() {
  renderBalance();
  renderEntries();
  renderStats();
  renderCategoryFilter();
}

/* ===== Actions ===== */
function addEntry(entry) {
  state.entries.push(entry);
  saveEntries();
  renderAll();
}

function deleteEntry(id) {
  state.entries = state.entries.filter(e => e.id !== id);
  saveEntries();
  renderAll();
}

/* ===== Event Handlers ===== */
function handleSubmit(e) {
  e.preventDefault();

  const desc = document.getElementById('description').value;
  const amount = document.getElementById('amount').value;
  const type = document.getElementById('type').value;
  const category = document.getElementById('category').value;

  if (!desc || !amount || parseFloat(amount) <= 0) return;

  const entry = createEntry(desc, amount, type, category);
  addEntry(entry);

  e.target.reset();
  document.getElementById('type').value = 'expense';
  document.getElementById('category').value = '餐饮';
  document.getElementById('description').focus();
}

function handleFilterChange() {
  state.filterType = document.getElementById('filterType').value;
  state.filterCategory = document.getElementById('filterCategory').value;
  renderEntries();
  renderStats();
}

function esc(s) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(s).replace(/[&<>"']/g, c => map[c]);
}

function escAttr(s) {
  return String(s).replace(/"/g, '&quot;');
}

/* ===== Init ===== */
function init() {
  state.entries = loadEntries();

  document.getElementById('entryForm').addEventListener('submit', handleSubmit);
  document.getElementById('filterType').addEventListener('change', handleFilterChange);
  document.getElementById('filterCategory').addEventListener('change', handleFilterChange);

  // Expose deleteEntry globally for onclick handler
  window.deleteEntry = deleteEntry;

  renderAll();
}

document.addEventListener('DOMContentLoaded', init);
