# JobMatch Agent

面向计算机与数据类求职者的岗位匹配与技能差距分析 Agent。系统从简历中提取技能，在本地岗位库中检索后端、前端、算法、嵌入式、数据分析、数据开发、测试开发和云原生岗位，并通过岗位分类模型、技能覆盖率和文本相似度生成可解释的岗位排序。

## 已实现功能

- 八类技术岗位识别与匹配；
- 简历技能提取与原文证据；
- 岗位必备技能、加分技能和团队核心能力分析；
- 岗位匹配度排序；
- 缺失技能提示与 JD 证据展示；
- 自定义 JD 方向和技能差距分析；
- PDF、DOCX、TXT 简历上传；
- 城市、招聘类型、经验年限和发布时间筛选；
- 岗位方向人工确认和“我具备该技能”反馈；
- 岗位不相关反馈会在后续排序中自动降权；
- 岗位库支持筛选和分页浏览；
- 简历只在当前请求内存中处理，不写入磁盘。

## 快速运行

```powershell
python -m pip install -r requirements.txt
# 可选：重新核验岗位链接是否仍有效
python scripts/audit_job_status.py
python scripts/prepare_data.py
python scripts/train_model.py
python scripts/evaluate_ranking.py
python app.py
```

打开 <http://127.0.0.1:5000>。

也可以直接运行：

```powershell
.\run.ps1
```

`run.ps1` 会在模型不存在时自动训练。

生成报告和验证复用的 Skill：

```powershell
python scripts/generate_report_figures.py
python scripts/generate_report.py
python scripts/generate_pdf_report.py
python scripts/check_frontend_design_skill.py
```

生成适合上传代码仓库的 ZIP：

```powershell
python scripts/package_repository.py
```

## 当前数据

`data/jobs_raw.jsonl` 保存 307 条原始结构；`data/jobs_clean.jsonl` 是训练和匹配实际使用的清洗版本，其中 222 条通过有效性和完整性检查：

- 后端开发：36 条；
- 前端开发：26 条；
- 算法工程师：35 条；
- 嵌入式开发：26 条；
- 数据分析：22 条；
- 数据开发/大数据：26 条；
- 测试开发：27 条；
- 云原生/DevOps/SRE：24 条。

`data/rejected_jobs.jsonl` 保存了新增材料中未通过完整性校验的 4 条记录，包含拒绝原因，不参与匹配和训练。

清洗脚本会处理职责/要求前的解析标点，识别多职位拼接、重复岗位、省级地点、缺失日期和过期数据。岗位链接会重新访问，明确显示“已过期/已下线”的记录不会进入匹配库。数据质量报告位于 `models/data_quality_report.json`。

数据来源和字段定义见项目外的 `../JD_数据说明.md`。来源页面没有明确开放数据许可证，当前数据只用于课程项目分析，不应直接作为开放数据集再次分发。

## 机器学习部分

八类岗位均已达到每类至少 5 条的训练门槛。岗位分类器输入岗位职责和任职要求，不直接把岗位标题作为特征，避免标题泄漏。

- 特征：字符级 TF-IDF，2—5 gram，sublinear TF；
- 基线：Multinomial Naive Bayes；
- 主模型：class-balanced Logistic Regression；
- 验证：按公司分组的 5 折交叉验证，随机分层 5 折结果作为泄漏风险参考。

训练时对“公司 × 岗位类别”最多保留 4 条，减少单一公司相似模板的影响。222 条可匹配岗位经平衡后得到 134 条训练样本，分组验证结果：

- Naive Bayes：Accuracy 0.5000，Macro-F1 0.3844；
- Logistic Regression：Accuracy 0.8657，Macro-F1 0.8550。

随机分层参考中的主模型 Macro-F1 为 0.8142，与分组验证接近，说明公司级去重后指标更可信。混淆矩阵显示，云原生和测试开发仍有少量跨方向误分类。

技能抽取目前采用可解释的规则词典，覆盖 41 个技能/能力标签。用户可以在结果页手动确认“我具备该技能”，确认后的技能会重新参与排序。岗位方向分类器同时参与自定义 JD 判定和本地岗位匹配分计算。

训练时会限制同一公司在同一岗位类别下的样本数，避免腾讯等单一来源占比过高。结果展示也会限制同公司岗位占位，并应用用户标记的“不相关”反馈。

## 匹配公式

```text
匹配分 =
    0.15 × 必备技能覆盖率
  + 0.60 × 必备技能命中强度
  + 0.05 × 加分技能覆盖率（有加分项时）
  + 0.05 × 目标方向核心能力
  + 0.05 × 简历与岗位文本相似度
  + 0.10 × 岗位分类模型方向一致度
```

如果岗位没有加分项，对应权重会自动重新归一化。方向核心能力低于 50% 时还会进一步降低得分。分数表示当前简历对岗位要求的覆盖程度，不代表录用概率。

## 排序评估

`scripts/evaluate_ranking.py` 使用 16 个覆盖八类岗位的求职者画像，比较关键词、TF-IDF 和 Agent 混合排序：

| 方法 | Precision@3 | Recall@5 | NDCG@5 |
|---|---:|---:|---:|
| 关键词基线 | 0.9259 | 0.3939 | 0.8927 |
| TF-IDF 基线 | 0.9630 | 0.3989 | 0.8948 |
| Agent 混合排序 | 1.0000 | 0.3984 | 0.9291 |

共 16 个画像，其中 9 个筛选后的候选岗位不少于 5 条，参与主指标汇总；其余候选过少的画像只在明细中展示。29 个 query-job 对已经经过 AI 辅助复核，但仍应由团队成员确认真实求职者偏好。

详细结果位于 `models/ranking_metrics.json`，20% 抽样的复核表位于 `models/relevance_review_template.csv`。

## 提交材料

- `reports/项目报告_待填写个人信息.docx`
- `reports/项目报告_待填写个人信息.pdf`
- `reports/复用组件与复现说明.pdf`
- `reports/提交清单.pdf`
- `demo/DEMO_GUIDE.md`
- `demo/*.txt` 示例简历与自定义 JD
- `THIRD_PARTY_NOTICES.md`

复用开源 Skill 的说明位于 `third_party/SKILL_USAGE.md`。本项目复用 Apache-2.0 许可的 `frontend-design` Skill，并通过 `scripts/check_frontend_design_skill.py` 执行确定性质量检查。

## 项目结构

完整目录和文件用途见 `PROJECT_STRUCTURE.md`。以下为便于快速定位的简表。

```text
job_match_agent/
├─ app.py                         # Web 入口
├─ run.ps1                        # 一键启动
├─ requirements.txt              # 依赖
├─ README.md
├─ PROJECT_STRUCTURE.md           # 完整目录索引
├─ agent/
│  ├─ core.py                     # Agent 工作流
│  ├─ data.py                     # 岗位库
│  ├─ documents.py                # 简历解析
│  ├─ matcher.py                  # 匹配与排序
│  ├─ model.py                    # 岗位分类模型
│  └─ skills.py                   # 技能规则与证据
├─ config/
│  └─ skills.json                 # 技能词表和方向能力
├─ data/
│  ├─ jobs_clean.jsonl            # 可匹配岗位
│  ├─ jobs_raw.jsonl              # 原始快照
│  ├─ rejected_jobs.jsonl         # 拒绝记录
│  ├─ job_status_audit.jsonl      # 链接核验
│  └─ evaluation_personas.json    # 评估画像
├─ models/
│  ├─ role_classifier.joblib      # 分类模型
│  ├─ metrics.json                # 分类指标
│  ├─ ranking_metrics.json        # 排序指标
│  ├─ relevance_review_*.csv      # 复核表
│  ├─ data_quality_report.json    # 数据质量
│  └─ frontend_skill_report.json  # 前端检查
├─ scripts/
│  ├─ audit_job_status.py
│  ├─ prepare_data.py
│  ├─ train_model.py
│  ├─ evaluate_ranking.py
│  ├─ generate_report_figures.py
│  ├─ generate_report.py
│  ├─ generate_pdf_report.py
│  ├─ package_submission.py
│  └─ check_frontend_design_skill.py
├─ static/                        # CSS 与前端逻辑
├─ templates/                     # HTML 页面
├─ tests/                         # 自动化测试
├─ demo/                          # 演示指南和示例简历
├─ reports/                       # 报告、复用说明、清单
│  └─ figures/                    # 报告图
├─ third_party/                   # Skill 原文、许可证、复用说明
└─ THIRD_PARTY_NOTICES.md         # 第三方组件清单
```

## API

### `GET /api/health`

返回服务状态、岗位数量和岗位方向。

### `GET /api/metrics`

返回岗位分类模型的交叉验证指标。

### `GET /api/ranking-metrics`

返回岗位排序的 Precision@3、Recall@5 和 NDCG@5 对比结果。

### `GET /api/jobs`

分页浏览有效岗位，支持岗位方向、城市、招聘类型、经验和发布时间筛选。返回 `total`、`page`、`has_more` 和当前页岗位列表。

### `POST /api/analyze`

表单字段：

- `resume_text`：简历文本；
- `resume_file`：可选，PDF、DOCX 或 TXT；
- `roles`：可重复字段，支持八个岗位方向；
- `top_n`：返回岗位数；
- `custom_jd_text`：可选的自定义 JD。
- `cities`：可选城市；
- `employment_types`：实习、校招或社招；
- `max_experience_years`：最高经验年限；
- `freshness_window`：`1y`、`2y` 或 `all`；
- `confirmed_skills`：用户确认具备的技能；
- `confirmed_custom_role`：用户确认的自定义 JD 方向。

### `POST /api/feedback`

记录岗位不相关、技能已具备或岗位方向已修正的反馈。反馈不包含简历原文。

## 测试

```powershell
python -m unittest discover -s tests -v
```

当前 15 项测试全部通过，覆盖筛选、八分类、技能确认、排序降权、岗位浏览、反馈写入、PDF 上传和 API。

## 已验证与未验证

已验证：

- 222 条可匹配岗位可以加载；
- 八分类模型可以训练、保存和推理；
- 简历技能抽取可以返回证据；
- 岗位按照技能覆盖、模型一致度和用户筛选条件排序；
- Web API 可以返回岗位结果；
- 自定义 JD 可以预测岗位方向。

尚未解决：

- 数据量不足，正式训练集还需要继续扩充；
- 数据来源仍以高校就业网和腾讯官方招聘为主，岗位发布时间跨度较大；
- 技能抽取依赖词典，同义表达可能漏检；
- 扫描图片型 PDF 没有可直接提取的文字，仍需要用户先做 OCR 或粘贴文本；
- 排序评估已建立，但相关性标签仍是半自动 silver label；
- 岗位数据来源没有开放许可，公开仓库时应移除完整 JD 原文。

## 学术诚信与安全边界

- 不自动投递、不修改原简历、不伪造项目经历；
- 不把模型分数解释为录用概率；
- “简历中未找到”不代表候选人不会该项技能；
- 高风险或低置信度结果应由用户人工确认；
- 使用岗位数据和第三方组件时，应在最终报告中记录来源、日期与许可。

