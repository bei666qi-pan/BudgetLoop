(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────────────
  const STORAGE_KEY = 'budget_tracker_transactions';
  let transactions = [];

  // ── DOM refs ──────────────────────────────────────────────────────
  const form = document.getElementById('transactionForm');
  const typeSelect = document.getElementById('type');
  const amountInput = document.getElementById('amount');
  const categorySelect = document.getElementById('category');
  const dateInput = document.getElementById('date');
  const noteInput = document.getElementById('note');
  const transactionList = document.getElementById('transactionList');
  const balanceEl = document.getElementById('balance');
  const totalIncomeEl = document.getElementById('totalIncome');
  const totalExpenseEl = document.getElementById('totalExpense');

  // ── Helpers ───────────────────────────────────────────────────────
  function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substring(2, 9);
  }

  function formatCurrency(amount) {
    const abs = Math.abs(amount);
    const sign = amount < 0 ? '-' : '';
    return sign + '¥' + abs.toFixed(2);
  }

  function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr + 'T00:00:00');
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  // ── Persistence ───────────────────────────────────────────────────
  function loadFromStorage() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        transactions = Array.isArray(parsed) ? parsed : [];
      }
    } catch (e) {
      transactions = [];
    }
  }

  function saveToStorage() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(transactions));
    } catch (e) {
      // Silently ignore (quota exceeded, private browsing, etc.)
    }
  }

  // ── Calculations ──────────────────────────────────────────────────
  function calcTotalIncome() {
    return transactions
      .filter(function (t) { return t.type === 'income'; })
      .reduce(function (sum, t) { return sum + t.amount; }, 0);
  }

  function calcTotalExpense() {
    return transactions
      .filter(function (t) { return t.type === 'expense'; })
      .reduce(function (sum, t) { return sum + t.amount; }, 0);
  }

  function calcBalance() {
    return calcTotalIncome() - calcTotalExpense();
  }

  // ── Actions ───────────────────────────────────────────────────────
  function addTransaction(transaction) {
    transactions.push(transaction);
    saveToStorage();
    updateUI();
  }

  function deleteTransaction(id) {
    transactions = transactions.filter(function (t) { return t.id !== id; });
    saveToStorage();
    updateUI();
  }

  // ── Form handler ──────────────────────────────────────────────────
  function handleSubmit(e) {
    e.preventDefault();

    var amount = parseFloat(amountInput.value);
    if (isNaN(amount) || amount <= 0) {
      amountInput.focus();
      return;
    }

    var transaction = {
      id: generateId(),
      type: typeSelect.value,
      amount: amount,
      category: categorySelect.value,
      date: dateInput.value,
      note: noteInput.value.trim() || ''
    };

    addTransaction(transaction);

    // Reset form
    form.reset();
    dateInput.value = new Date().toISOString().split('T')[0];
    amountInput.focus();
  }

  function handleDeleteClick(e) {
    var btn = e.target.closest('.btn-delete');
    if (!btn) return;

    var id = btn.getAttribute('data-id');
    if (id) {
      deleteTransaction(id);
    }
  }

  // ── Rendering ─────────────────────────────────────────────────────
  function renderTransactionList() {
    if (transactions.length === 0) {
      transactionList.innerHTML = '<p class="empty-message">暂无交易记录</p>';
      return;
    }

    // Sort newest first
    var sorted = transactions.slice().sort(function (a, b) {
      return new Date(b.date) - new Date(a.date) || (b.id > a.id ? 1 : -1);
    });

    var html = '';
    sorted.forEach(function (t) {
      var typeClass = t.type === 'income' ? 'tx-income' : 'tx-expense';
      var typeLabel = t.type === 'income' ? '收入' : '支出';
      var amountPrefix = t.type === 'income' ? '+' : '-';
      var amountFormatted = formatCurrency(t.amount);

      html +=
        '<div class="transaction-item ' + typeClass + '">' +
          '<div class="tx-info">' +
            '<span class="tx-category">' + escapeHtml(t.category) + '</span>' +
            '<span class="tx-note">' + escapeHtml(t.note) + '</span>' +
            '<span class="tx-date">' + formatDate(t.date) + '</span>' +
          '</div>' +
          '<div class="tx-right">' +
            '<span class="tx-amount">' + amountPrefix + amountFormatted + '</span>' +
            '<span class="tx-type-badge">' + typeLabel + '</span>' +
            '<button class="btn-delete" data-id="' + t.id + '" title="删除">✕</button>' +
          '</div>' +
        '</div>';
    });

    transactionList.innerHTML = html;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function updateSummary() {
    var income = calcTotalIncome();
    var expense = calcTotalExpense();
    var balance = calcBalance();

    totalIncomeEl.textContent = formatCurrency(income);
    totalExpenseEl.textContent = formatCurrency(expense);
    balanceEl.textContent = formatCurrency(balance);

    // Color the balance
    balanceEl.classList.remove('positive', 'negative');
    if (balance > 0) {
      balanceEl.classList.add('positive');
    } else if (balance < 0) {
      balanceEl.classList.add('negative');
    }
  }

  function updateUI() {
    renderTransactionList();
    updateSummary();
  }

  // ── Init ──────────────────────────────────────────────────────────
  function init() {
    loadFromStorage();

    // Set today as default date
    dateInput.value = new Date().toISOString().split('T')[0];

    // Bind events
    form.addEventListener('submit', handleSubmit);
    transactionList.addEventListener('click', handleDeleteClick);

    // Initial render
    updateUI();
  }

  init();
})();
