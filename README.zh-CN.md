# shotline

把 App Store 宣传图做成一条流水线：从模拟器**拍**真实画面，配上文案**合成**商店尺寸的图，用硬性规则**检查**，**上传**到 App Store Connect，再**核验**确实到位。

每个 app 一个 JSON。不用设计软件，不用写 UI 测试，不改 app 代码。

[English](README.md) · [完整方法论（英文）](docs/METHOD.md)

![VisaScout 中文 iPhone 组图](examples/visascout/sheet-zh-iphone.png)

## 安装与用法

```bash
pip install git+https://github.com/Hellotravisss/shotline
```

```bash
shotline capture -c shotline.json            # 模拟器 → raw/
shotline compose -c shotline.json            # raw/ + 文案 → out/
shotline check   -c shotline.json            # 检查 + 缩略图总览 out/sheet-*.png
shotline ship    -c shotline.json --version 1.4.0      # 上传并核验
shotline submit  -c shotline.json --version 1.4.0      # 核验通过才提交审核
```

依赖：macOS + Xcode、Google Chrome、Python 3.10+（只用标准库）；拍摄步骤要点击或滑动时需要 [AXe](https://github.com/cameroncooke/AXe)。App Store Connect 密钥只从环境变量读（`ASC_KEY_ID`、`ASC_ISSUER_ID`、`ASC_KEY_PATH`），不写进配置文件。

配置格式见 [README.md](README.md#shotlinejson)，完整示例见 [examples/visascout/shotline.json](examples/visascout/shotline.json)。

## 方法论

五个阶段，每个阶段有一道关。关过了才算完成，不是「看起来差不多」就算。

### 1. 构思：先定每张图卖什么

- **一张图只讲一件事。** 标题里需要「和」，就该拆成两张。
- **先卖结果，再给证据。** 标题写用户得到什么（「你的护照能免签去哪？」），截图是证据，副标题讲怎么做到。写功能名（「探索页面」）等于浪费一张图。
- **前三张就是全部。** 搜索结果只露三张，大多数人不会往后滑。第 1 张放最强的承诺，第 2 张放最具体的数字，第 3 张放对手没有的东西。
- **每行 3–5 个词，两行为限。** 自动缩字是文案的问题，该改文案，不该缩字。
- **只强调一个词。** 标题里 `*词*` 会加强调色块，一个标题只用一次。
- **每个说法都要在它下面那张截图上成立。** 标题写「43 国」，截图里就必须是 43。数据更新后数字会变：重拍，不要改数字。
- **每张配一句可核实的信任信号。** 「每条都附官方来源」「199 个国家和地区」「签证数据每月更新」。不编评分、不编用户数、不编媒体评价。
- **图上的文字会被搜索收录。** 2025 年起 Apple 会识别截图文案并参与搜索。用用户真正会搜的词，每个语言单独写，不要直译。
- **遮住截图读一遍。** 只按顺序读标题，应该能讲清这个 app 是干什么的。
- **最后一张用「工具墙」收尾，不要再放一台手机。** 连续五个手机框，眼睛就不看了。最后一张用大字列出其他功能（`wall`），或一次放三屏（`mosaic`）。
- **版式要错开。** `hero`（文字在上、手机出底）、`device-top`（手机出顶、文字在下）、`tilted`（倾斜）、`wall`、`mosaic`，相邻两张不要同一个轮廓。

### 2. 拍摄：真 app、真数据、可重复

- **用 Release 包拍。** Debug / 开发版会带调试浮层和悬浮按钮。
- **状态栏统一。** 9:41、满格信号、Wi-Fi、电量 100% 且**未充电**（充电会显示闪电）。
- **冷启动再开深链接。** 每张图都先关掉 app、重新启动、再打开链接：同一路由的深链接常常不刷新；app 在前台时打开链接，也不会弹「在 xxx 中打开？」。
- **状态用写入，不要靠点击。** 填表单、转日期选择器是拍摄脚本里最不稳定的部分。启动前直接写入状态：`mergeJson` 写进 app 数据目录（React Native 的 AsyncStorage 在 `Library/Application Support/<bundle>/RCTAsyncLocalStorage_V1/manifest.json`），原生 app 用 `defaults`。app 自带语言设置时，这样切语言比 `-AppleLanguages` 可靠。
- **能用深链接就不点，能点就不滑。** 坐标单位是 point，每台设备不同，`tap` 支持 `{"iphone": [x,y], "ipad": [x,y]}`；坐标用 `axe describe-ui` 查。
- **滑动要慢。** 3 秒的拖动停在哪就是哪；快速一甩，截图之后还在滚。
- **只用真实数据。** 不造数字、不放假人、不写占位文字。
- **每张原图都要看。** 内容 bug 在这一步暴露：中文界面里冒出一段英文、中文里的半角标点、被截断的标签。修 app，或者换一个例子，不要在合成时遮掉。
- **iPad 必须用 iPad 画面。** 手机图套 iPad 框会被拒，也难看。app 的 iPad 版如果只是拉宽的手机界面，图上也藏不住，要改的是 app。
- **原图进 git。** 原图很贵，而且常常无法复现（数据变了、账号过期了）。`out/` 随时能从原图 + 配置重新生成。

### 3. 合成：文案和版式在一个 JSON 里，由浏览器渲染

图是 HTML，用无界面 Chrome 按商店尺寸渲染：字是真字（字距、中文字体、表情符号都对），排版是 CSS。渲染完模板会回报哪一行被缩了字、哪里溢出。

**中文排版：** 用全角标点（，。？：）；中文与英文、数字之间加空格（`免签 43 国`、`申根 90/180 天`）。全角字符直接输入，或写成 `，` 这样的转义，别让编辑器替换成半角。

**主题只是起点。** 自带 `brutal`（纯色底、硬阴影）和 `editorial`（纸色底、衬线标题），`theme` 里可覆盖任意变量。宣传图的视觉应该和 app 本身一致。

### 4. 检查：出门前过关

`shotline check` 会**拦下**：尺寸不是商店要求的精确像素；文字超出画布，或文字挤得手机放不下。
会**警告**：标题被自动缩字（当作文案 bug 处理）；PNG 带透明通道。

它会生成 `out/sheet-<语言>-<设备>.png`：每张图缩到约 200 像素宽，也就是搜索结果里的大小。**看缩略图，不要看原尺寸。** 缩略图上读不清的标题，就是不成立。

### 5. 上传：传完要证明真的到了

- **审核中截图是锁定的。** `ship --cancel-review` 会把版本从审核里撤回（状态变 `DEVELOPER_REJECTED`）才能替换，代价是重新排队，要想清楚再用。
- **整组替换。** 每组先删再按顺序全部重传，局部修改会留下旧图。
- **逐组核验。** 每次上传都可能返回 200，之后处理却失败；处理也可能要好几分钟。`ship` 结束时会重新读取每个语言 × 设备的组，要求文件名、顺序完全一致且全部 `COMPLETE`。没处理完的组会在这里暴露，再跑 `verify` 直到通过。
- **核验通过才提交审核。** `shotline submit` 不通过就拒绝提交。提交审核是对外动作，所以单独一条命令。

## 致谢

构思部分的规则来自两个开源项目，再加上我们实际上架时踩过的坑：

- [ParthJadhav/app-store-screenshots](https://github.com/ParthJadhav/app-store-screenshots)：一图一事、短标题、错开版式、收尾页、缩略图测试。
- [framara/app-store-screenshots-skill](https://github.com/framara/app-store-screenshots-skill)（Scrnsht Studio）：从调研出卖点、卖结果、遮图测试、每张都有可信信号、上传后核验。
- [cameroncooke/AXe](https://github.com/cameroncooke/AXe)：在模拟器里点击和滑动。

## 许可证

MIT
