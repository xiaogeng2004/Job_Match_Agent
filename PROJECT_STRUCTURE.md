# 项目目录说明

本项目按“应用入口、业务代码、配置与数据、模型产物、脚本、界面、测试、演示、报告、第三方材料”分类。核心运行路径保持稳定，移动文件前应同步修改 README、报告和脚本中的引用。

## 目录树

```text
job_match_agent/
├─ app.py                         # Flask Web 入口与 API
├─ run.ps1                        # Windows 一键启动脚本
├─ requirements.txt              # Python 运行与报告生成依赖
├─ README.md                      # 安装、运行、功能和复现说明
├─ PROJECT_STRUCTURE.md           # 本目录索引
├─ agent/                         # Agent 业务代码
│  ├─ core.py                     # 工作流编排与对外分析接口
│  ├─ data.py                     # 本地岗位库加载和筛选
│  ├─ documents.py                # PDF、DOCX、TXT 简历解析
│  ├─ matcher.py                  # 技能覆盖、可解释评分与排序
│  ├─ model.py                    # 岗位分类模型加载与推理
│  └─ skills.py                   # 技能词表匹配、证据和能力组
├─ config/
│  └─ skills.json                 # 41 个技能标签、方向核心能力和同义词规则
├─ data/                          # 输入与评估数据
│  ├─ jobs_raw.jsonl              # 原始岗位快照
│  ├─ jobs_clean.jsonl            # 当前可匹配岗位
│  ├─ rejected_jobs.jsonl         # 未通过完整性校验的岗位及原因
│  ├─ job_status_audit.jsonl      # 岗位链接活跃状态核验结果
│  └─ evaluation_personas.json    # 排序评估画像
├─ models/                        # 训练产物和实验记录
│  ├─ role_classifier.joblib      # 岗位分类模型
│  ├─ metrics.json                # 分类指标与混淆矩阵
│  ├─ ranking_metrics.json        # 排序基线、混合排序指标与明细
│  ├─ relevance_review_*.csv      # 排序抽样复核表
│  ├─ data_quality_report.json    # 数据质量统计
│  └─ frontend_skill_report.json  # 前端设计 Skill 检查结果
├─ scripts/                       # 可重复执行的数据、模型、报告和打包脚本
│  ├─ audit_job_status.py         # 核验岗位链接状态
│  ├─ prepare_data.py             # 清洗和准备岗位数据
│  ├─ train_model.py              # 训练与交叉验证
│  ├─ evaluate_ranking.py         # 排序基线和 Agent 对比
│  ├─ generate_report_figures.py  # 从模型 JSON 生成报告图
│  ├─ generate_report.py          # 生成 DOCX 报告
│  ├─ generate_pdf_report.py      # 生成 PDF 文档
│  ├─ package_submission.py       # 生成提交 ZIP
│  └─ check_frontend_design_skill.py # 复核复用的前端 Skill
├─ static/                        # 前端样式和交互脚本
├─ templates/                     # Flask HTML 模板
├─ tests/                         # 自动化测试
├─ demo/                          # 演示指南、三类简历和自定义 JD
├─ reports/                       # 报告源文件与最终提交材料
│  └─ figures/                    # 报告图：工作流、混淆矩阵、排序指标
└─ third_party/                   # 外部 Skill 原文、许可证和复用说明
   └─ skills/frontend-design/     # 固定版本的上游 Skill
```

## 文件用途

| 目标 | 首先查看 |
|---|---|
| 了解并运行系统 | `README.md` |
| 修改 Agent 流程 | `agent/core.py` |
| 修改匹配或排序 | `agent/matcher.py`、`config/skills.json` |
| 重新训练岗位分类器 | `scripts/train_model.py` |
| 重新运行排序实验 | `scripts/evaluate_ranking.py` |
| 查看实验指标 | `models/metrics.json`、`models/ranking_metrics.json` |
| 修改报告正文 | `reports/项目报告.md` |
| 重新导出报告 | `scripts/generate_report.py`、`scripts/generate_pdf_report.py` |
| 查看 Skill 来源和许可证 | `third_party/SKILL_USAGE.md`、`third_party/skills/frontend-design/` |
| 运行提交前验证 | `tests/test_agent.py` |

## 本地缓存和运行数据

以下路径不属于核心项目内容，已通过 `.gitignore` 和打包脚本排除：

- `.deps/`：当前环境安装的本地依赖；
- `work/`：报告页面检查产生的临时目录；
- `__pycache__/`：Python 字节码缓存；
- `data/feedback.jsonl`：运行时反馈，不包含简历正文，也不进入提交包。

## 推荐操作顺序

```powershell
python -m pip install -r requirements.txt
python scripts/audit_job_status.py
python scripts/prepare_data.py
python scripts/train_model.py
python scripts/evaluate_ranking.py
python -m unittest discover -s tests -v
python scripts/check_frontend_design_skill.py
python scripts/generate_report_figures.py
python scripts/generate_report.py
python scripts/generate_pdf_report.py
python scripts/package_submission.py
python app.py
```

最终访问地址为 <http://127.0.0.1:5000>。报告、复用说明和提交清单位于 `reports/`。
