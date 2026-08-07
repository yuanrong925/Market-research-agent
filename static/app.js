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

    // 将 Markdown 文本转为 HTML
    // 将 Markdown 文本转为 HTML（支持完整 Markdown 语法 + 数据差异蓝色提示）
    function renderMarkdown(text) {
      if (!text) return '';
      // 检测数据差异提示 → 整体包裹蓝色样式
      var hasDiscrepancy = /\u26a0\ufe0f\u3010\u5f85\u4eba\u5de5\u786e\u8ba4\u3011/.test(text);
      var wrapBlue = '';
      var wrapBlueEnd = '';
      if (hasDiscrepancy) {
        wrapBlue = '<div style="color:#2563eb;background:#eff6ff;padding:8px 12px;border-radius:6px;border-left:3px solid #2563eb;margin:4px 0;">';
        wrapBlueEnd = '</div>';
      }
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
          if (!hasDiscrepancy) result += '<br>';
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
      // 如果有差异提示，包裹蓝色容器
      if (hasDiscrepancy) {
        result = wrapBlue + result + wrapBlueEnd;
      }
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
        html += '<div class="summary-text">' + renderMarkdown(value) + '</div>';
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

  // ========== 追问功能 ==========
  function injectFollowupBox(sessionId, reportEl) {
    // 移除已有追问框
    var old = document.getElementById('followupBox');
    if (old) old.remove();

    if (!reportEl) return;
    var box = document.createElement('div');
    box.id = 'followupBox';
    box.style.cssText = 'margin-top:16px;padding:12px;background:var(--surface);border-radius:8px;border:1px solid var(--border, #e5e7eb);';
    box.innerHTML =
      '<div style="font-weight:600;margin-bottom:8px;">💬 对该报告进行追问</div>' +
      '<div style="display:flex;gap:8px;">' +
      '<input id="followupInput" type="text" placeholder="追问：如"报告中提到的风险，有什么应对策略？"" autocomplete="off" style="flex:1;padding:8px 12px;border:1px solid var(--border,#d1d5db);border-radius:6px;font-size:14px;">' +
      '<button id="followupBtn" style="padding:8px 16px;background:var(--primary,#2563eb);color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;">发送</button>' +
      '</div>' +
      '<div id="followupAnswer" style="margin-top:10px;font-size:14px;line-height:1.6;max-height:300px;overflow-y:auto;display:none;"></div>';
    reportEl.parentNode.insertBefore(box, reportEl.nextSibling);

    var input = document.getElementById('followupInput');
    var btn = document.getElementById('followupBtn');
    var answerDiv = document.getElementById('followupAnswer');

    async function sendFollowup() {
      var question = input.value.trim();
      if (!question) return;
      input.disabled = true;
      btn.disabled = true;
      btn.textContent = '...';
      answerDiv.style.display = 'block';
      answerDiv.innerHTML = '<span style="color:var(--muted);">⏳ 正在生成回答...</span>';

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
                answerDiv.textContent = accumulated;
                answerDiv.scrollTop = answerDiv.scrollHeight;
              }
              if (evt.step === 'followup_done') {
                answerDiv.textContent = evt.answer || accumulated;
              }
              if (evt.step === 'error') {
                answerDiv.innerHTML = '<span style="color:#ef4444;">❌ ' + escapeHtml(evt.msg || '未知') + '</span>';
              }
            } catch(e) {}
          }
        }
      } catch(e) {
        answerDiv.innerHTML = '<span style="color:#ef4444;">❌ 追问失败: ' + escapeHtml(e.message) + '</span>';
      } finally {
        input.disabled = false;
        btn.disabled = false;
        btn.textContent = '发送';
        input.value = '';
      }
    }

    btn.addEventListener('click', sendFollowup);
    input.addEventListener('keydown', function(e) { if (e.key === 'Enter') sendFollowup(); });
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
        'ingestion_start': '📄 正在解析数据...',
        'ingestion_done': '✅ 数据解析完成',
        'retrieval_start': '🔍 正在检索相关素材...',
        'retrieval_done': '✅ 检索完成',
        'analyst_start': '🧠 正在分析规划...',
        'analyst_streaming': '🧠 分析规划中...',
        'analyst_done': '✅ 大纲规划完成',
        'writer_start': '✍️ 正在撰写报告...',
        'writer_streaming': '✍️ 生成报告中...',
        'writer_done': '✅ 报告撰写完成',
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
                injectFollowupBox(sid, reportDisplay);
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
  console.log('[MRA] app.js loaded');
});

