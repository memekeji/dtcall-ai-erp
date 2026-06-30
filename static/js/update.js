/**
 * DTCall Online Update System - Frontend
 *
 * Features:
 * - Check for updates with one click (admin only)
 * - Execute update with progress feedback (admin only)
 * - Rollback to previous version (admin only)
 * - Changelog modal with commit history
 * - Auto-refresh after update
 */

(function () {
  'use strict';

  var STATE = {
    currentVersion: '',
    currentCommit: '',
    updateAvailable: false,
    latestVersion: '',
    canRollback: false,
    changelog: [],
    checkedAt: '',
  };

  var CHECKING = false;
  var UPDATING = false;

  var $btnCheckUpdate = null;
  var $btnUpdateNow = null;
  var $btnRollback = null;
  var $versionActions = null;
  var $currentVersion = null;
  var $currentCommit = null;
  var $versionStatus = null;
  var $versionStatusText = null;
  var $versionStatusLink = null;

  // =====================================================================
  // Initialization
  // =====================================================================
  function init() {
    $btnCheckUpdate = document.getElementById('btnCheckUpdate');
    $btnUpdateNow = document.getElementById('btnUpdateNow');
    $btnRollback = document.getElementById('btnRollback');
    $versionActions = document.getElementById('versionActions');
    $currentVersion = document.getElementById('currentVersion');
    $currentCommit = document.getElementById('currentCommit');
    $versionStatus = document.getElementById('versionStatus');
    $versionStatusText = document.getElementById('versionStatusText');
    $versionStatusLink = document.getElementById('versionStatusLink');

    // Admin-only controls: only show if buttons exist (template controls visibility)
    if ($btnCheckUpdate && $versionActions) {
      $versionActions.style.display = 'flex';
      $btnCheckUpdate.addEventListener('click', checkUpdate);
      if ($btnUpdateNow) $btnUpdateNow.addEventListener('click', confirmUpdate);
      if ($btnRollback) $btnRollback.addEventListener('click', confirmRollback);

      // Silent check on load
      setTimeout(checkUpdateSilent, 3000);
    }
  }

  // =====================================================================
  // API helpers
  // =====================================================================
  function apiGet(url) {
    return fetch(url, {
      method: 'GET',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  function apiPost(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCsrfToken(),
      },
      credentials: 'same-origin',
      body: body ? JSON.stringify(body) : '{}',
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  function getCsrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  // =====================================================================
  // Update UI
  // =====================================================================
  function updateUI(data) {
    STATE.currentVersion = data.current_version || '';
    STATE.currentCommit = data.current_commit || '';
    STATE.updateAvailable = !!data.update_available;
    STATE.latestVersion = data.latest_version || '';
    STATE.canRollback = !!data.can_rollback;
    STATE.changelog = data.changelog || [];
    STATE.checkedAt = data.checked_at || '';

    if ($currentVersion) {
      $currentVersion.textContent = 'v' + STATE.currentVersion;
    }
    if ($currentCommit) {
      $currentCommit.textContent = STATE.currentCommit;
      $currentCommit.title = '提交 ' + STATE.currentCommit;
    }

    // Update status
    if (!$versionStatusText) return;

    if (STATE.updateAvailable) {
      $versionStatusText.textContent = '可更新至 v' + STATE.latestVersion;
      $versionStatusText.classList.add('has-update');
      $versionStatus.classList.add('has-update');

      if ($btnUpdateNow) {
        $btnUpdateNow.style.display = 'inline-flex';
        $btnUpdateNow.classList.add('has-update');
      }
      // Make status clickable if link exists
      if ($versionStatusLink) {
        $versionStatusLink.title = '点击查看 ' + STATE.changelog.length + ' 条更新记录';
        $versionStatusLink.style.display = '';
      }
    } else {
      $versionStatusText.textContent = '已是最新';
      $versionStatusText.classList.remove('has-update');
      $versionStatus.classList.remove('has-update');

      if ($btnUpdateNow) {
        $btnUpdateNow.style.display = 'none';
        $btnUpdateNow.classList.remove('has-update');
      }
      if ($versionStatusLink) {
        $versionStatusLink.style.display = 'none';
      }
    }

    if ($btnRollback) {
      $btnRollback.style.display = STATE.canRollback ? 'inline-flex' : 'none';
    }
  }

  function setStatus(text, isError) {
    if (!$versionStatusText) return;
    $versionStatusText.textContent = text;
    $versionStatus.classList.toggle('has-update', false);
    if (isError) {
      $versionStatusText.style.color = '#f04438';
      setTimeout(function () { $versionStatusText.style.color = ''; }, 5000);
    }
  }

  // =====================================================================
  // Check for updates
  // =====================================================================
  function checkUpdateSilent() {
    apiGet('/system/version/info/').then(function (res) {
      if (res.success) updateUI(res.data);
    }).catch(function () {});
  }

  function checkUpdate() {
    if (CHECKING) return;
    CHECKING = true;
    $btnCheckUpdate.classList.add('checking');
    setStatus('检查中...');

    apiGet('/system/version/info/').then(function (res) {
      CHECKING = false;
      $btnCheckUpdate.classList.remove('checking');
      if (res.success) {
        updateUI(res.data);
      } else {
        setStatus('检查失败', true);
      }
    }).catch(function (err) {
      CHECKING = false;
      $btnCheckUpdate.classList.remove('checking');
      setStatus('检查失败: ' + err.message, true);
    });
  }

  // =====================================================================
  // Changelog Modal
  // =====================================================================
  window.showChangelogModal = function () {
    var overlay = document.getElementById('changelogOverlay');
    if (!overlay) return;

    // If we need fresh data, fetch first
    if (STATE.changelog.length === 0) {
      apiGet('/system/version/info/').then(function (res) {
        if (res.success) {
          STATE.changelog = res.data.changelog || [];
          STATE.latestVersion = res.data.latest_version || '';
        }
        renderChangelog();
        overlay.style.display = 'flex';
      }).catch(function () {
        overlay.style.display = 'flex';
      });
    } else {
      renderChangelog();
      overlay.style.display = 'flex';
    }
  };

  window.hideChangelogModal = function () {
    var overlay = document.getElementById('changelogOverlay');
    if (overlay) overlay.style.display = 'none';
  };

  function renderChangelog() {
    var tag = document.getElementById('changelogVersionTag');
    var body = document.getElementById('changelogBody');
    var updateBtn = document.getElementById('changelogUpdateBtn');

    if (tag) {
      tag.textContent = STATE.latestVersion ? 'v' + STATE.latestVersion : 'v' + STATE.currentVersion;
    }

    if (updateBtn) {
      updateBtn.style.display = STATE.updateAvailable ? '' : 'none';
    }

    if (!body) return;

    if (!STATE.changelog || STATE.changelog.length === 0) {
      body.innerHTML = '<div class="changelog-empty">暂无更新记录</div>';
      return;
    }

    var html = '<ul class="changelog-list">';
    STATE.changelog.forEach(function (line, i) {
      // Split git log --oneline: "abc1234 message"
      var parts = (line || '').split(' ');
      var hash = parts[0] || '';
      var msg = parts.slice(1).join(' ') || line;
      var isNew = i < 3 ? ' changelog-item-new' : '';
      html += '<li class="changelog-item' + isNew + '">';
      html += '<span class="changelog-hash">' + escapeHtml(hash) + '</span>';
      html += '<span class="changelog-msg">' + escapeHtml(msg) + '</span>';
      html += '</li>';
    });
    html += '</ul>';
    body.innerHTML = html;
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Click overlay background to close
  document.addEventListener('click', function (e) {
    if (e.target && e.target.id === 'changelogOverlay') {
      hideChangelogModal();
    }
  });

  // =====================================================================
  // Confirm & execute update
  // =====================================================================
  function confirmUpdate() {
    var msg = '确认更新到 v' + STATE.latestVersion + '？\n\n';
    msg += '更新前会自动备份数据库，更新过程中系统可能短暂不可用。\n';
    msg += '确认继续？';
    if (!confirm(msg)) return;
    executeUpdate();
  }

  window.confirmUpdateFromChangelog = function () {
    hideChangelogModal();
    setTimeout(confirmUpdate, 300);
  };

  function executeUpdate() {
    if (UPDATING) return;
    UPDATING = true;

    showProgressOverlay('正在准备更新...', '步骤 1/4：备份数据库');

    apiPost('/system/version/backup/').then(function (res) {
      if (!res.success) throw new Error('备份失败: ' + (res.error || '未知错误'));
      updateProgress('步骤 2/4：拉取最新代码', 25);
      return apiPost('/system/version/update/', { target_version: STATE.latestVersion });
    }).then(function (res) {
      if (res.success) {
        updateProgress('更新完成！', 100);
        if (typeof layer !== 'undefined') {
          layer.msg('更新成功！系统将在3秒后刷新。', { icon: 1, time: 3000 }, function () {
            window.location.reload(true);
          });
        }
        setTimeout(function () { window.location.reload(true); }, 3000);
      } else {
        throw new Error('更新失败: ' + (res.error || '未知错误'));
      }
    }).catch(function (err) {
      UPDATING = false;
      hideProgressOverlay();
      setStatus(err.message, true);
      if (typeof layer !== 'undefined') {
        layer.msg(err.message, { icon: 2, time: 5000 });
      } else {
        alert(err.message);
      }
    });
  }

  // =====================================================================
  // Rollback
  // =====================================================================
  function confirmRollback() {
    var msg = '确认回滚到上一个版本？\n\n';
    msg += '回滚会恢复更新前的代码和数据迁移状态。\n';
    msg += '确认继续？';
    if (!confirm(msg)) return;
    executeRollback();
  }

  function executeRollback() {
    if (UPDATING) return;
    UPDATING = true;

    showProgressOverlay('正在回滚...', '恢复到更新前的版本');

    apiPost('/system/version/rollback/').then(function (res) {
      if (res.success) {
        updateProgress('回滚完成！', 100);
        if (typeof layer !== 'undefined') {
          layer.msg('回滚成功！系统将在3秒后刷新。', { icon: 1, time: 3000 }, function () {
            window.location.reload(true);
          });
        }
        setTimeout(function () { window.location.reload(true); }, 3000);
      } else {
        throw new Error('回滚失败: ' + (res.error || '未知错误'));
      }
    }).catch(function (err) {
      UPDATING = false;
      hideProgressOverlay();
      setStatus(err.message, true);
      if (typeof layer !== 'undefined') {
        layer.msg(err.message, { icon: 2, time: 5000 });
      } else {
        alert(err.message);
      }
    });
  }

  // =====================================================================
  // Progress overlay
  // =====================================================================
  function showProgressOverlay(title, step) {
    var overlay = document.createElement('div');
    overlay.className = 'update-progress-overlay';
    overlay.id = 'updateProgressOverlay';
    overlay.innerHTML =
      '<div class="update-progress-card">' +
      '<h3>' + escapeHtml(title) + '</h3>' +
      '<p class="update-step">' + escapeHtml(step) + '</p>' +
      '<div class="layui-progress layui-progress-big" lay-showpercent="true" lay-filter="updateProgress">' +
      '<div class="layui-progress-bar" lay-percent="0%"></div>' +
      '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    if (typeof layui !== 'undefined' && layui.element) {
      layui.element.init();
    }
  }

  function updateProgress(step, percent) {
    var stepEl = document.querySelector('.update-step');
    if (stepEl) stepEl.textContent = step;
    if (typeof layui !== 'undefined' && layui.element) {
      layui.element.progress('updateProgress', percent + '%');
    }
  }

  function hideProgressOverlay() {
    var overlay = document.getElementById('updateProgressOverlay');
    if (overlay) overlay.remove();
  }

  // =====================================================================
  // Start
  // =====================================================================
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
