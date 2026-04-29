# -*- coding: utf-8 -*-
"""
API 测试脚本 — 用于确认 Function Compute HTTP API 返回格式
使用方法：
1. 填入 ACCESS_KEY_ID 和 ACCESS_KEY_SECRET（阿里云 FC 签名用）
2. 运行: python test_api.py
3. 把终端输出发给 AI
"""
import os
import json
import requests
import hmac
import hashlib
import datetime

# ===================== 配置区（请自行填入）=====================
ACCESS_KEY_ID = ""      # 填入 AccessKey ID
ACCESS_KEY_SECRET = ""   # 填入 AccessKey Secret

# API 端点
API_URL = "https://fc-maxcte-query-azbabkaceu.ap-southeast-1.fcapp.run"

# 测试 SQL
TEST_SQL = "SELECT * FROM phl_anls.tmp_liujun_ana_11_agent_process_daily LIMIT 3"
# ===================== 配置区 END =====================


def make_fc_signature(method, path, secret, content_type="", date=""):
    """生成阿里云 FC 签名"""
    string_to_sign = f"{method}\n{content_type}\n{date}\n{path}"
    signature = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1
    ).hexdigest()
    return signature


def main():
    if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET:
        print("请先在脚本顶部填入 ACCESS_KEY_ID 和 ACCESS_KEY_SECRET")
        return

    print("=" * 60)
    print("API 测试脚本")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print(f"AK ID:   {ACCESS_KEY_ID[:4]}...{ACCESS_KEY_ID[-4:]}")
    print("-" * 60)

    body = {"sql": TEST_SQL}
    headers = {"Content-Type": "application/json"}

    # 阿里云 FC 签名
    date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    path = "/".lstrip("/")
    signature = make_fc_signature("POST", "/" + path, ACCESS_KEY_SECRET, "application/json", date)
    auth_header = f"FC {ACCESS_KEY_ID}:{signature}"
    headers["Authorization"] = auth_header
    headers["Date"] = date

    print(f"\n[Request] POST {API_URL}")
    print(f"[Authorization]: {auth_header[:40]}...")
    print(f"[Body]: {json.dumps(body, ensure_ascii=False)[:300]}")

    try:
        resp = requests.post(API_URL, json=body, headers=headers, timeout=60)
        print(f"\n[Status] {resp.status_code}")
        print(f"[Content-Type] {resp.headers.get('Content-Type', 'N/A')}")
        print(f"[Response Headers]: {dict((k, v) for k, v in resp.headers.items() if k not in ['X-Fc-Request-Id'])}")

        try:
            content = resp.json()
            print(f"[Body - JSON]:")
            print(json.dumps(content, ensure_ascii=False, indent=2)[:3000])
        except Exception:
            print(f"[Body - Raw]: {resp.text[:2000]}")

    except requests.exceptions.Timeout:
        print("[ERROR] 请求超时（60秒）")
    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] 连接失败: {e}")
    except Exception as e:
        print(f"[ERROR] 未知错误: {e}")

    print("\n" + "=" * 60)
    print("测试完成。请把上方输出发给 AI")
    print("=" * 60)


if __name__ == "__main__":
    main()
    input("\n按 Enter 键关闭窗口...")
