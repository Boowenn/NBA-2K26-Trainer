# NBA 2K26 Trainer - 球员属性修改器

一款基于 Python + PyQt5 的 NBA 2K26 经理模式球员属性修改器，通过读写游戏进程内存实现实时修改。

## 功能特性

- **球员浏览** — 扫描游戏内存中的球员列表，支持按姓名搜索和球队筛选
- **全属性编辑** — 修改球员的所有属性，包括：
  - 基本信息：年龄、身高、体重、位置、球衣号码
  - 进攻能力：投篮、控球、传球、扣篮等
  - 防守能力：内线防守、外线防守、抢断、盖帽等
  - 体能属性：速度、力量、弹跳、耐力等
  - 篮球智商：进攻/防守意识
  - 潜力与成长：潜力值、巅峰年龄、发展特质
  - 合同：年薪、合同年限
  - 徽章：所有徽章等级（无/铜/银/金/名人堂）
  - 热区：所有区域投篮热区等级
  - 倾向：各类球场行为倾向值
- **批量编辑** — 一键全队满属性、年轻化、满徽章等
- **Offset 可配置** — 属性内存偏移独立为 JSON 配置文件，游戏更新后只需更新配置

## 安装

### 从源码运行

```bash
# 克隆仓库
git clone https://github.com/Boowenn/NBA-2K26-Trainer.git
cd NBA-2K26-Trainer

# 安装依赖
pip install -r requirements.txt

# 运行（需要管理员权限）
python main.py
```

### 从 Release 下载

前往 [Releases](https://github.com/Boowenn/NBA-2K26-Trainer/releases) 下载最新的 `NBA2K26Trainer.exe`，直接运行即可。

## 使用方法

1. 启动 NBA 2K26 并进入经理模式
2. 以管理员权限运行 `NBA2K26Trainer.exe`（或 `python main.py`）
3. 点击「连接游戏」按钮
4. 等待球员列表加载完成
5. 在左侧列表中选择要编辑的球员
6. 在右侧编辑面板中修改属性值
7. 点击「应用修改」写入游戏内存

## Offset 配置

属性的内存偏移定义在 `config/offsets_2k26.json` 中。当游戏更新导致偏移变化时，只需更新此文件。

你也可以点击「加载Offset」按钮加载自定义的 offset 配置文件。

### 获取正确的 Offset

配置文件中的 offset 为示例值，实际值需要通过以下方式获取：

1. 参考 [discobisco/2k26-Editor](https://github.com/discobisco/2k26-Editor) 项目的 offset 数据
2. 使用 Cheat Engine 手动逆向确定
3. 参考 [NLSC Forum](https://forums.nba-live.com/) 社区的 Cheat Table

## 构建 EXE

```bash
pip install pyinstaller
pyinstaller NBA2K26Trainer.spec
```

输出文件在 `dist/NBA2K26Trainer.exe`。

## 技术架构

```
nba2k26_trainer/
├── core/
│   ├── memory.py       # Win32 内存读写层 (ctypes)
│   ├── process.py      # 进程发现与附加
│   ├── scanner.py      # AOB 特征码扫描
│   └── offsets.py      # Offset 加载与管理
├── models/
│   ├── player.py       # 球员数据模型
│   └── team.py         # 球队数据模型
├── ui/
│   ├── main_window.py      # 主窗口
│   ├── player_list.py      # 球员列表组件
│   ├── attribute_editor.py # 属性编辑面板
│   ├── batch_editor.py     # 批量编辑对话框
│   └── theme.py            # UI 主题
└── config/
    └── offsets_2k26.json   # 属性偏移配置
```

## 免责声明

本工具仅供学习和研究用途。使用修改器可能违反游戏服务条款并导致账号封禁。请自行承担使用风险。

## License

MIT License
