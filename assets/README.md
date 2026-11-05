# 素材目录说明

把素材放到这里，游戏会自动加载；**没有的素材会自动回退成占位色块/合成音**，所以可以一份份慢慢替换。

## 目录结构

```
assets/
├── manifest.json          # 可选：逻辑名 -> 自定义文件（一般不用改）
├── images/
│   ├── characters/        # 主角
│   │   └── player.png
│   ├── companions/        # 伙伴（按名字）
│   │   ├── 艾琳.png
│   │   ├── 古德.png
│   │   └── 露娜.png
│   ├── npcs/              # 城镇 NPC（按名字）
│   │   ├── 艾琳.png
│   │   ├── 古德.png
│   │   └── 露娜.png
│   ├── monsters/          # 怪物（按 monster_id）
│   │   ├── slime.png
│   │   ├── bat.png
│   │   ├── goblin.png
│   │   ├── wolf.png
│   │   ├── spider.png
│   │   ├── ghost.png
│   │   ├── skeleton.png
│   │   ├── troll.png
│   │   └── demon.png
│   ├── events/            # 事件插画
│   │   └── wounded.png
│   └── items/             # 物品图标（可选，暂时未接 UI）
│       ├── potion.png
│       └── ...
├── audio/
│   ├── bgm/               # 背景音乐（.ogg）
│   │   ├── town.ogg
│   │   ├── dungeon.ogg
│   │   └── battle.ogg
│   └── sfx/               # 音效（.wav）
│       ├── hit.wav
│       ├── crit.wav
│       ├── heal.wav
│       ├── hurt.wav
│       └── victory.wav
└── fonts/
    └── main.ttf           # 中文字体（可选）
```

## 命名规则

- **逻辑名 = 相对 `images/` 的路径去掉 `.png`**。例如 `images/monsters/slime.png` 的逻辑名是 `monsters/slime`。
- 游戏里的调用是 `assets.sprite("monsters/slime", 颜色, 尺寸)`：找到图就用图，找不到就用色块。

## 尺寸建议

| 类型 | 建议尺寸 |
|------|----------|
| 主角 / 伙伴 / NPC | 128×128 或 256×256（程序会缩放到 120/96） |
| 怪物 | 128×128（程序缩放 100/96/64） |
| 事件插画 | 256×256 |
| 物品图标 | 32×32 或 48×48 |

> 程序会 `pygame.transform.scale` 到目标尺寸，所以**不必严格按尺寸**，但保持正方形、透明背景（PNG）效果最好。

## 音效 / 音乐

- 音效放 `audio/sfx/<名>.wav`，名与代码里的 `sound.play("hit")` 等对应。
- BGM 放 `audio/bgm/<名>.ogg`。
- **没有音频文件时**，游戏用正弦波合成简单的打击/治疗音（`pygame_game/sound.py`），不会静音报错。

## 字体

- 放 `assets/fonts/main.ttf`，程序会优先用它；没有就用系统里的微软雅黑等。

## 怎么替换

1. 把图片按上面的路径丢进去（比如 `images/monsters/slime.png`）。
2. **不用改代码**，重启游戏即可生效。
3. 想用自定义文件名，就在 `manifest.json` 里加一条：
   ```json
   {
     "monsters/slime": { "image": "images/monsters/slime_v2.png" }
   }
   ```
