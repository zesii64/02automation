#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动下载邮件附件并触发报告生成
用法: python 01-email_attachment_downloader.py
"""

import imaplib
import email
import email.header
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ==================== 配置区域 ====================
# 邮箱配置
EMAIL_HOST = "imap.company.com"      # IMAP服务器地址
EMAIL_USER = "your.email@company.com" # 邮箱地址
EMAIL_PASS = "your_password_or_token" # 密码或应用专用密码
EMAIL_FOLDER = "INBOX"               # 邮箱文件夹

# 邮件筛选条件
SENDER_FILTER = "data-system@company.com"  # 发件人邮箱（部分匹配）
SUBJECT_KEYWORD = "collection_data"         # 主题关键词（部分匹配）
ATTACHMENT_NAME_PATTERN = r"260318_output_automation_v3.*\.xlsx"  # 附件名正则

# 路径配置
DOWNLOAD_DIR = Path(r"D:\11automation\02automation\10-Collection_Inspection\10-Collection_Inspection\10-data\email_attachments")
REPORT_SCRIPT = Path(r"D:\11automation\02automation\10-Collection_Inspection\10-Collection_Inspection\05-scripts\generate_report_v2_7.py")

# 时间范围：只处理今天或最近 N 天的邮件
DAYS_BACK = 1
# =================================================


def decode_str(s):
    """解码邮件头中的编码字符串"""
    if not s:
        return ""
    value, charset = email.header.decode_header(s)[0]
    if isinstance(value, bytes):
        if charset:
            return value.decode(charset)
        return value.decode("utf-8", errors="ignore")
    return value


def get_attachment_filename(part):
    """从邮件part中获取附件文件名"""
    filename = part.get_filename()
    if filename:
        return decode_str(filename)
    return None


def connect_imap():
    """连接IMAP服务器"""
    print(f"[{datetime.now()}] 连接邮箱: {EMAIL_HOST}")
    mail = imaplib.IMAP4_SSL(EMAIL_HOST)
    mail.login(EMAIL_USER, EMAIL_PASS)
    print(f"[{datetime.now()}] 登录成功")
    return mail


def search_target_emails(mail):
    """搜索符合条件的邮件"""
    mail.select(EMAIL_FOLDER)

    # 计算日期范围
    since_date = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%d-%b-%Y")

    # 构建搜索条件: 未删除 + 日期之后
    search_criteria = f'(SINCE "{since_date}")'

    status, messages = mail.search(None, search_criteria)
    if status != "OK":
        print(f"[{datetime.now()}] 邮件搜索失败: {status}")
        return []

    email_ids = messages[0].split()
    print(f"[{datetime.now()}] 找到 {len(email_ids)} 封邮件需要检查")
    return email_ids


def process_email(mail, email_id):
    """处理单封邮件，下载符合条件的附件"""
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    if status != "OK":
        return None

    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    # 解析邮件头
    subject = decode_str(msg["Subject"])
    from_addr = decode_str(msg["From"])
    date_str = msg["Date"]

    print(f"  检查邮件: [发件人]{from_addr} | [主题]{subject} | [日期]{date_str}")

    # 筛选发件人和主题
    if SENDER_FILTER and SENDER_FILTER.lower() not in from_addr.lower():
        return None
    if SUBJECT_KEYWORD and SUBJECT_KEYWORD.lower() not in subject.lower():
        return None

    print(f"  >>> 匹配成功！处理附件...")

    downloaded_files = []

    # 遍历邮件内容，寻找附件
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get("Content-Disposition") is None:
            continue

        filename = get_attachment_filename(part)
        if not filename:
            continue

        # 检查附件名是否匹配
        if not re.search(ATTACHMENT_NAME_PATTERN, filename, re.IGNORECASE):
            print(f"    跳过附件: {filename} (不匹配)")
            continue

        # 下载附件
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        # 添加时间戳避免覆盖
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{Path(filename).stem}_{timestamp}{Path(filename).suffix}"
        filepath = DOWNLOAD_DIR / safe_filename

        with open(filepath, "wb") as f:
            payload = part.get_payload(decode=True)
            if payload:
                f.write(payload)

        print(f"    已下载: {filepath}")
        downloaded_files.append(filepath)

    return downloaded_files


def run_report_generation(filepath):
    """调用报告生成脚本"""
    if not REPORT_SCRIPT.exists():
        print(f"[{datetime.now()}] 错误: 报告脚本不存在: {REPORT_SCRIPT}")
        return False

    print(f"[{datetime.now()}] 开始生成报告，数据源: {filepath}")

    try:
        # 根据你的实际脚本调整调用方式
        # 方式1: 直接调用Python脚本并传递文件路径
        result = subprocess.run(
            [sys.executable, str(REPORT_SCRIPT), "--input", str(filepath)],
            capture_output=True,
            text=True,
            timeout=300,  # 5分钟超时
        )

        print(f"[{datetime.now()}] 报告脚本输出:\n{result.stdout}")
        if result.stderr:
            print(f"[{datetime.now()}] 报告脚本错误:\n{result.stderr}")

        if result.returncode == 0:
            print(f"[{datetime.now()}] 报告生成成功！")
            return True
        else:
            print(f"[{datetime.now()}] 报告生成失败，返回码: {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        print(f"[{datetime.now()}] 报告生成超时")
        return False
    except Exception as e:
        print(f"[{datetime.now()}] 报告生成异常: {e}")
        return False


def cleanup_old_files(days=7):
    """清理超过N天的旧附件"""
    if not DOWNLOAD_DIR.exists():
        return
    cutoff = datetime.now() - timedelta(days=days)
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            f.unlink()
            print(f"[{datetime.now()}] 清理旧文件: {f.name}")


def main():
    print("=" * 60)
    print(f"[{datetime.now()}] 开始执行邮件附件自动下载任务")
    print("=" * 60)

    # 连接邮箱
    try:
        mail = connect_imap()
    except Exception as e:
        print(f"[{datetime.now()}] 邮箱连接失败: {e}")
        input("按 Enter 键关闭窗口...")
        return 1

    try:
        # 搜索邮件
        email_ids = search_target_emails(mail)
        if not email_ids:
            print(f"[{datetime.now()}] 没有找到符合条件的邮件")
            return 0

        # 按ID倒序（最新的优先）
        email_ids.reverse()

        all_downloaded = []
        for eid in email_ids:
            files = process_email(mail, eid)
            if files:
                all_downloaded.extend(files)
                # 只处理最新一封匹配的邮件
                break

        if not all_downloaded:
            print(f"[{datetime.now()}] 未下载到任何附件")
            return 0

        # 用最新下载的文件生成报告
        latest_file = max(all_downloaded, key=lambda p: p.stat().st_mtime)
        print(f"[{datetime.now()}] 使用最新文件生成报告: {latest_file}")

        success = run_report_generation(latest_file)

        # 清理7天前的旧文件
        cleanup_old_files(days=7)

        return 0 if success else 1

    finally:
        mail.logout()
        print(f"[{datetime.now()}] 邮箱连接已关闭")
        print("=" * 60)


if __name__ == "__main__":
    exit_code = main()
    input("按 Enter 键关闭窗口...")
    sys.exit(exit_code)
