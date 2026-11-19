# 桌宠素材来源与署名

`whale-girl-open.png` 和 `whale-girl-blink.png` 是 `assets/pet/` 里桌宠用的两帧
（睁眼 / 闭眼），由 `tools/build_pet_assets.py` 生成。

## 来源

- 原始素材：[YunYueSama/codex-deepseek-pet](https://github.com/YunYueSama/codex-deepseek-pet) 的
  `assets/whale/idle-front.png`（一张左右两帧的透明底图：左睁眼、右闭眼）。
- 作者：YunYueSama
- 仓库：https://github.com/YunYueSama/codex-deepseek-pet

## 本项目的修改

- 从 `idle-front.png` 里左右切出两帧，用同一裁切框对齐，保证眨眼时不位移；
- 四周留 10px 空白，脚下加了一层很淡的椭圆阴影；
- 运行时按屏幕 DPI 缩放到约 210dp 高，预乘 alpha 后交给分层窗口绘制；
- 角色造型、配色、动作都没有改动。

修改后的两帧同样按下面的许可提供。

## 许可

素材使用「大肥鱼项目署名许可 1.0」（自定义许可，非标准 MIT）：

- 完整许可文本：[LICENSE-YunYueSama.txt](LICENSE-YunYueSama.txt)
- 素材范围说明（含第三方参考与边界）：[ASSET_LICENSE.md](ASSET_LICENSE.md)

要点：允许使用、修改、再分发（含商用），须保留上面的作者与仓库地址，分发时一并保留许可全文，并说明修改过。

## 角色来历

「鲸鱼娘 / 大肥鱼」是 DeepSeek 社区的拟人二创形象，社区里常见的原型作者包括
上善无形（上善）和 ZipZipPipe 等，见
[xiaoweigen/deepseek-dafeiyu-assets](https://github.com/xiaoweigen/deepseek-dafeiyu-assets)
的署名表。上面的许可只覆盖 YunYueSama 有权授权的部分，不替代角色原型可能需要的授权。

本项目只是个人自用的桌面时间表工具，与 DeepSeek 官方无关，也不代表官方认可。
