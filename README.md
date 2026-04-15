# wheel-dedup

批量安装 wheel 文件时自动跳过已安装的包，并在安装前检测版本冲突。

## 安装

```bash
pip install .
# 或开发模式
pip install -e ".[dev]"
```

要求 Python >= 3.8，唯一第三方依赖为 `packaging`。

## 用法

```
wheel-dedup install <wheels...>
```

### 参数

| 参数 | 说明 |
|------|------|
| `wheels` | 一个或多个 wheel 文件路径，支持 glob 通配 |
| `--dry-run` | 仅预览，不实际安装 |
| `-y, --yes` | 跳过所有确认提示（适合脚本化场景） |
| `-v, --verbose` | 显示 pip install 的完整输出 |
| `--skip-conflict-check` | 跳过版本冲突检测 |

## 输出示例

### 基本用法：跳过已安装包

环境中已安装 numpy 2.4.4、pandas 3.0.2，flask 未安装：

```
$ wheel-dedup install numpy-2.4.4-cp313-cp313-linux_x86_64.whl \
                     pandas-3.0.2-cp313-cp313-linux_x86_64.whl \
                     flask-3.1.3-py3-none-any.whl

Checking 3 wheel file(s)...
  SKIP   numpy-2.4.4-cp313-cp313-linux_x86_64.whl (numpy 2.4.4 already installed)
  SKIP   pandas-3.0.2-cp313-cp313-linux_x86_64.whl (pandas 3.0.2 already installed)
  INSTALL flask-3.1.3-py3-none-any.whl

2 skipped, 1 to install

1 to install. Continue? [y/N]: y

Installing flask-3.1.3-py3-none-any.whl... OK

Done: 1 installed, 2 skipped, 0 failed
```

### 预览模式

```
$ wheel-dedup install --dry-run numpy-2.4.4-cp313-cp313-linux_x86_64.whl flask-3.1.3-py3-none-any.whl

Checking 2 wheel file(s)...
  SKIP   numpy-2.4.4-cp313-cp313-linux_x86_64.whl (numpy 2.4.4 already installed)
  INSTALL flask-3.1.3-py3-none-any.whl

1 skipped, 1 to install

Checking for version conflicts...
  No conflicts detected
```

### 检测到版本冲突

环境中已安装 numpy 2.4.4，待安装的 `my_pkg` 要求 numpy>=3.0：

```
$ wheel-dedup install my_pkg-1.0.0-py3-none-any.whl

Checking 1 wheel file(s)...
  INSTALL my_pkg-1.0.0-py3-none-any.whl

0 skipped, 1 to install

Checking for version conflicts...
  VERSION MISMATCH: my_pkg-1.0.0-py3-none-any.whl requires numpy>=3.0, but numpy 2.4.4 is installed

1 conflict(s) found. Continue anyway? [y/N]: n
Aborted.
```

### 三种冲突类型

```
Checking for version conflicts...
  VERSION MISMATCH: my_pkg-1.0.0-py3-none-any.whl requires numpy>=3.0, but numpy 2.4.4 is installed
  WHEEL CONFLICT: my_pkg-1.0.0-py3-none-any.whl requires bar>=2.0, but bar 1.0.0 is in the install list
  MISSING DEPENDENCY: my_pkg-1.0.0-py3-none-any.whl requires nonexistent>=1.0, but nonexistent is not installed and not in wheels

3 conflict(s) found. Continue anyway? [y/N]:
```

| 冲突类型 | 说明 |
|----------|------|
| `VERSION MISMATCH` | wheel 依赖的已安装包版本不满足要求 |
| `WHEEL CONFLICT` | 待安装 wheel 的版本与另一个 wheel 的依赖要求不兼容 |
| `MISSING DEPENDENCY` | 依赖的包既未安装，也不在待安装列表中 |

> 如果待安装列表中包含兼容版本的 wheel，`VERSION MISMATCH` 不会误报——工具会识别到安装后将满足依赖。

## 跳过确认

适合 CI/CD 或脚本化场景：

```bash
wheel-dedup install -y ./wheels/*.whl
```
