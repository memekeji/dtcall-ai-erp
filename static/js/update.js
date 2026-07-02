/**
 * DTCall Official Update Center Frontend
 *
 * Features:
 * - Admin-only update controls
 * - Check updates from https://www.dtcall.cn official update center
 * - Show release highlights and release notes
 * - Online update execution
 * - Offline ZIP import fallback
 * - Rollback support
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
    release: null,
    releaseNotes: '',
    source: '',
    channel: '',
    platform: '',
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

    if ($btnCheckUpdate && $versionActions) {
      if (document.body && document.body.dataset && document.body.dataset.updateManageable === 'false') {
        if ($btnUpdateNow) $btnUpdateNow.style.display = 'none';
        if ($btnRollback) $btnRollback.style.display = 'none';
      }
      $versionActions.style.display = 'flex';
      $btnCheckUpdate.addEventListener('click', checkUpdate);
      if ($btnUpdateNow && isUpdateManageable()) $btnUpdateNow.addEventListener('click', confirmUpdate);
      if ($btnRollback && isUpdateManageable()) $btnRollback.addEventListener('click', confirmRollback);
      if (isUpdateManageable()) injectOfflineImportButton();
      setTimeout(checkUpdateSilent, 2000);
    }
  }

  function isUpdateManageable() {
    return !!(document.body && document.body.dataset && document.body.dataset.updateManageable !== 'false');
  }

  function apiGet(url) {
    return fetch(url, {
      method: 'GET',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    }).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok) throw new Error((data && (data.error || data.message)) || ('HTTP ' + r.status));
        return data;
      });
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
      return r.json().then(function (data) {
        if (!r.ok) throw new Error((data && (data.error || data.message)) || ('HTTP ' + r.status));
        return data;
      });
    });
  }

  function getCsrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function injectOfflineImportButton() {
    if (!document.getElementById('btnImportOfflinePackage') && $versionActions) {
      var btn = document.createElement('button');
      btn.className = 'version-btn version-btn-check';
      btn.id = 'btnImportOfflinePackage';
      btn.title = '导入离线更新包';
      btn.innerHTML = '<i class="layui-icon layui-icon-upload-circle"></i>';
      btn.addEventListener('click', openOfflineFileChooser);
      $versionActions.appendChild(btn);
    }
    if (!document.getElementById('offlinePackageInput')) {
      var input = document.createElement('input');
      input.type = 'file';
      input.accept = '.zip';
      input.id = 'offlinePackageInput';
      input.style.display = 'none';
      input.addEventListener('change', function (event) {
        var file = event.target.files && event.target.files[0];
        if (file) executeOfflineUpload(file);
        event.target.value = '';
      });
      document.body.appendChild(input);
    }
  }

  function updateUI(data) {
    STATE.currentVersion = data.current_version || '';
    STATE.currentCommit = data.current_commit || '';
    STATE.updateAvailable = !!data.update_available;
    STATE.latestVersion = data.latest_version || '';
    STATE.canRollback = !!data.can_rollback;
    STATE.changelog = data.changelog || [];
    STATE.checkedAt = data.checked_at || '';
    STATE.release = data.release || null;
    STATE.releaseNotes = data.release_notes || '';
    STATE.source = data.source || '';
    STATE.channel = data.channel || '';
    STATE.platform = data.platform || '';

    if ($currentVersion) $currentVersion.textContent = 'v' + STATE.currentVersion;
    if ($currentCommit) {
      $currentCommit.textContent = STATE.currentCommit;
      $currentCommit.title = '提交 ' + STATE.currentCommit;
    }
    if (!$versionStatusText) return;

    if (STATE.updateAvailable) {
      $versionStatusText.textContent = '可更新至 v' + STATE.latestVersion;
      $versionStatusText.classList.add('has-update');
      $versionStatus.classList.add('has-update');
      if ($btnUpdateNow) {
        $btnUpdateNow.style.display = 'inline-flex';
        $btnUpdateNow.classList.add('has-update');
      }
      if ($versionStatusLink) {
        $versionStatusLink.title = '点击查看官网发布说明';
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
      if ($versionStatusLink) $versionStatusLink.style.display = 'none';
    }

    if ($btnRollback) {
      $btnRollback.style.display = STATE.canRollback ? 'inline-flex' : 'none';
    }
  }

  function setStatus(text, isError) {
    if (!$versionStatusText) return;
    $versionStatusText.textContent = text;
    if (isError) {
      $versionStatusText.style.color = '#f04438';
      setTimeout(function () { $versionStatusText.style.color = ''; }, 5000);
    }
  }

  function checkUpdateSilent() {
    apiGet('/system/version/info/').then(function (res) {
      if (res.success) updateUI(res.data);
    }).catch(function () {});
  }

  function checkUpdate() {
    if (CHECKING) return;
    CHECKING = true;
    if ($btnCheckUpdate) $btnCheckUpdate.classList.add('checking');
    setStatus('检查中...');

    apiGet('/system/version/info/').then(function (res) {
      CHECKING = false;
      if ($btnCheckUpdate) $btnCheckUpdate.classList.remove('checking');
      if (res.success) {
        updateUI(res.data);
      } else {
        setStatus('检查失败', true);
      }
    }).catch(function (err) {
      CHECKING = false;
      if ($btnCheckUpdate) $btnCheckUpdate.classList.remove('checking');
      setStatus('检查失败: ' + err.message, true);
    });
  }

  window.showChangelogModal = function () {
    var overlay = document.getElementById('changelogOverlay');
    if (!overlay) return;
    renderChangelog();
    overlay.style.display = 'flex';
  };

  window.hideChangelogModal = function () {
    var overlay = document.getElementById('changelogOverlay');
    if (overlay) overlay.style.display = 'none';
  };

  function renderChangelog() {
    var tag = document.getElementById('changelogVersionTag');
    var body = document.getElementById('changelogBody');
    var updateBtn = document.getElementById('changelogUpdateBtn');
    if (tag) tag.textContent = STATE.latestVersion ? 'v' + STATE.latestVersion : 'v' + STATE.currentVersion;
    if (updateBtn) updateBtn.style.display = STATE.updateAvailable ? '' : 'none';
    if (!body) return;

    var html = '';
    if (STATE.release) {
      html += '<div class="changelog-meta">';
      if (STATE.release.channel) html += '<p>渠道：' + escapeHtml(STATE.release.channel) + '</p>';
      if (STATE.release.platform) html += '<p>平台：' + escapeHtml(STATE.release.platform) + '</p>';
      if (STATE.release.build) html += '<p>构建号：' + escapeHtml(STATE.release.build) + '</p>';
      if (STATE.release.target) html += '<p>目标环境：' + escapeHtml(STATE.release.target) + '</p>';
      if (STATE.release.minSupportedVersion) html += '<p>最低可升级版本：' + escapeHtml(STATE.release.minSupportedVersion) + '</p>';
      if (STATE.release.packageUrl) html += '<p><a class="text-link" href="' + escapeHtml(STATE.release.packageUrl) + '" target="_blank" rel="noopener">下载更新包</a></p>';
      html += '</div>';
    }

    if (STATE.releaseNotes) {
      html += '<div class="changelog-markdown">' + markdownToHtml(STATE.releaseNotes) + '</div>';
    }

    if (STATE.changelog && STATE.changelog.length) {
      html += '<ul class="changelog-list">';
      STATE.changelog.forEach(function (line, i) {
        var isNew = i < 3 ? ' changelog-item-new' : '';
        html += '<li class="changelog-item' + isNew + '">';
        html += '<span class="changelog-msg">' + escapeHtml(String(line || '')) + '</span>';
        html += '</li>';
      });
      html += '</ul>';
    }

    if (!html) {
      html = '<div class="changelog-empty">暂无更新记录</div>';
    }
    body.innerHTML = html;
  }

  function markdownToHtml(text) {
    return escapeHtml(String(text || ''))
      .replace(/^###\s+(.*)$/gm, '<h4>$1</h4>')
      .replace(/^##\s+(.*)$/gm, '<h3>$1</h3>')
      .replace(/^#\s+(.*)$/gm, '<h2>$1</h2>')
      .replace(/^-\s+(.*)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
      .replace(/\n\n+/g, '</p><p>')
      .replace(/^(?!<h|<u|<li|<p)(.+)$/gm, '<p>$1</p>');
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  document.addEventListener('click', function (e) {
    if (e.target && e.target.id === 'changelogOverlay') hideChangelogModal();
  });

  function confirmUpdate() {
    if (!isUpdateManageable()) {
      setStatus('当前账号仅可查看更新信息，不能执行更新', true);
      return;
    }
    var msg = '确认更新到 v' + STATE.latestVersion + '？\n\n';
    msg += '本次升级将从官网更新中心获取发布包，并执行版本目录切换。\n';
    msg += '确认继续？';
    if (!confirm(msg)) return;
    executeUpdate();
  }

  window.confirmUpdateFromChangelog = function () {
    hideChangelogModal();
    setTimeout(confirmUpdate, 200);
  };

  function executeUpdate() {
    if (UPDATING) return;
    UPDATING = true;
    showProgressOverlay('正在执行在线升级...', '步骤 1/3：请求官网更新中心');
    apiPost('/system/version/update/', { target_version: STATE.latestVersion }).then(function (res) {
      if (!res.success) throw new Error(res.error || '更新失败');
      updateProgress('在线升级完成，准备刷新...', 100);
      finishWithSuccess('更新成功，系统将在 3 秒后刷新。');
    }).catch(function (err) {
      failUpdate(err);
    });
  }

  function openOfflineFileChooser() {
    if (!isUpdateManageable()) {
      setStatus('当前账号仅可查看更新信息，不能导入升级包', true);
      return;
    }
    var input = document.getElementById('offlinePackageInput');
    if (input) input.click();
  }

  function promptOfflineImport() {
    var zipPath = window.prompt('请输入服务器本地离线更新包绝对路径，例如：/opt/dtcall/downloads/dtcall-release-1.0.1-linux-x86_64.zip');
    if (!zipPath) return;
    executeOfflineImport(zipPath);
  }

  function executeOfflineImport(zipPath) {
    if (UPDATING) return;
    UPDATING = true;
    showProgressOverlay('正在导入离线升级包...', '步骤 1/3：校验 ZIP 包');
    apiPost('/system/version/import-package/', { zip_path: zipPath }).then(function (res) {
      if (!res.success) throw new Error(res.error || '离线导入失败');
      updateProgress('离线升级完成，准备刷新...', 100);
      finishWithSuccess('离线升级成功，系统将在 3 秒后刷新。');
    }).catch(function (err) {
      failUpdate(err);
    });
  }

  function executeOfflineUpload(file) {
    if (UPDATING) return;
    UPDATING = true;
    showProgressOverlay('正在上传离线升级包...', '步骤 1/3：上传 ZIP 包');

    var formData = new FormData();
    formData.append('package', file);

    fetch('/system/version/import-package/', {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCsrfToken(),
      },
      credentials: 'same-origin',
      body: formData,
    }).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok) throw new Error((data && (data.error || data.message)) || ('HTTP ' + r.status));
        return data;
      });
    }).then(function (res) {
      if (!res.success) throw new Error(res.error || '离线导入失败');
      updateProgress('离线升级完成，准备刷新...', 100);
      finishWithSuccess('离线升级成功，系统将在 3 秒后刷新。');
    }).catch(function (err) {
      failUpdate(err);
    });
  }

  function confirmRollback() {
    if (!isUpdateManageable()) {
      setStatus('当前账号仅可查看更新信息，不能执行回滚', true);
      return;
    }
    var msg = '确认回滚到上一个版本？\n\n';
    msg += '这会将 current 链接切回上一个版本目录。\n确认继续？';
    if (!confirm(msg)) return;
    executeRollback();
  }

  function executeRollback() {
    if (UPDATING) return;
    UPDATING = true;
    showProgressOverlay('正在回滚...', '切换到上一版本目录');
    apiPost('/system/version/rollback/').then(function (res) {
      if (!res.success) throw new Error(res.error || '回滚失败');
      updateProgress('回滚完成，准备刷新...', 100);
      finishWithSuccess('回滚成功，系统将在 3 秒后刷新。');
    }).catch(function (err) {
      failUpdate(err);
    });
  }

  function finishWithSuccess(message) {
    if (typeof layer !== 'undefined') {
      layer.msg(message, { icon: 1, time: 3000 }, function () {
        window.location.reload(true);
      });
    }
    setTimeout(function () { window.location.reload(true); }, 3000);
  }

  function failUpdate(err) {
    UPDATING = false;
    hideProgressOverlay();
    setStatus(err.message || String(err), true);
    if (typeof layer !== 'undefined') {
      layer.msg(err.message || String(err), { icon: 2, time: 5000 });
    } else {
      alert(err.message || String(err));
    }
  }

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
    if (typeof layui !== 'undefined' && layui.element) layui.element.init();
  }

  function updateProgress(step, percent) {
    var stepEl = document.querySelector('.update-step');
    if (stepEl) stepEl.textContent = step;
    if (typeof layui !== 'undefined' && layui.element) layui.element.progress('updateProgress', percent + '%');
  }

  function hideProgressOverlay() {
    var overlay = document.getElementById('updateProgressOverlay');
    if (overlay) overlay.remove();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
