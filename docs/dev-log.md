# alpha-jerry 开发日志

## 总结

### M0 - 1

- `CHANGELOG` 建好版本记录习惯

- uv 替代 pip 做包管理更快更稳
- pytest 分 mock/network 两组标记隔离网络依赖
- ruff 一次配齐格式+lint
- hatchling 构建让 `uv run` 零配置导入 `src` 包
- Settings 单例、默认值、数据目录自动创建，数据子目录不手动建、不入库，由代码运行时自动创建，这样目录结构跟随数据生命周期，不污染版本库

- GitHub Actions 用 `astral-sh/setup-uv@v5` 自动装 Python 并同步依赖；CI 三步流水线（format→lint→pytest）阻断不合规提交


- `BaseFetcher` 抽象基类做依赖倒置，未来换数据源只改适配层；`StockFeatures(extra="allow")` 让 VIP 接口 ~460 字段动态接受，无需逐个声明；`REQUIREMENT_ALIGNMENT(53项)` 做需求追溯，`FIELD_CN/FIELD_UNIT` 全量映射做中文翻译与单位格式化


- CSV 显示给用户看时才是中文（`FIELD_CN` 映射做一道翻译），但数据层和存储层的"事实"永远是 Tushare 的原始字段名，不做二次加工。用户看到的永远是经过翻译的，即原始数据保证真实
- 追加字段不破坏原字段
- 数据来源 CSV 列出接口/字段/中文/文档 URL 实现全链可追溯

- 先定义"接口"再写"实现"，未来换数据源时减少业务代码修改
- 失败隔离：一只股票出错不能拖垮整体，记下来后续采集

- 时间复杂度：**能批量就不逐股，能缓存就不调 API**，一次调用拿全市场数据 O(1) 而非逐股询问 O(n)，照顾中低性能电脑
- 流式写入：每 500 行存一次，防止 5000+ StockFeatures 同时驻留撑爆内存
- 断点续采：从断掉的地方接着写，让中断不白跑，已完成的接口跳过不重复调
- 性能配置：让低配机器自行调低并发和批次大小
- 分页处理：接口可能按 offset/limit 分页返回，一次拿不完，就分几次搬，循环收集直到数据集完整

- IO 耦合：测试非得连网/读盘/打日志，缺一样就报错
- IO 解耦：把 IO 操作从核心逻辑中分离，使得核心逻辑可以被测试而减少依赖真实的 IO / 减少 IO 行数
  - 几十行的 print，解耦成组装和写入两步骤，先把输出内容拼好（返回一个字符串或列表）
- mock：用假的代替真的
- IO 不好覆盖测试：mock 了代码才能被跑到，不 mock 就跳过，mock 了也只是测"假数据"，不是真实的 IO

### M2

- 纯函数最好测，给相同输入永远得相同输出，不碰网络/文件/时间
- 边界值测试：如 8.5、7.0、5.5 这些临界点最容易出错，必须专门测

**值得关注的点**：

1. **数据是 Q1 单季度**（20260331 报告期）——季度数据天然比年报波动大，营收/利润增速有季节性扭曲
2. **缺失维度压低部分得分**——`score_stability` 缺审计意见、`score_return` 缺分红率和 PEG，有效维度少使个别低分项的拖累更大
3. **阈值未分行业差异化**——所有行业用同一套分数阈值，但资产负债率 60% 对银行和对科技公司意义完全不同

**判断**：策略逻辑本身没问题，但等年报数据（20251231 报告期）出来后分布可能会更合理。不是代码的问题，是数据阶段和阈值严格度的叠加效应。

### M3

- LLM 适配层做依赖倒置，业务代码不直接依赖 DeepSeek SDK
- mock 测试验证调用参数正确
- 增强系统提示：`src/reports/reporting.py:196` — `_generate_single` 函数内的 `chat_completion` 调用
- **该高的必须高**：`scores.py` 100%（RIGID 规则，全部阈值边界必测）
- **该低的低也没事**：`reporting.py` 22%（LLM 相关，mock 它没意义，靠 network 测试真跑验证）
- **这项目当前 89% 足够**：核心业务逻辑（评分/评级/否决/权重）全覆盖，I/O 层够用即可
- IO 进集成保单测

1. **`reasoning=False` → `True`** — 最大单点提升。不用阉割版模型。
2. **max_tokens 80→300 / max_chars 30→120** — 给足输出空间，消除截断。
3. **system prompt 去编号化** — 删除"规则1/2/3"，改为自然角色描述；编号格式是元推理触发器。
4. **prompt 与 field_set 对齐** — `_RISK_FIELDS` 补 `roe`+`free_cashflow`；user prompt 不再提及模型看不到的字段。
5. **软化数据约束** — "每句必须带数据"→"有数据优先用数据，无数据直接写评分结论"。缺数据时模型不再崩溃自语。
6. **`clean_llm_output` 正则扩军** — `_RE_NOISE` 追加 20+ 元推理模式（排查/规则/这里/那么/或许/有可能/只能/否则）；`_RE_HAS_CONTENT` 扩展 30+ 关键词；`clean_llm_output` 入口剥中文引号。

## 待定

- [ ] 校验成果
- [ ] 对齐 dev、RM
- [ ] 如果没有，层层新建
- [ ] 双端目录
- [ ] 更新 AG、RD

- [ ] quanttide/qtdata

- [ ] 模型参数
  - [ ] 思考深度
- [ ] 已完成的步骤中未实现的功能
- [ ] Tushare skill
- [ ] 先指引用户生成本地数据基础
- [ ] 老王的 DS 账号替换 Key
- [ ] 系统提示规范和准确性提高的思路

- [ ] 知识产权保护
- [ ] 法律风险
- [ ] 评审：果哥、昂哥、哥、郑哥
- [ ] 更合适的语言

## 参考资料

- [openclaw 源码解读和开发文档范例](https://www.moely.ai/resources/openclaw-framework-source-code-review)
- [RAG 公众号 * 2](https://mp.weixin.qq.com/s/t20kNKfMgdnUmUsD603p7g)
- [网页](https://wikimind.top/)
- [界面](https://quanttide.github.io/qtcloud-devops/)
- https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SZ000679&color=b#/cwfx