# alpha-jerry 开发日志

### 总结

#### M0 - 1

- 数据子目录不手动建、不入库，由代码运行时自动创建，这样目录结构跟随数据生命周期，不污染版本库
- CSV 显示给用户看时才是中文（`FIELD_CN` 映射做一道翻译），但数据层和存储层的"事实"永远是 Tushare 的原始字段名，不做二次加工。用户看到的永远是经过翻译的，即原始数据保证真实

- 先定义"接口"再写"实现"，未来换数据源时减少业务代码修改

- 失败隔离：一只股票出错不能拖垮整体，记下来后续采集
- 集成测试：真实网络的测试，单元测试：mock 掉网络
- 冒烟测试：用最小代价验证主链路通不通

- 时间复杂度：**能批量就不逐股，能缓存就不调 API**，一次调用拿全市场数据 O(1) 而非逐股询问 O(n)，照顾中低性能电脑
- 流式写入：每 500 行存一次，防止 5000+ StockFeatures 同时驻留撑爆内存
- 断点续采：从断掉的地方接着写，让中断不白跑，已完成的接口跳过不重复调
- 性能配置：让低配机器自行调低并发和批次大小
- 分页处理：接口可能按 offset/limit 分页返回，一次拿不完，就分几次搬，循环收集直到数据集完整

## 待定

- [ ] 基于素材提炼各主要文件规范
- [ ] 知识产权保护
- [ ] 法律风险
- [ ] 评审：果哥、昂哥、哥、郑哥
- [ ] 小红书收藏购物车
- [ ] 需求编程的 agent

## 参考资料

- [openclaw 源码解读和开发文档范例](https://www.moely.ai/resources/openclaw-framework-source-code-review)
- [RAG 公众号 * 2](https://mp.weixin.qq.com/s/t20kNKfMgdnUmUsD603p7g)
- [网页](https://wikimind.top/)
- [界面](https://quanttide.github.io/qtcloud-devops/)
- https://tushare.pro/document/2
- https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SZ000679&color=b#/cwfx