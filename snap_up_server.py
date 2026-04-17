"""
腾讯云服务器秒杀工具 - 支持多活动配置
支持双12活动、CodingPlan活动等
"""
import requests
import json
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import os
import re

# =================== 配置加载 =================== #

CONFIG_FILE = "config.json"

def load_config():
    """加载配置文件"""
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"配置文件 {CONFIG_FILE} 不存在，请创建")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    current_key = config.get("current_activity")
    if current_key not in config["activities"]:
        raise KeyError(f"活动 '{current_key}' 在配置文件中不存在")

    activity = config["activities"][current_key]
    return activity

# 加载活动配置
try:
    ACTIVITY = load_config()
except Exception as e:
    print(f"❌ 配置加载失败: {e}")
    exit(1)

ACTIVITY_NAME = ACTIVITY["name"]
ACTIVITY_ID = ACTIVITY["activity_id"]
SECkiLL_TIME_STR = ACTIVITY["seckill_time"]
GOODS_LIST = ACTIVITY["goods"]
CONCURRENT = ACTIVITY.get("concurrent", True)
REFERER = ACTIVITY.get("referer", "")

print(f"✓ 当前活动: {ACTIVITY_NAME}")
print(f"✓ 活动ID: {ACTIVITY_ID}")
print(f"✓ 秒杀时间: {SECkiLL_TIME_STR}")
print(f"✓ 商品数量: {len(GOODS_LIST)}")
for g in GOODS_LIST:
    print(f"   - {g['name']} (act_id={g['act_id']}, 地域={g['region_ids']})")

# =================== 会话初始化 =================== #

session = requests.Session()

# 加载Cookie
try:
    with open("cookies.json", "r", encoding="utf-8") as f:
        cookies = json.load(f)
        for cookie in cookies:
            session.cookies.set(
                cookie.get('name', ''),
                cookie.get('value', ''),
                domain=cookie.get('domain', ''),
                path=cookie.get('path', '/')
            )
    print("✓ Cookie 加载成功")
except FileNotFoundError:
    print("✗ 未找到 cookies.json，请先运行 get_cookies.py 获取登录Cookie")
    exit(1)

# 请求头（CSRF Token动态更新）
headers = {
    "x-csrf-token": "",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "referer": REFERER
}

def fetch_platform_csrf():
    """
    使用 Playwright 访问活动页面，从 auth-api/common/platform 请求的 URL
    中捕获动态生成的 csrfCode 参数
    :return: CSRF token字符串或None
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[WARN] Playwright未安装，无法获取动态CSRF")
        return None

    print("[INFO] 正在获取动态CSRF token...")
    captured_token = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()

            # 加载相同的Cookie（保持登录态）
            try:
                with open("cookies.json", "r", encoding="utf-8") as f:
                    cookies_data = json.load(f)
                context.add_cookies(cookies_data)
            except Exception as e:
                print(f"[WARN] 加载cookies失败: {e}")

            page = context.new_page()

            # 监听请求，捕获平台接口的 csrfCode
            def on_request(request):
                url = request.url
                if 'auth-api/common/platform' in url:
                    match = re.search(r'csrfCode=([^&;]+)', url)
                    if match:
                        token = match.group(1)
                        if token not in captured_token:
                            captured_token.append(token)
                            print(f"[OK] 捕获到CSRF token: {token[:30]}")

            page.on("request", on_request)

            # 访问页面
            page.goto("https://cloud.tencent.com/act/pro/codingplan")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)  # 等待请求完成

            browser.close()

    except Exception as e:
        print(f"[WARN] Playwright获取CSRF失败: {e}")
        return None

    if captured_token:
        return captured_token[0]
    else:
        print("[WARN] 未捕获到动态token，尝试备用方案...")
        # 备用：从 cookies 读取
        for name, value in session.cookies.items():
            if any(kw in name.lower() for kw in ['csrf', 'xsrf', '_csrf']):
                print(f"[OK] 使用备用 token: {name}")
                return value
        return None

def update_csrf_token():
    """
    更新CSRF Token（优先从平台接口获取动态token）
    降级策略：平台接口失败 -> cookies -> session cookies
    """
    # 优先级1: 从平台接口获取动态token
    token = fetch_platform_csrf()
    if token:
        headers['x-csrf-token'] = token
        return token

    # 降级策略: 从静态cookies读取（作为备用）
    token_keywords = ['csrf', 'xsrf', '_csrf']

    try:
        with open("cookies.json", "r", encoding="utf-8") as f:
            cookies_data = json.load(f)
        for cookie in cookies_data:
            name = cookie.get('name', '')
            if any(kw in name.lower() for kw in token_keywords):
                token = cookie.get('value', '')
                if token:
                    headers['x-csrf-token'] = token
                    print(f"✓ 已从cookies更新 CSRF Token: {token[:20]}...")
                    return token
    except Exception as e:
        print(f"⚠ 读取cookies.json失败: {e}")

    # 从session.cookies中查找
    for name, value in session.cookies.items():
        if any(kw in name.lower() for kw in token_keywords):
            headers['x-csrf-token'] = value
            print(f"✓ 已从会话更新 CSRF Token: {name}")
            return value

    print("❌ 未能获取CSRF Token，抢购将失败")
    print("   请检查网络连接或重新导出cookies.json")
    return None

# =================== 库存检查 =================== #

def build_check_data(goods_item):
    """构建库存检查请求数据"""
    return {
        "activity_id": ACTIVITY_ID,
        "goods": [
            {
                "act_id": goods_item["act_id"],
                "region_id": goods_item["region_ids"]
            }
        ],
        "preview": 0
    }

def check_available(goods_item):
    """
    检查指定商品的库存
    :param goods_item: 商品配置字典
    :return: 有货的地域ID列表，或None
    """
    try:
        resp = session.post(
            "https://act-api.cloud.tencent.com/dianshi/check-available",
            json=build_check_data(goods_item),
            headers=headers,
            timeout=10
        )
        resp.raise_for_status()
        result = resp.json()
    except Exception as e:
        print(f"❌ [{goods_item['name']}] 库存检查失败: {str(e)}")
        return None

    # 校验接口返回
    if result.get("code") != 0 or result.get("msg") != "ok":
        print(f"❌ [{goods_item['name']}] 接口异常: {json.dumps(result, ensure_ascii=False)[:100]}")
        return None

    goods_data = result.get("data", [{}])[0]

    if goods_data.get("available") != 1 or goods_data.get("user_available") != 1:
        print(f"❌ [{goods_item['name']}] 无购买权限/整体无货")
        return None

    # 检查各地域库存
    quota = goods_data.get("quota", {})
    available_regions = []

    region_names = {1: "华北", 4: "华东", 8: "华南"}
    for region_id in goods_item["region_ids"]:
        available = quota.get(str(region_id), {})\
                        .get("bundle_budget_mc_lg4_01", {})\
                        .get("available", 0)
        rname = region_names.get(region_id, f"地域{region_id}")
        if available > 0:
            print(f"✅ [{goods_item['name']}] {rname}（region_id={region_id}）有库存！")
            available_regions.append(region_id)

    return available_regions if available_regions else None

# =================== 抢购下单 =================== #

def build_goods_param(goods_item, region_id):
    """构建商品参数字典"""
    template = goods_item.get("goods_param_template", {})
    param = template.copy()
    param["regionId"] = region_id
    param["area"] = region_id
    return param

def buy_now(goods_item, region_id):
    """
    调用do-goods接口完成购买
    :param goods_item: 商品配置
    :param region_id: 有货的地域ID
    """
    goods_param = build_goods_param(goods_item, region_id)

    do_data = {
        "activity_id": ACTIVITY_ID,
        "agent_channel": {
            "fromChannel": "",
            "fromSales": "",
            "isAgentClient": False,
            "fromUrl": REFERER
        },
        "business": {
            "id": 22755,
            "from": "lightningDeals"
        },
        "goods": [
            {
                "act_id": goods_item["act_id"],
                "type": goods_item["type"],
                "goods_param": goods_param
            }
        ],
        "preview": 0
    }

    try:
        resp = session.post(
            "https://act-api.cloud.tencent.com/dianshi/do-goods",
            json=do_data,
            headers=headers,
            timeout=10
        )
        print(f"🎯 [{goods_item['name']}] 抢购响应: {resp.text[:200]}")
        result = resp.json()

        if isinstance(result, dict) and result.get("code") == 0:
            print(f"🎉 [{goods_item['name']}] region_id={region_id} 抢购成功！")
            return result
        else:
            print(f"❌ [{goods_item['name']}] 抢购失败: {result}")
            return None
    except Exception as e:
        print(f"❌ [{goods_item['name']}] 抢购异常: {str(e)}")
        return None

def buy_goods_concurrent(goods_item, region_ids):
    """
    并发抢购同一商品在不同地域
    """
    with ThreadPoolExecutor(max_workers=len(region_ids)) as executor:
        futures = [executor.submit(buy_now, goods_item, rid) for rid in region_ids]
        for future in futures:
            result = future.result()
            if result:
                return result
    return None

# =================== 时间工具 =================== #

def get_server_time():
    """获取腾讯云服务器时间"""
    try:
        response = requests.head("https://cloud.tencent.com", timeout=10)
        server_time = response.headers.get("Date")

        if server_time:
            dt = datetime.strptime(server_time, "%a, %d %b %Y %H:%M:%S GMT")
            beijing_time = dt + timedelta(hours=8)
            timestamp_ms = int(beijing_time.timestamp() * 1000)
            print(f"服务器时间(GMT): {dt} | 北京时间: {beijing_time}")
            return timestamp_ms
        else:
            print("⚠ 未获取到服务器时间，使用本地时间")
            return int(time.time() * 1000)
    except Exception as e:
        print(f"⚠ 获取服务器时间失败: {e}，使用本地时间")
        return int(time.time() * 1000)

# =================== 主程序 =================== #

def main():
    print("=" * 60)
    print(f"🚀 腾讯云秒杀工具 - {ACTIVITY_NAME}")
    print("=" * 60)

    # 更新CSRF Token
    update_csrf_token()

    # 计算秒杀时间戳
    try:
        seckill_timestamp = int(time.mktime(time.strptime(SECkiLL_TIME_STR, "%Y-%m-%d %H:%M:%S"))) * 1000
    except ValueError:
        print(f"❌ 秒杀时间格式错误: {SECkiLL_TIME_STR}，应为 YYYY-MM-DD HH:MM:SS")
        return

    print(f"\n⏰ 秒杀时间: {SECkiLL_TIME_STR}")
    print(f"⏳ 等待秒杀开始...")

    # 等待秒杀时间
    while True:
        current_time = get_server_time()
        if current_time >= seckill_timestamp:
            print("\n🔥 秒杀开始！")
            break
        else:
            remaining = (seckill_timestamp - current_time) / 1000
            if remaining > 0:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                print(f"\r⏳ 距离秒杀还有: {mins:02d}分{secs:02d}秒", end="", flush=True)
            time.sleep(1)

    # 开始抢购
    print("\n\n🚀 开始抢购...")
    success_count = 0

    for goods_item in GOODS_LIST:
        print(f"\n{'='*50}")
        print(f"--- 正在抢购: {goods_item['name']} ---")

        # 检查库存
        print(f"正在检查库存...")
        available_regions = check_available(goods_item)

        if not available_regions:
            print(f"❌ [{goods_item['name']}] 当前无货，跳过")
            continue

        print(f"✅ [{goods_item['name']}] 发现库存地域: {available_regions}")

        # 并发或顺序抢购
        if CONCURRENT and len(available_regions) > 1:
            result = buy_goods_concurrent(goods_item, available_regions)
        else:
            result = buy_now(goods_item, available_regions[0])

        if result:
            print(f"🎉 [{goods_item['name']}] 抢购成功！")
            success_count += 1
        else:
            print(f"❌ [{goods_item['name']}] 抢购失败")

    print(f"\n{'='*60}")
    if success_count > 0:
        print(f"🎊 本次抢购成功 {success_count}/{len(GOODS_LIST)} 个商品！请登录控制台确认订单！")
    else:
        print("😢 本次抢购未成功，请继续监控库存或稍后重试")

if __name__ == "__main__":
    main()
