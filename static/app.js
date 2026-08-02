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

    // ===== 1. 调研概述 =====
    var overview = reportData['调研概述'] || reportData.overview || '';
    if (overview) {
      html += '<div class="section-card">'
        + '<div class="section-icon">📋</div>'
        + '<div class="section-content"><div class="section-label">1. 调研概述</div>'
        + '<div class="summary-text">' + escapeHtml(overview) + '</div></div></div>';
    }

    // ===== 2. 行业现状 =====
    var industry = reportData['行业现状'] || reportData.industry_status || '';
    if (industry) {
      html += '<div class="section-card">'
        + '<div class="section-icon">🏭</div>'
        + '<div class="section-content"><div class="section-label">2. 行业现状</div>'
        + '<p class="bg-text">' + escapeHtml(industry) + '</p></div></div>';
    }

    // ===== 3. 竞品分析 =====
    var competitors = reportData['竞品分析'] || reportData.competitor_analysis || [];
    if (competitors.length > 0) {
      html += '<div class="section-header">3. 竞品分析</div>';
      for (var i = 0; i < competitors.length; i++) {
        var c = competitors[i];
        var name = c['竞品名称'] || c.name || '竞品 ' + (i + 1);
        var analysis = c['分析'] || c.analysis || '';
        html += '<div class="finding-card">'
          + '<div class="finding-number">' + (i + 1) + '</div>'
          + '<div class="finding-body">'
          + '<div class="finding-topic">' + escapeHtml(name) + '</div>'
          + '<div class="finding-detail">' + escapeHtml(analysis) + '</div></div></div>';
      }
    }

    // ===== 4. 机会与风险 =====
    var oppRisk = reportData['机会与风险'] || reportData.opportunities_and_risks || {};
    var opportunities = oppRisk['机会'] || oppRisk.opportunities || [];
    var risks = oppRisk['风险'] || oppRisk.risks || [];
    if (opportunities.length > 0 || risks.length > 0) {
      html += '<div class="section-header">4. 机会与风险</div>';
      if (opportunities.length > 0) {
        html += '<div style="margin-bottom:8px;"><strong>🟢 机会</strong></div><div class="conclusion-list">';
        for (var i = 0; i < opportunities.length; i++) {
          if (opportunities[i]) {
            html += '<div class="conclusion-item"><span class="conclusion-check">✓</span>' + escapeHtml(opportunities[i]) + '</div>';
          }
        }
        html += '</div>';
      }
      if (risks.length > 0) {
        html += '<div style="margin-top:8px;margin-bottom:8px;"><strong>🔴 风险</strong></div><div class="conclusion-list">';
        for (var i = 0; i < risks.length; i++) {
          if (risks[i]) {
            html += '<div class="conclusion-item" style="color:#ef4444;"><span class="conclusion-check" style="color:#ef4444;">⚠</span>' + escapeHtml(risks[i]) + '</div>';
          }
        }
        html += '</div>';
      }
    }

    // ===== 5. 信息来源附录 =====
    var sources = reportData['信息来源附录'] || reportData.sources_appendix || [];
    if (sources.length > 0) {
      html += '<div class="section-header">5. 信息来源附录</div>'
        + '<div class="references-list">';
      for (var i = 0; i < sources.length; i++) {
        if (sources[i]) {
          html += '<div class="reference-item"><span class="ref-id">[' + (i + 1) + ']</span> ' + escapeHtml(sources[i]) + '</div>';
        }
      }
      html += '</div>';
    }

        if (reportDisplay) reportDisplay.innerHTML = html;
    // 隐藏原始 JSON 输出
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

          // 意图识别兜底通知 → 显示通知横幅，更新模式指示器
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

