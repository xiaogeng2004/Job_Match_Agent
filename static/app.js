const SAMPLE_RESUMES = [
  {
    name: "数据分析",
    text: `计算机科学与技术专业，本科。熟悉 Python、SQL、pandas、scikit-learn 和 Tableau。
在广告投放分析项目中完成数据清洗、指标体系建设、A/B 测试和可视化看板搭建，
通过用户分层和转化漏斗分析定位低效投放渠道。熟悉 Excel、Power BI、Linux 和 Git。`
  },
  {
    name: "前端开发",
    text: `软件工程专业，本科。熟悉 JavaScript、TypeScript、HTML、CSS、React 和 Vue3。
使用 React、TypeScript、Vite 和 Ant Design 开发过数据管理平台，负责组件设计、
路由状态管理、接口联调和首屏性能优化。熟悉浏览器与 HTTP、Git、单元测试和
ECharts 数据可视化，了解 Node.js 和 Webpack。`
  },
  {
    name: "嵌入式开发",
    text: `电子信息工程专业，本科。熟悉 C/C++、STM32、ARM Cortex-M 和 FreeRTOS，
有嵌入式软件开发与调试经验。项目中使用 UART、SPI、I2C 和 CAN 连接传感器与电机，
完成外设驱动、任务调度、通信协议解析和单元测试。能够阅读原理图，使用示波器
和逻辑分析仪定位软硬件问题，熟悉 Git 和 Python 自动化测试脚本。`
  }
];

const roleNames = {
  backend: "后端开发",
  frontend: "前端开发",
  algorithm: "算法工程师",
  embedded: "嵌入式开发",
  data_analysis: "数据分析",
  data_engineering: "数据开发 / 大数据",
  test_development: "测试开发",
  cloud_native_sre: "云原生 / DevOps / SRE"
};

const $ = (selector) => document.querySelector(selector);
const analyzeButton = $("#analyze-button");
const resumeText = $("#resume-text");
const resumeFile = $("#resume-file");
const sampleButton = $("#sample-button");
const sampleStatus = $("#sample-status");
let nextSampleIndex = 0;
const confirmedSkills = new Set();
let confirmedCustomRole = "";
let browsePage = 1;
let browseLoading = false;

if (new URLSearchParams(window.location.search).get("gray") === "1") {
  document.body.classList.add("grayscale-check");
}

sampleButton.addEventListener("click", () => {
  const sample = SAMPLE_RESUMES[nextSampleIndex];
  resumeText.value = sample.text;
  confirmedSkills.clear();
  confirmedCustomRole = "";
  sampleStatus.textContent = `已加载：${sample.name}（${nextSampleIndex + 1}/${SAMPLE_RESUMES.length}）`;
  nextSampleIndex = (nextSampleIndex + 1) % SAMPLE_RESUMES.length;
  sampleButton.textContent = "下一个示例";
});

resumeFile.addEventListener("change", () => {
  $("#file-name").textContent = resumeFile.files[0]?.name || "未选择文件";
  confirmedSkills.clear();
});
resumeText.addEventListener("input", () => confirmedSkills.clear());
$("#custom-jd").addEventListener("input", () => {
  confirmedCustomRole = "";
});

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function skillChips(skills, className = "", interactive = false) {
  return skills.map((skill) => {
    if (interactive) {
      return `<button class="skill-chip ${className}" type="button"
        data-skill-key="${escapeHtml(skill.key)}"
        data-skill-name="${escapeHtml(skill.name)}"
        title="点击确认您具备该技能">${escapeHtml(skill.name)}</button>`;
    }
    return `<span class="skill-chip ${className}" title="${escapeHtml(skill.category)}">${escapeHtml(skill.name)}</span>`;
  }).join("");
}

function evidenceBlock(job) {
  const entries = Object.entries(job.requirements_evidence || {});
  if (!entries.length) return "";
  return `<details class="evidence"><summary>查看未匹配技能的 JD 原文</summary><ul>${
    entries.map(([, evidence]) =>
      (evidence || []).slice(0, 2).map((line) => `<li>${escapeHtml(line)}</li>`).join("")
    ).join("")
  }</ul></details>`;
}

function jobCard(job, index) {
  const url = /^https?:\/\//.test(job.source_url || "")
    ? `<a class="job-link" href="${escapeHtml(job.source_url)}" target="_blank" rel="noopener">查看原始岗位</a>`
    : "";
  const freshnessLabel = job.active_status === "unknown"
    ? "状态待确认"
    : job.freshness_status === "fresh"
      ? "近期发布"
      : job.freshness_status === "recent"
        ? "有效期内"
        : "历史岗位";
  return `<article class="job-card">
    <div class="job-top">
      <div>
        <h3 class="job-title">${index + 1}. ${escapeHtml(job.job_title)}</h3>
        <div class="job-meta">
          <span>${escapeHtml(job.company)}</span>
          <span>${escapeHtml(job.city)}</span>
          <span>${escapeHtml(job.role_family_zh)}</span>
          <span>${escapeHtml(job.employment_type || "类型未知")}</span>
          <span>${escapeHtml(job.published_at || "时间未知")}</span>
          <span class="status-text"><i class="status-dot ${job.active_status === "unknown" ? "unknown" : job.freshness_status}"></i>${freshnessLabel}</span>
          <span>模型方向：${escapeHtml(roleNames[job.model_role] || job.model_role)} ${Math.round(job.model_confidence * 100)}%</span>
          ${url}
        </div>
      </div>
      <div class="score"><strong>${job.score}</strong><span>匹配分</span></div>
    </div>
    <div class="coverage-grid">
      <div class="coverage"><span>必备技能</span><strong>${job.required_coverage}%</strong></div>
      <div class="coverage"><span>加分技能</span><strong>${job.preferred_coverage == null ? "—" : `${job.preferred_coverage}%`}</strong></div>
      <div class="coverage"><span>方向核心</span><strong>${job.core_coverage}%</strong></div>
      <div class="coverage"><span>文本相似</span><strong>${job.text_similarity}%</strong></div>
      <div class="coverage"><span>模型一致度</span><strong>${job.model_alignment}%</strong></div>
    </div>
    <div class="skill-section">
      <div class="skill-row"><strong>已匹配</strong><div class="skill-cloud">${skillChips(job.matched_skills) || '<span class="muted">暂无明确匹配</span>'}</div></div>
      <div class="skill-row"><strong>简历中未找到</strong><div class="skill-cloud">${skillChips(job.missing_skills, "gap", true) || '<span class="muted">没有识别到必备技能缺口</span>'}</div></div>
    </div>
    <button class="job-feedback" type="button" data-job-id="${escapeHtml(job.jd_id)}">该岗位匹配不准确</button>
    <div class="inline-feedback" data-feedback-for="${escapeHtml(job.jd_id)}"></div>
    ${evidenceBlock(job)}
  </article>`;
}

function renderCustom(custom) {
  const box = $("#custom-result");
  if (!custom) {
    box.hidden = true;
    return;
  }
  const prediction = roleNames[custom.prediction.role_family] || custom.prediction.role_family;
  box.hidden = false;
  box.innerHTML = `
    <h3>自定义岗位分析</h3>
    <p class="muted">预测方向：${escapeHtml(prediction)} · 置信度 ${Math.round(custom.prediction.confidence * 100)}%
      ${custom.prediction.low_confidence ? " · 置信度较低，请核验" : ""}
      · 判定方式：${escapeHtml(custom.prediction.decision_method || "未知")}</p>
    <div class="custom-grid">
      <div class="metric-box"><strong>${custom.requirement_coverage}%</strong><span>必备技能覆盖</span></div>
      <div class="metric-box"><strong>${Math.round(custom.core_readiness.coverage * 100)}%</strong><span>方向核心能力</span></div>
      <div class="metric-box"><strong>${custom.missing_skills.length}</strong><span>未找到的技能</span></div>
    </div>
    <div class="skill-section">
      <div class="skill-row"><strong>已匹配</strong><div class="skill-cloud">${skillChips(custom.matched_skills) || '<span class="muted">暂无</span>'}</div></div>
      <div class="skill-row"><strong>简历中未找到</strong><div class="skill-cloud">${skillChips(custom.missing_skills, "gap", true) || '<span class="muted">暂无明显缺口</span>'}</div></div>
    </div>
    <div class="confirm-role">
      <label for="confirmed-role-select">方向识别有误？</label>
      <select id="confirmed-role-select">
        ${Object.entries(roleNames).map(([key, name]) =>
          `<option value="${key}" ${key === custom.prediction.role_family ? "selected" : ""}>${escapeHtml(name)}</option>`
        ).join("")}
      </select>
      <button class="secondary-button" id="confirm-role-button" type="button">确认方向并重新分析</button>
    </div>`;
  $("#confirm-role-button").addEventListener("click", async () => {
    confirmedCustomRole = $("#confirmed-role-select").value;
    await postFeedback({
      feedback_type: "role_corrected",
      corrected_role: confirmedCustomRole
    });
    analyze();
  });
}

async function analyze() {
  const roles = [...document.querySelectorAll('input[name="role"]:checked')].map((item) => item.value);
  if (!roles.length) {
    showError("请至少选择一个岗位方向。");
    return;
  }
  if (!resumeText.value.trim() && !resumeFile.files[0]) {
    showError("请粘贴简历文本或上传 PDF/DOCX/TXT 文件。");
    return;
  }

  $("#error-box").hidden = true;
  analyzeButton.disabled = true;
  analyzeButton.classList.add("loading");
  analyzeButton.querySelector(".button-label").textContent = "分析中";

  const form = new FormData();
  form.append("resume_text", resumeText.value);
  if (resumeFile.files[0]) form.append("resume_file", resumeFile.files[0]);
  roles.forEach((role) => form.append("roles", role));
  form.append("top_n", $("#top-n").value);
  form.append("custom_jd_text", $("#custom-jd").value);
  const city = $("#city-filter").value.trim();
  if (city) form.append("cities", city);
  const employmentType = $("#employment-filter").value;
  if (employmentType) form.append("employment_types", employmentType);
  const maxExperience = $("#experience-filter").value;
  if (maxExperience) form.append("max_experience_years", maxExperience);
  form.append("freshness_window", $("#freshness-filter").value);
  confirmedSkills.forEach((skill) => form.append("confirmed_skills", skill));
  if (confirmedCustomRole) {
    form.append("confirmed_custom_role", confirmedCustomRole);
  }

  try {
    const response = await fetch("/api/analyze", { method: "POST", body: form });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "分析失败");
    renderResults(data);
  } catch (error) {
    showError(error.message);
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.classList.remove("loading");
    analyzeButton.querySelector(".button-label").textContent = "开始分析";
  }
}

function showError(message) {
  const box = $("#error-box");
  box.textContent = message;
  box.hidden = false;
}

function renderResults(data) {
  $("#results").hidden = false;
  const profileSkills = Object.values(data.profile);
  const technical = profileSkills.filter((skill) => skill.technical);
  const names = data.role_families.map((key) => data.role_family_names[key]).join("、");
  $("#summary-text").textContent = `从简历中识别出 ${profileSkills.length} 项技能，其中 ${technical.length} 项为技术技能。当前分析方向：${names}。`;
  $("#profile-skills").innerHTML = profileSkills
    .sort((a, b) => Number(b.technical) - Number(a.technical) || a.name.localeCompare(b.name))
    .map((skill) => `<span class="skill-chip ${skill.technical ? "" : "soft"} ${skill.confirmed ? "confirmed" : ""}">${escapeHtml(skill.name)}${skill.confirmed ? " · 已确认" : ""}</span>`)
    .join("");

  const warnings = [
    ...(data.privacy_warnings || []),
    ...(data.filter_advice || [])
  ];
  $("#privacy-warnings").innerHTML = warnings
    .map((item) => `<div class="notice">${escapeHtml(item)}</div>`)
    .join("");

  renderCustom(data.custom_jd);
  const filters = [];
  if (data.filters?.cities?.length) filters.push(`城市：${data.filters.cities.join("、")}`);
  if (data.filters?.employment_types?.length) filters.push(`类型：${data.filters.employment_types.join("、")}`);
  if (data.filters?.max_experience_years != null) filters.push(`经验≤${data.filters.max_experience_years}年`);
  $("#result-meta").textContent = `筛选后 ${data.job_count} 条岗位${filters.length ? ` · ${filters.join(" · ")}` : ""} · ${data.elapsed_ms} ms`;
  $("#job-list").innerHTML = data.jobs.length
    ? data.jobs.map(jobCard).join("")
    : '<div class="card no-results">当前筛选条件下没有可匹配岗位，请放宽城市、招聘类型、经验或发布时间。</div>';
  $("#results").scrollIntoView({ behavior: "smooth", block: "start" });
}

function appendFilters(params) {
  document
    .querySelectorAll('input[name="role"]:checked')
    .forEach((item) => params.append("roles", item.value));
  const city = $("#city-filter").value.trim();
  if (city) params.append("cities", city);
  const employmentType = $("#employment-filter").value;
  if (employmentType) params.append("employment_types", employmentType);
  const maxExperience = $("#experience-filter").value;
  if (maxExperience) params.append("max_experience_years", maxExperience);
  params.append("freshness_window", $("#freshness-filter").value);
  return params;
}

function browserRow(job) {
  const source = /^https?:\/\//.test(job.source_url || "")
    ? `<a href="${escapeHtml(job.source_url)}" target="_blank" rel="noopener">来源</a>`
    : "";
  const status = job.active_status === "unknown"
    ? "状态待确认"
    : job.freshness_status === "fresh"
      ? "近期发布"
      : job.freshness_status === "recent"
        ? "有效期内"
        : "历史岗位";
  return `<article class="browser-row">
    <div>
      <h3>${escapeHtml(job.job_title)}</h3>
      <p>${escapeHtml(job.company)} · ${escapeHtml(job.city || "地点未明确")}</p>
    </div>
    <p>${escapeHtml(job.role_family_zh)} · ${escapeHtml(job.employment_type)} · ${escapeHtml(status)}</p>
    <div>${source}</div>
  </article>`;
}

async function browseJobs(reset = true) {
  if (browseLoading) return;
  browseLoading = true;
  const browseButton = $("#browse-button");
  browseButton.disabled = true;
  if (reset) {
    browsePage = 1;
    $("#browser-list").innerHTML = "";
  }
  const params = appendFilters(new URLSearchParams());
  params.append("page", String(browsePage));
  params.append("page_size", "20");
  $("#browser-status").textContent = "加载中";
  try {
    const response = await fetch(`/api/jobs?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "岗位加载失败");
    $("#browser-list").insertAdjacentHTML(
      "beforeend",
      data.jobs.map(browserRow).join("")
    );
    $("#browser-status").textContent = `共 ${data.total} 条，已显示 ${Math.min(browsePage * data.page_size, data.total)} 条`;
    $("#load-more-button").hidden = !data.has_more;
    if (data.has_more) browsePage += 1;
  } catch (error) {
    $("#browser-status").textContent = error.message;
  } finally {
    browseLoading = false;
    browseButton.disabled = false;
  }
}

analyzeButton.addEventListener("click", analyze);
$("#browse-button").addEventListener("click", () => browseJobs(true));
$("#load-more-button").addEventListener("click", () => browseJobs(false));

async function postFeedback(payload) {
  try {
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch (_) {
    // Feedback failure must not block the main matching workflow.
  }
}

$("#job-list").addEventListener("click", async (event) => {
  const feedbackButton = event.target.closest(".job-feedback");
  if (feedbackButton) {
    await postFeedback({
      feedback_type: "job_not_relevant",
      jd_id: feedbackButton.dataset.jobId
    });
    const message = document.querySelector(
      `[data-feedback-for="${feedbackButton.dataset.jobId}"]`
    );
    if (message) message.textContent = "已记录反馈，该岗位会在后续分析中降权。";
    feedbackButton.disabled = true;
    return;
  }

  const skillButton = event.target.closest("button.skill-chip.gap");
  if (skillButton) {
    const skillKey = skillButton.dataset.skillKey;
    const skillName = skillButton.dataset.skillName;
    if (!window.confirm(`确认您具备“${skillName}”这项技能吗？确认后会重新计算匹配结果。`)) {
      return;
    }
    confirmedSkills.add(skillKey);
    await postFeedback({
      feedback_type: "skill_confirmed",
      skill_key: skillKey
    });
    analyze();
  }
});

fetch("/api/health")
  .then((response) => response.json())
  .then((data) => {
    $("#job-count").textContent = data.jobs;
    $("#role-count").textContent = data.roles.length;
    $("#skill-count").textContent = data.skills;
    $("#city-options").innerHTML = data.cities
      .map((city) => `<option value="${escapeHtml(city)}"></option>`)
      .join("");
  })
  .catch(() => {});

