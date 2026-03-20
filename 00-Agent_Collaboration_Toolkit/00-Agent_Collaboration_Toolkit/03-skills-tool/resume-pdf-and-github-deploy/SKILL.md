---
name: resume-pdf-and-github-deploy
description: Converts resume HTML to PDF (Playwright) and pushes personal site updates to GitHub. Use when the user asks to 转 PDF、转简历 PDF、生成简历 PDF、推线上、推 GitHub、更新个人站、deploy、推到线上.
---

# 简历转 PDF 与个人站推 GitHub

## 一、简历转 PDF

### 路径约定（按当前工作区）

- **源 HTML**：`site-redesign/final/1.resume/resume-pdf.html`（一页打印版）
- **同步到线上仓库**：`risk-digital-assets/1.resume/` 内也有同名文件，以 final 为内容源

### 单版 PDF（默认字体）

在 **1.resume** 目录下执行：

```bash
cd site-redesign/final/1.resume
python html-to-pdf.py
```

- **输出**：同目录下 `resume-YuanPeng-one-page.pdf`
- **依赖**：`pip install playwright` 且已执行 `playwright install chromium`

### 多字体版 PDF（对比用）

```bash
cd site-redesign/final/1.resume
python html-to-pdf-fonts.py
```

生成三份：`resume-YuanPeng-one-page-SegoeUI.pdf`、`-YaHei.pdf`、`-Songti.pdf`。

### Windows PowerShell 注意

- 用 `Set-Location "e:\site-redesign\final\1.resume"` 切目录，不要用 `cd /d` 或 `&&`。

---

## 二、推 GitHub（个人站更新）

### 仓库与源

- **线上仓库**：`risk-digital-assets`，远程 `origin` → `https://github.com/jerr-yuan/-risk-digital-assets.git`
- **内容源**：`site-redesign/final/`（成就页、简历等以此处为准）

### 需要同步的文件

从 `site-redesign/final/` 复制到 `risk-digital-assets/` 再提交：

| 源 (final) | 目标 (risk-digital-assets) |
|------------|-----------------------------|
| achievements.html | achievements.html |
| 1.resume/resume-pdf.html | 1.resume/resume-pdf.html |
| 1.resume/resume-v4.16.html | 1.resume/resume-v4.16.html |
| 1.resume/html-to-pdf.py | 1.resume/html-to-pdf.py |
| 1.resume/html-to-pdf-fonts.py | 1.resume/html-to-pdf-fonts.py |

### 提交流程

1. **复制文件**（PowerShell）  
   ```powershell
   Copy-Item "e:\site-redesign\final\achievements.html" "e:\risk-digital-assets\achievements.html" -Force
   Copy-Item "e:\site-redesign\final\1.resume\resume-pdf.html" "e:\risk-digital-assets\1.resume\resume-pdf.html" -Force
   Copy-Item "e:\site-redesign\final\1.resume\resume-v4.16.html" "e:\risk-digital-assets\1.resume\resume-v4.16.html" -Force
   Copy-Item "e:\site-redesign\final\1.resume\html-to-pdf.py" "e:\risk-digital-assets\1.resume\html-to-pdf.py" -Force
   Copy-Item "e:\site-redesign\final\1.resume\html-to-pdf-fonts.py" "e:\risk-digital-assets\1.resume\html-to-pdf-fonts.py" -Force
   ```

2. **进入仓库并暂存**  
   ```bash
   cd risk-digital-assets
   git add achievements.html 1.resume/resume-pdf.html 1.resume/resume-v4.16.html 1.resume/html-to-pdf.py 1.resume/html-to-pdf-fonts.py
   ```

3. **提交**  
   ```bash
   git commit -m "feat: 业绩成就/简历与 PDF 脚本更新"
   ```

4. **拉取并变基（避免被拒）**  
   ```bash
   git fetch origin main
   git pull origin main --rebase
   ```

5. **若 rebase 出现冲突**  
   - 保留「我方」内容（来自 final 的成就页/简历）：  
     `git checkout --theirs achievements.html`  
     `git checkout --theirs 1.resume/resume-v4.16.html`  
   - 然后：`git add` 上述文件，`git rebase --continue`（可设 `GIT_EDITOR=true` 避免弹编辑器）。

6. **推送**  
   ```bash
   git push origin main
   ```

### 若本地有未提交修改

- 先 `git stash push -m "temp" -- <file>` 再执行 pull/rebase，推送成功后 `git stash pop`。

---

## 三、一次做完「转 PDF + 推 GitHub」时的顺序

1. 在 `site-redesign/final/1.resume` 执行 `python html-to-pdf.py` 生成最新 PDF。
2. 按「二」将 final 中指定文件同步到 risk-digital-assets，再 add → commit → fetch → pull --rebase（必要时解决冲突）→ push。

线上站点（如 GitHub Pages）更新后，成就页与简历会与 final 一致；PDF 可在本地使用或自行上传到站点/网盘。
