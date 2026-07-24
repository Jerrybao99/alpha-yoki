# alpha-jerry 开发日志

### 总结

- 数据子目录不手动建、不入库，由代码运行时自动创建，这样目录结构跟随数据生命周期，不污染版本库
- 先定义"接口"再写"实现"，未来换数据源时减少业务代码修改
- 失败隔离：一只股票出错不能拖垮整体，记下来后续采集
- 集成测试：真实网络的测试，单元测试：mock 掉网络
- 冒烟测试：用最小代价验证主链路通不通

## 待定


- [ ] 低性能电脑下，高速采集全量 A 股市场数据，文件格式，缓存和性能搭配策略
- [ ] 大数据下怎么验证数据普遍可靠？
- [ ] 总结精华和设计巧思
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