/**
 * app.js — Market Research Agent 前端 UI
 */
document.addEventListener('DOMContentLoaded', function () {
  'use strict';
  function $(id) { return document.getElementById(id); }
  var runBtn   = $('runBtn');
  var planList = $('planList');
  var reportDisplay = $('reportDisplay');
  var reportOut = $('reportOutput');
  var factPanel   = $('factcheckPanel');
  var factOut     = $('factcheckOutput');
  var dlBtn       = $('downloadPdfBtn');
  var currentSessionId = null;  // 多轮对话：当前会话 ID
  if (!runBtn) { console.error('[MRA] #runBtn not found'); return; }
  function getModel() {
    var el = $('modelMode');
    return el ? el.value : 'cloud';
  }
  function getWebMode() {
    var els = document.querySelectorAll('input[name="webMode"]');
    for (var i = 0; i < els.length; i++) {
      if (els[i].checked) return els[i].value;
    }
    return 'auto';
  }
  function getWebModeLabel() {
    var mode = getWebMode();
    var labels = { 'disabled': '📄 仅 PDF', 'auto': '🌐 PDF + 联网', 'enabled': '🔍 纯联网' };
    return labels[mode] || '🌐 PDF + 联网';
  }
  function getTask() {
    var el = $('taskInput');
    return el ? el.value.trim() : '';
  }
  function getFile() {
    var el = $('pdfFile');
    return (el && el.files && el.files[0]) || null;
  }
  function renderPlan(plan) {
    if (!planList) return;
    planList.innerHTML = '';
    if (!plan || plan.length === 0) {
      planList.innerHTML = '<li style="color:var(--muted);">暂无计划</li>';
      return;
    }
    for (var i = 0; i < plan.length; i++) {
      var item = plan[i];
      var li = document.createElement('li');
      var status = (item.status || '') === 'done' ? 'done' : 'pending';
      li.innerHTML = '<span class="status-dot ' + status + '"></span>' + escapeHtml(item.step || item.title || item.topic || '');
      planList.appendChild(li);
    }
  }
  function renderReport(reportData) {
    if (reportDisplay) reportDisplay.innerHTML = '';
    if (!reportData || Object.keys(reportData).length === 0) {
      if (reportDisplay) reportDisplay.innerHTML = '<div class="empty-state">暂无数据</div>';
      return;
    }

    var html = '';

    // ===== 报告标题 =====
    if (reportData.title || reportData['标题']) {
      html += '<div class="report-title">' + escapeHtml(reportData.title || reportData['标题']) + '</div>';
    }

    // ====== 通用章节渲染：按优先级顺序渲染所有字段 ======
    var priorityKeys = [
      '摘要', '执行摘要', '研究背景', '调研概述',
      '行业现状', '市场规模', '竞争格局',
      '产品与价格趋势', '商业模式',
      '行业挑战与风险', '总结与展望',
      '总结', '结论', '建议', '引用来源',
      '竞品分析', '机会与风险', '信息来源附录',
    ];

    var allKeys = Object.keys(reportData);
    var orderedKeys = [];
    for (var pi = 0; pi < priorityKeys.length; pi++) {
      if (reportData[priorityKeys[pi]] !== undefined) {
        orderedKeys.push(priorityKeys[pi]);
      }
    }
    for (var ki = 0; ki < allKeys.length; ki++) {
      if (orderedKeys.indexOf(allKeys[ki]) === -1 && allKeys[ki] !== '标题' && allKeys[ki] !== 'title') {
        orderedKeys.push(allKeys[ki]);
      }
    }

    // 将 Markdown 文本转为 HTML（支持完整 Markdown 语法）
    // 数据差异标记已在前端渲染为普通文本，不额外着色
    function renderMarkdown(text) {
      if (!text) return '';
      // 先转义 HTML 实体
      var escaped = escapeHtml(text);
      // 将 Markdown 语法转换为 HTML 标签
      // 行内代码：\`code\` → <code>code</code>
      escaped = escaped.replace(/\`([^\`]+)\`/g, '<code>$1</code>');
      // 加粗：**text** → <strong>text</strong>
      escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      // 斜体：*text* → <em>text</em>
      escaped = escaped.replace(/\*([^*]+)\*/g, '<em>$1</em>');
      // 链接：[text](url) → <a href="url" target="_blank">text</a>
      escaped = escaped.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
      // 图片：![alt](url) → <img src="url" alt="alt" />
      escaped = escaped.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;height:auto;" />');
      // 删除线：~~text~~ → <del>text</del>
      escaped = escaped.replace(/~~([^~]+)~~/g, '<del>$1</del>');
      // 按行处理
      var lines = ('' + escaped).split('\n');
      var result = '';
      var inList = false;
      for (var li = 0; li < lines.length; li++) {
        var line = lines[li];
        var trimmed = line.trim();
        if (!trimmed) {
          if (inList) { result += '</ul>'; inList = false; }
          result += '<br>';
          continue;
        }
        // 中文编号章节标题：一、市场发展现状（深蓝 h4）
        var cnHMatch = trimmed.match(/^([一二三四五六七八九十]+)[、.．]\\s*(.*)/);
        if (cnHMatch) {
          if (inList) { result += '</ul>'; inList = false; }
          result += '<h4 style="margin:14px 0 6px 0;font-size:15px;color:#1e40af;">' + cnHMatch[1] + '、' + cnHMatch[2] + '</h4>';
          continue;
        }
        // 数字编号子标题：1.1 全球市场规模与增长（浅蓝 h5）
        var numHMatch = trimmed.match(/^(\\d+\\.\\d+)\\s+(.*)/);
        if (numHMatch) {
          if (inList) { result += '</ul>'; inList = false; }
          result += '<h5 style="margin:10px 0 4px 0;font-size:14px;color:#2563eb;">' + numHMatch[1] + ' ' + numHMatch[2] + '</h5>';
          continue;
        }
        // Markdown 标题
        var hMatch = trimmed.match(/^(#{1,3})\\s+(.*)/);
        if (hMatch) {
          if (inList) { result += '</ul>'; inList = false; }
          var hLevel = hMatch[1].length;
          var hText = hMatch[2];
          if (hLevel === 1) result += '<h3 style="margin:16px 0 8px 0;font-size:16px;color:#1e40af;">' + hText + '</h3>';
          else if (hLevel === 2) result += '<h4 style="margin:12px 0 6px 0;font-size:15px;color:#2563eb;">' + hText + '</h4>';
          else result += '<h5 style="margin:10px 0 4px 0;font-size:14px;color:#3b82f6;">' + hText + '</h5>';
          continue;
        }
        // 列表项
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          if (!inList) { result += '<ul style="margin:4px 0;padding-left:20px;">'; inList = true; }
          result += '<li style="margin:2px 0;line-height:1.6;">' + trimmed.substring(2) + '</li>';
          continue;
        }
        // 普通段落
        if (inList) { result += '</ul>'; inList = false; }
        result += '<p style="margin:4px 0;line-height:1.8;">' + trimmed + '</p>';
      }
      if (inList) result += '</ul>';
      // 普通文本渲染，无特殊着色
      return result;
    }

    for (var i = 0; i < orderedKeys.length; i++) {
      var key = orderedKeys[i];
      var value = reportData[key];
      if (value === undefined || value === null || value === '') continue;

      // 渲染章节标题
      html += '<div class="section-card">';
      html += '<div class="section-icon">📄</div>';
      html += '<div class="section-content">';
      html += '<div class="section-label">' + escapeHtml(key) + '</div>';

      // 根据值类型渲染
      if (typeof value === 'string') {
        html += '<div class="summary-text" style="overflow-wrap:break-word;">' + renderMarkdown(value) + '</div>';
      } else if (Array.isArray(value)) {
        html += '<div class="references-list">';
        for (var vi = 0; vi < value.length; vi++) {
          var item = value[vi];
          if (typeof item === 'string') {
            html += '<div class="reference-item" style="margin:4px 0;">' + renderMarkdown(item) + '</div>';
          } else if (typeof item === 'object' && item !== null) {
            html += '<div class="finding-card" style="margin:6px 0;">';
            html += '<div class="finding-number">' + (vi + 1) + '</div>';
            html += '<div class="finding-body">';
            for (var k in item) {
              if (item.hasOwnProperty(k)) {
                html += '<div class="finding-topic">' + escapeHtml(k) + '</div>';
                html += '<div class="finding-detail">' + renderMarkdown('' + item[k]) + '</div>';
              }
            }
            html += '</div></div>';
          }
        }
        html += '</div>';
      } else if (typeof value === 'object' && value !== null) {
        html += '<div>';
        for (var k in value) {
          if (value.hasOwnProperty(k)) {
            var v = value[k];
            html += '<div style="margin:6px 0;"><strong>' + escapeHtml(k) + '：</strong>';
            if (Array.isArray(v)) {
              html += '<ul style="margin:4px 0;padding-left:20px;">';
              for (var vi = 0; vi < v.length; vi++) {
                html += '<li style="margin:2px 0;">' + escapeHtml('' + v[vi]) + '</li>';
              }
              html += '</ul>';
            } else {
              html += renderMarkdown('' + v);
            }
            html += '</div>';
          }
        }
        html += '</div>';
      }

      html += '</div></div>';
    }

    if (reportDisplay) reportDisplay.innerHTML = html;
    if (reportOut) reportOut.style.display = 'none';
  }
  function renderFactCheck(issues) {
    if (!factPanel || !factOut) return;
    if (!issues || issues.length === 0) {
      factPanel.style.display = 'none';
      return;
    }
    factPanel.style.display = 'block';
    var html = '<h3 style="color:#fbbf24;">⚠️ ' + issues.length + ' 个事实核查问题</h3><ul>';
    for (var i = 0; i < Math.min(issues.length, 5); i++) {
      var sent = (issues[i].sentence || '').substring(0, 80);
      html += '<li>' + escapeHtml(sent) + ' → <em>' + escapeHtml(issues[i].issue || '') + '</em></li>';
    }
    html += '</ul>';
    factOut.innerHTML = html;
  }
  function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  function setupDownload(task, reportData) {
    if (!dlBtn) return;
    if (!reportData) { dlBtn.disabled = true; return; }
    dlBtn.disabled = false;
    dlBtn.onclick = async function () {
      var reportText = typeof reportData === 'string' ? reportData : JSON.stringify(reportData, null, 2);
      var payload = new FormData();
      payload.append('task', task);
      payload.append('report_text', reportText);
      try {
        var resp = await fetch('/api/report/pdf', { method: 'POST', body: payload });
        if (!resp.ok) {
          try {
            var err = await resp.json();
            alert('PDF 导出失败: ' + (err.detail || resp.statusText));
          } catch(e) {
            alert('PDF 导出失败: HTTP ' + resp.status + ' ' + resp.statusText);
          }
          return;
        }
        var blob = await resp.blob();
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'market_research_report.pdf';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (e) {
        alert('PDF 导出失败: ' + e.message);
      }
    };
  }

  // ========== 气泡对话模式（取代追问框） ==========
  function injectBubbleChat(sessionId, reportEl) {
    // 移除已有追问框
    var old = document.getElementById('followupBox');
    if (old) old.remove();

    if (!reportEl) return;

    // 创建气泡对话容器
    var chatContainer = document.createElement('div');
    chatContainer.id = 'followupBox';
    chatContainer.style.cssText = 'margin-top:16px;border:1px solid var(--border,#e5e7eb);border-radius:12px;overflow:hidden;background:var(--surface,#fff);box-shadow:0 1px 3px rgba(0,0,0,0.08);';

    // ---- 头部 ----
    var header = document.createElement('div');
    header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:#f8fafc;border-bottom:1px solid #e5e7eb;';
    header.innerHTML = '<span style="font-weight:600;font-size:14px;color:#1e293b;">💬 对话追问</span>' +
      '<span style="font-size:12px;color:#94a3b8;" id="chatMsgCount">0 轮对话</span>';
    chatContainer.appendChild(header);

    // ---- 消息列表 ----
    var msgList = document.createElement('div');
    msgList.id = 'chatMessageList';
    msgList.style.cssText = 'padding:16px;max-height:420px;overflow-y:auto;display:flex;flex-direction:column;gap:12px;background:#fafbfc;';
    chatContainer.appendChild(msgList);

    // ---- 输入区域 ----
    var inputArea = document.createElement('div');
    inputArea.style.cssText = 'display:flex;gap:8px;padding:12px 16px;border-top:1px solid #e5e7eb;background:#fff;';
    inputArea.innerHTML =
      '<input id="followupInput" type="text" placeholder="输入追问内容…" autocomplete="off" style="flex:1;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;font-size:14px;outline:none;transition:border-color 0.2s;">' +
      '<button id="followupBtn" style="padding:10px 18px;background:var(--primary,#2563eb);color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:14px;white-space:nowrap;transition:background 0.2s;">发送</button>';
    chatContainer.appendChild(inputArea);

    // 插入到报告下方
    reportEl.parentNode.insertBefore(chatContainer, reportEl.nextSibling);

    var input = document.getElementById('followupInput');
    var btn = document.getElementById('followupBtn');
    var msgListEl = document.getElementById('chatMessageList');

    // 公共的 Markdown 转换函数（避免重复）
    function simpleMarkdown(text, linkColor) {
      if (!text) return '';
      linkColor = linkColor || '#2563eb';
      var html = escapeHtml(text);
      html = html.replace(/\`([^\`]+)\`/g, '<code style="background:#e2e8f0;padding:1px 4px;border-radius:3px;font-size:13px;">$1</code>');
      html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
      html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:' + linkColor + ';text-decoration:underline;">$1</a>');
      html = html.replace(/\n/g, '<br>');
      return html;
    }

    // 创建气泡消息
    function createBubble(role, content, isStreaming) {
      var div = document.createElement('div');
      div.style.cssText = 'display:flex;' + (role === 'user' ? 'justify-content:flex-end;' : 'justify-content:flex-start;');
      var bubble = document.createElement('div');
      bubble.className = 'chat-bubble';
      var isUser = role === 'user';
      bubble.style.cssText =
        'max-width:80%;padding:10px 14px;border-radius:12px;font-size:14px;line-height:1.6;word-break:break-word;' +
        (isUser
          ? 'background:#2563eb;color:#fff;border-bottom-right-radius:4px;'
          : 'background:#e8f0fe;color:#1e293b;border-bottom-left-radius:4px;');
      // 如果是流式内容，使用 textContent 防止 XSS；否则用 innerHTML 支持基本格式
      if (isStreaming) {
        bubble.textContent = content;
      } else {
        bubble.innerHTML = simpleMarkdown(content, isUser ? '#bfdbfe' : '#2563eb');
      }
      div.appendChild(bubble);
      return div;
    }

    // 加载历史对话
    function loadConversationHistory() {
      fetch('/api/v1/conversation/' + encodeURIComponent(sessionId))
        .then(function(resp) {
          if (!resp.ok) return null;
          return resp.json();
        })
        .then(function(data) {
          if (!data || !data.conversation) return;
          var msgs = data.conversation;
          var countEl = document.getElementById('chatMsgCount');
          if (countEl) countEl.textContent = Math.ceil(msgs.length / 2) + ' 轮对话';
          msgListEl.innerHTML = '';
          for (var i = 0; i < msgs.length; i++) {
            var msg = msgs[i];
            if (msg.role === 'user' || msg.role === 'assistant') {
              var bubble = createBubble(msg.role, msg.content);
              msgListEl.appendChild(bubble);
            }
          }
          msgListEl.scrollTop = msgListEl.scrollHeight;
        })
        .catch(function(e) {
          console.warn('[MRA] 加载对话历史失败:', e);
        });
    }

    // 发送追问
    async function sendFollowup() {
      var question = input.value.trim();
      if (!question) return;
      input.disabled = true;
      btn.disabled = true;
      btn.textContent = '...';

      // 追加用户气泡
      var userBubbleDiv = createBubble('user', question);
      msgListEl.appendChild(userBubbleDiv);
      msgListEl.scrollTop = msgListEl.scrollHeight;

      // 创建助手气泡（占位，流式写入）
      var assistantBubbleDiv = createBubble('assistant', '', true);
      var assistantBubble = assistantBubbleDiv.querySelector('.chat-bubble');
      msgListEl.appendChild(assistantBubbleDiv);
      msgListEl.scrollTop = msgListEl.scrollHeight;

      // 更新计数
      var countEl = document.getElementById('chatMsgCount');
      if (countEl) {
        var currentCount = parseInt(countEl.textContent) || 0;
        countEl.textContent = (currentCount + 1) + ' 轮对话';
      }

      input.value = '';

      try {
        var formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('question', question);
        formData.append('model_mode', getModel());

        var resp = await fetch('/api/followup-stream', { method: 'POST', body: formData });
        if (!resp.ok) {
          var et = await resp.text();
          throw new Error(et);
        }

        var reader = resp.body.getReader();
        var decoder = new TextDecoder('utf-8');
        var buffer = '';
        var accumulated = '';

        while (true) {
          var chunk = await reader.read();
          if (chunk.done) break;
          buffer += decoder.decode(chunk.value, { stream: true });
          var lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (var li = 0; li < lines.length; li++) {
            var line = lines[li];
            if (!line.startsWith('data: ')) continue;
            try {
              var evt = JSON.parse(line.substring(6));
              if (evt.text) {
                accumulated += evt.text;
                if (assistantBubble) {
                  assistantBubble.textContent = accumulated;
                }
                msgListEl.scrollTop = msgListEl.scrollHeight;
              }
              if (evt.step === 'followup_done') {
                // 最终内容用格式化版本替换
                if (assistantBubble && evt.answer) {
                  assistantBubble.innerHTML = simpleMarkdown(evt.answer, '#2563eb');
                }
              }
              if (evt.step === 'error') {
                if (assistantBubble) {
                  assistantBubble.style.background = '#fee2e2';
                  assistantBubble.style.color = '#dc2626';
                  assistantBubble.innerHTML = '❌ ' + escapeHtml(evt.msg || '未知错误');
                }
              }
            } catch(e) {}
          }
        }

        // 更新计数
        if (countEl) {
          var totalMsgs = msgListEl.querySelectorAll('.chat-bubble').length;
          countEl.textContent = Math.ceil(totalMsgs / 2) + ' 轮对话';
        }

      } catch(e) {
        if (assistantBubble) {
          assistantBubble.style.background = '#fee2e2';
          assistantBubble.style.color = '#dc2626';
          assistantBubble.innerHTML = '❌ 追问失败: ' + escapeHtml(e.message);
        }
      } finally {
        input.disabled = false;
        btn.disabled = false;
        btn.textContent = '发送';
      }
    }

    // 加载历史
    loadConversationHistory();

    // 绑定事件
    btn.addEventListener('click', sendFollowup);
    input.addEventListener('keydown', function(e) { if (e.key === 'Enter') sendFollowup(); });
    // 输入框焦点样式
    input.addEventListener('focus', function() { this.style.borderColor = '#2563eb'; });
    input.addEventListener('blur', function() { this.style.borderColor = '#d1d5db'; });
    btn.addEventListener('mouseenter', function() { this.style.background = '#1d4ed8'; });
    btn.addEventListener('mouseleave', function() { this.style.background = '#2563eb'; });
  }

  runBtn.addEventListener('click', async function () {
    var task = getTask();
    if (!task) { alert('请填写分析任务'); return; }
    var model = getModel();
    var file = getFile();
    // 初始化 UI
    if (planList) planList.innerHTML = '<li style="color:var(--muted);">⏳ 流式分析中...</li>';
    var webModeLabel = getWebModeLabel();
    if (reportDisplay) reportDisplay.innerHTML =
      '<div id="streamProgress" class="stream-progress">\n' +
      '  <div class="stream-step active" id="stepBar">🚀 正在启动...</div>\n' +
      '  <div class="stream-step" id="modeIndicator" style="background:var(--primary,#2563eb);color:#fff;font-weight:600;">' + webModeLabel + '</div>\n' +
      '</div>\n' +
      '<div id="streamOutput" class="stream-output" style="white-space:pre-wrap;font-family:monospace;font-size:13px;padding:12px;background:var(--surface);border-radius:8px;margin-top:12px;max-height:400px;overflow-y:auto;"></div>';
    if (reportOut) { reportOut.style.display = 'none'; }
    if (factPanel) factPanel.style.display = 'none';
    runBtn.disabled = true;
    runBtn.textContent = '⏳ 分析中...';

    try {
      var webMode = getWebMode();
      var formData = new FormData();
      formData.append('task', task);
      formData.append('model_mode', model);
      formData.append('manual_web_search_mode', webMode);
      if (file) formData.append('pdf_file', file);

      var response = await fetch('/api/v1/research/stream', { method: 'POST', body: formData });
      if (!response.ok) {
        var errText = await response.text();
        throw new Error(errText || ('HTTP ' + response.status));
      }

      var reader = response.body.getReader();
      var decoder = new TextDecoder('utf-8');
      var buffer = '';
      var finalReportData = null;
      var finalPdfPath = null;
      var streamOutput = document.getElementById('streamOutput');
      var stepBar = document.getElementById('stepBar');
      var allStreamedText = '';

      var stepLabels = {
        'planning_start': '📋 正在拆解调研需求...',
        'planning_done': '✅ 规划完成',
        'ingestion_start': '📄 正在解析数据...',
        'ingestion_done': '✅ 数据解析完成',
        'retrieval_start': '🔍 正在检索相关素材...',
        'retrieval_done': '✅ 检索完成',
        'subtask_retrieval': '🔍 执行子任务检索...',
        'citation_metadata': '📝 已生成引用元数据',
        'web_ingestion_start': '🌐 正在清洗网页切片...',
        'web_ingestion_done': '✅ 网页入库完成',
        'conflict_check_start': '🔎 正在检查多源数据一致性...',
        'conflict_check_done': '✅ 冲突检测完成',
        'validation_start': '✅ 正在校验素材一致性...',
        'validation_done': '✅ 素材校验完成',
        'supplement_retrieval_start': '🔍 素材不足，正在补充检索...',
        'supplement_retrieval_done': '✅ 补充检索完成',
        'supplement_retrieval_result': '📊 补充检索结果',
        'supplement_retrieval_maxed': '⚠️ 补充检索已达上限',
        'analyst_start': '🧠 正在分析规划...',
        'analyst_streaming': '🧠 分析规划中...',
        'analyst_done': '✅ 大纲规划完成',
        'writer_start': '✍️ 正在撰写报告...',
        'writer_streaming': '✍️ 生成报告中...',
        'writer_done': '✅ 报告撰写完成',
        'post_check_start': '🔎 正在执行后置段落校验...',
        'post_check_done': '✅ 后置校验完成',
        'number_rewrite_start': '✏️ 正在修正数字...',
        'number_rewrite_done': '✅ 数字修正完成',
        'manual_confirm': '📋 需人工确认数字问题',
        'pdf_generating': '📑 正在生成 PDF 报告...',
        'done': '🎉 全部分析完成！',
        'error': '❌ 出错了',
        'early_terminate': '⏹️ 检索无有效信息，分析已提前终止',
        'intent_override': '🔔 意图识别兜底生效'
      };

      while (true) {
        var result = await reader.read();
        if (result.done) break;
        buffer += decoder.decode(result.value, { stream: true });
        var lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (var li = 0; li < lines.length; li++) {
          var line = lines[li];
          if (!line.startsWith('data: ')) continue;
          var jsonStr = line.substring(6);
          var event;
          try { event = JSON.parse(jsonStr); } catch(e) { continue; }

          var step = event.step;
          var label = stepLabels[step] || step;
          if (stepBar && label) {
            stepBar.textContent = label;
          }

          // 流式文本 → 实时输出
          if (event.text && streamOutput) {
            allStreamedText += event.text;
            streamOutput.textContent = allStreamedText;
            streamOutput.scrollTop = streamOutput.scrollHeight;
          }

          // 检索完成通知（含 web_only 模式PDF忽略提示）
          if (step === 'retrieval_done' && event.notification && streamOutput) {
            allStreamedText += '\n📢 ' + event.notification + '\n';
            streamOutput.textContent = allStreamedText;
            streamOutput.scrollTop = streamOutput.scrollHeight;
            // 更新模式指示器为警告色，提示用户PDF被忽略
            var modeIndicator = document.getElementById('modeIndicator');
            if (modeIndicator) {
              modeIndicator.textContent = '🔍 纯联网（已忽略上传的PDF）';
              modeIndicator.style.background = '#f59e0b';
              modeIndicator.style.color = '#fff';
            }
          }

          // 早停事件（检索后子任务全部不相关/文档无数据，直接截停）
          if (step === 'early_terminate') {
            if (streamOutput) {
              allStreamedText += '\n⏹️ ' + (event.msg || '检索未发现有效信息，自动停止分析') + '\n';
              if (event.info_limitation_note) {
                allStreamedText += '\n💡 建议：' + event.info_limitation_note + '\n';
              }
              streamOutput.textContent = allStreamedText;
              streamOutput.style.color = '#f59e0b';
            }
            if (stepBar) stepBar.textContent = '⏹️ 检索无有效信息，分析已提前终止';
            // 显示错误提示卡片
            if (reportDisplay) {
              reportDisplay.innerHTML = '<div class="empty-state" style="text-align:center;padding:40px;border:2px dashed #f59e0b;border-radius:12px;">'
                + '<div style="font-size:48px;margin-bottom:16px;">⏹️</div>'
                + '<div style="font-size:18px;font-weight:600;color:#f59e0b;margin-bottom:8px;">分析已提前终止</div>'
                + '<div style="font-size:14px;color:var(--muted);max-width:400px;margin:0 auto;">'
                + escapeHtml(event.msg || '检索未发现有效信息') + '</div>'
                + (event.info_limitation_note ? '<div style="font-size:13px;color:var(--muted);margin-top:12px;padding:8px 12px;background:#fefce8;border-radius:6px;">💡 ' + escapeHtml(event.info_limitation_note) + '</div>' : '')
                + '</div>';
            }
            if (streamOutput) streamOutput.style.display = 'none';
          }

          // 意图识别兜底通知 → 显示通知横幅，弹出二选一确认框
          if (step === 'intent_override' && event.notification) {
            var modeIndicator = document.getElementById('modeIndicator');
            if (modeIndicator) {
              modeIndicator.textContent = '📄 ' + escapeHtml(event.notification);
              modeIndicator.style.background = '#f59e0b';
              modeIndicator.style.color = '#fff';
            }
            if (streamOutput) {
              allStreamedText += '\n🔔 ' + event.notification + '\n';
              streamOutput.textContent = allStreamedText;
              streamOutput.scrollTop = streamOutput.scrollHeight;
            }
            // 弹出二选一确认框：用户确认是否切换为仅PDF模式
            if (event.suggest_switch && event.new_mode === 'disabled') {
              var userChoice = confirm('检测到您的需求偏向仅基于文档内容分析。\n\n是否切换至【仅PDF】模式（关闭联网，仅使用文档信息）？\n\n点击「确定」切换为仅PDF模式\n点击「取消」保持当前模式继续');
              if (userChoice) {
                // 用户确认切换 → 重新发起请求（标记为pdf_only模式）
                // 由于当前请求已经在执行中，我们标记请求需要重启
                if (streamOutput) {
                  allStreamedText += '\n🔄 正在切换至【仅PDF】模式，重新分析...\n';
                  streamOutput.textContent = allStreamedText;
                }
                // 设置标志，让后续代码重启请求
                window._intentSwitchConfirmed = true;
                window._intentSwitchNewMode = 'disabled';
              } else {
                if (streamOutput) {
                  allStreamedText += '\n✅ 保持当前模式继续分析\n';
                  streamOutput.textContent = allStreamedText;
                }
              }
            }
          }

          // 分析完成 → 提取大纲结果
          if (step === 'analyst_done' && streamOutput) {
            streamOutput.textContent = allStreamedText;
          }

          // 报告生成完成 → 渲染最终报告
          if (step === 'writer_done' || step === 'done') {
            finalReportData = event.report;
            finalPdfPath = event.pdf_path;
            if (finalReportData && typeof finalReportData === 'object') {
              renderReport(finalReportData);
              setupDownload(task, finalReportData);
              if (streamOutput) streamOutput.style.display = 'none';
              // 捕获 session_id，注入追问输入框
              var sid = event.session_id || '';
              if (sid) {
                currentSessionId = sid;
                injectBubbleChat(sid, reportDisplay);
              }
            }
          }

          // 错误处理
          if (step === 'error') {
            if (streamOutput) {
              streamOutput.textContent = '❌ ' + (event.msg || '未知错误');
              streamOutput.style.color = '#ef4444';
            }
            if (stepBar) stepBar.textContent = '❌ ' + (event.msg || '分析失败');
          }

          // 更新计划列表（用步骤标签作为计划进度）
          if (planList && step && step !== 'analyst_streaming' && step !== 'writer_streaming') {
            var existing = planList.querySelectorAll('li');
            var found = false;
            for (var ei = 0; ei < existing.length; ei++) {
              if (existing[ei].textContent.indexOf(label) !== -1) { found = true; break; }
            }
            if (!found) {
              var li = document.createElement('li');
              li.innerHTML = '<span class="status-dot pending"></span>' + escapeHtml(label);
              planList.appendChild(li);
            }
          }
        }
      }

      // 循环结束：如果没收到 done 事件但有报告数据
      if (finalReportData) {
        renderReport(finalReportData);
        setupDownload(task, finalReportData);
      }

    } catch (error) {
      console.error('[MRA] Stream Error:', error);
      if (reportDisplay) reportDisplay.innerHTML = '<div class="empty-state" style="color:#ef4444;">❌ 流式分析失败: ' + escapeHtml(error.message) + '</div>';
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = '🚀 开始分析';
    }
  });
  // 自动初始化气泡对话（如果存在会话）
  function tryAutoInitChat() {
    fetch('/api/v1/conversation')
      .then(function(resp) {
        if (!resp.ok) return null;
        return resp.json();
      })
      .then(function(data) {
        if (!data || !data.conversations || data.conversations.length === 0) return;
        var conv = data.conversations[0];
        var sid = conv.session_id || conv.id;
        if (sid) {
          currentSessionId = sid;
          injectBubbleChat(sid, reportDisplay);
        }
      })
      .catch(function(e) {
        console.warn('[MRA] 自动加载会话失败:', e);
      });
  }
  tryAutoInitChat();

  console.log('[MRA] app.js loaded');
});

