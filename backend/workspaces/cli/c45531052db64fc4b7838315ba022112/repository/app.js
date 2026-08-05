(function () {
  'use strict';

  const STORAGE_KEY = 'budget_transactions';

  function getTransactions() {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      return [];
    }
  }

  function saveTransactions(transactions) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(transactions));
  }

  function addTransaction(transaction) {
    const transactions = getTransactions();
    transactions.push(transaction);
    saveTransactions(transactions);
  }

  function deleteTransaction(id) {
    let transactions = getTransactions();
    transactions = transactions.filter(function (t) { return t.id !== id; });
    saveTransactions(transactions);
  }

  function calculateStats(transactions) {
    var totalIncome = 0;
    var totalExpense = 0;
    transactions.forEach(function (t) {
      if (t.type === 'income') {
        totalIncome += t.amount;
      } else {
        totalExpense += t.amount;
      }
    });
    return {
      totalIncome: totalIncome,
      totalExpense: totalExpense,
      balance: totalIncome - totalExpense
    };
  }

  function formatCurrency(amount) {
    var sign = amount < 0 ? '-' : '';
    var abs = Math.abs(amount);
    return sign + '¥' + abs.toFixed(2);
  }

  function formatDate(dateStr) {
    var d = new Date(dateStr + 'T00:00:00');
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 9);
  }

  var el = {
    form: document.getElementById('transactionForm'),
    type: document.getElementById('type'),
    amount: document.getElementById('amount'),
    category: document.getElementById('category'),
    date: document.getElementById('date'),
    note: document.getElementById('note'),
    balance: document.getElementById('balance'),
    totalIncome: document.getElementById('totalIncome'),
    totalExpense: document.getElementById('totalExpense'),
    transactionList: document.getElementById('transactionList'),
    filterType: document.getElementById('filterType')
  };

  el.date.value = new Date().toISOString().slice(0, 10);

  function updateUI() {
    var allTransactions = getTransactions();
    var filter = el.filterType.value;
    var filtered = allTransactions;
    if (filter === 'income') {
      filtered = allTransactions.filter(function (t) { return t.type === 'income'; });
    } else if (filter === 'expense') {
      filtered = allTransactions.filter(function (t) { return t.type === 'expense'; });
    }

    var stats = calculateStats(allTransactions);
    el.balance.textContent = formatCurrency(stats.balance);
    el.totalIncome.textContent = formatCurrency(stats.totalIncome);
    el.totalExpense.textContent = formatCurrency(stats.totalExpense);

    renderList(filtered);
  }

  function renderList(transactions) {
    if (transactions.length === 0) {
      el.transactionList.innerHTML = '<p class="empty-state">暂无交易记录，快去添加一条吧！</p>';
      return;
    }

    var html = '';
    transactions.slice().reverse().forEach(function (t) {
      var typeClass = t.type === 'income' ? 'tx-income' : 'tx-expense';
      var typeLabel = t.type === 'income' ? '收入' : '支出';
      var sign = t.type === 'income' ? '+' : '-';
      html += '<div class="transaction-item ' + typeClass + '">' +
        '<div class="tx-left">' +
          '<span class="tx-category">' + escapeHtml(t.category) + '</span>' +
          '<span class="tx-note">' + escapeHtml(t.note || '') + '</span>' +
          '<span class="tx-date">' + formatDate(t.date) + '</span>' +
        '</div>' +
        '<div class="tx-right">' +
          '<span class="tx-amount">' + sign + '¥' + t.amount.toFixed(2) + '</span>' +
          '<span class="tx-type-badge ' + typeClass + '">' + typeLabel + '</span>' +
          '<button class="btn-delete" data-id="' + t.id + '" title="删除">✕</button>' +
        '</div>' +
      '</div>';
    });

    el.transactionList.innerHTML = html;

    var deleteButtons = el.transactionList.querySelectorAll('.btn-delete');
    deleteButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        deleteTransaction(btn.dataset.id);
        updateUI();
      });
    });
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  el.form.addEventListener('submit', function (e) {
    e.preventDefault();

    var amount = parseFloat(el.amount.value);
    if (isNaN(amount) || amount <= 0) return;

    var transaction = {
      id: generateId(),
      type: el.type.value,
      amount: amount,
      category: el.category.value.trim(),
      date: el.date.value,
      note: el.note.value.trim()
    };

    addTransaction(transaction);
    el.form.reset();
    el.date.value = new Date().toISOString().slice(0, 10);
    updateUI();
  });

  el.filterType.addEventListener('change', function () {
    updateUI();
  });

  updateUI();
})();
