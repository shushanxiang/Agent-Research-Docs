import requests
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 基本配置 ---
BASE_URL = "http://localhost:8080"
ENDPOINT = "/suppliers/addSuppliers"
FULL_URL = BASE_URL + ENDPOINT

TOTAL = 1000          # 目标数量
MAX_WORKERS = 20       # 并发线程数，可根据服务能力调整
MAX_RETRIES = 3        # 每条数据的最大重试次数
TIMEOUT = 10           # 请求超时时间（秒）

# --- 数据样本库 (用于生成多样化数据) ---
CITIES = ["北京", "上海", "广州", "深圳", "成都", "杭州", "武汉", "重庆", "西安", "苏州", "天津", "南京", "长沙", "郑州", "东莞", "青岛", "沈阳", "济南"]
SUPPLIER_NAME_PREFIXES = ["京东", "美团", "盒马", "永辉", "天天", "果蔬", "绿源", "鲜丰", "百果园", "阳光"]
SUPPLIER_NAME_SUFFIXES = ["生鲜", "优选", "买菜", "农场", "果业", "配送", "仓储"]

def gen_supplier_payload(i: int) -> dict:
    """
    生成真实的供应商请求体(payload)，价格与距离正相关。
    """
    address = random.choice(CITIES)

    name = f"{random.choice(SUPPLIER_NAME_PREFIXES)}{random.choice(SUPPLIER_NAME_SUFFIXES)}{address}仓"

    # --- 生成 deliveryAreas ---
    num_areas = random.randint(1, 3)
    areas_list = []
    available_cities = [c for c in CITIES if c != address]
    
    for _ in range(num_areas):
        if not available_cities: break
        
        start_node = address
        end_node = random.choice(available_cities)
        available_cities.remove(end_node)
        
        path_len = random.randint(2, 4)
        middle_candidates = [c for c in CITIES if c not in [start_node, end_node]]
        middle_nodes = random.sample(middle_candidates, min(path_len - 2, len(middle_candidates)))
        
        # **核心改动 2: 价格与距离正相关**
        # 1. 首先确定距离
        distance = random.randint(100, 2500)
        
        # 2. 根据距离计算价格，并加入随机性
        # 基础运费在20-40元之间
        base_fee = random.uniform(20, 40)
        # 每公里成本在0.08元到0.15元之间
        cost_per_km = random.uniform(0.08, 0.15)
        # 计算基础价格
        base_price = base_fee + (distance * cost_per_km)
        # 增加一个-10%到+10%的随机扰动，让数据更真实
        final_price = base_price * (1 + random.uniform(-0.1, 0.1))
        # 确保价格是整数且不低于20
        final_price = max(20, int(final_price))

        area_object = {
            "region": end_node,
            "distance": distance,
            "price": final_price,  # <-- 使用计算出的关联价格
            "paths": [start_node] + middle_nodes + [end_node]
        }
        areas_list.append(area_object)
    
    phone = f"1{random.randint(3000000000, 9999999999)}"
    rating = round(random.uniform(3.0, 5.0), 1)
    status = "InUse" if random.random() < 0.85 else "DisUse"

    payload = {
        "name": name,
        "phone": phone,
        "address": address,
        "deliveryAreas": areas_list,
        "rating": rating,
        "status": status
    }
    return payload

def post_one(i: int) -> tuple:
    """
    发送单个POST请求，并包含重试逻辑。
    """
    payload = gen_supplier_payload(i)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(FULL_URL, json=payload, timeout=TIMEOUT)
            if resp.status_code in [200, 201]:
                return (i, True, None)
            else:
                err = f"HTTP {resp.status_code} - {resp.text[:200]}"
        except requests.RequestException as e:
            err = str(e)
        
        time.sleep(0.5 * attempt)
        
    return (i, False, err)

def main():
    """
    主函数，使用线程池并发执行所有请求。
    """
    print(f"开始向 {FULL_URL} 并发插入 {TOTAL} 条")
    success, fail = 0, 0
    errors = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(post_one, i): i for i in range(1, TOTAL + 1)}
        
        for fut in as_completed(futures):
            i, ok, err = fut.result()
            if ok:
                success += 1
                if success % 500 == 0:
                    print(f"已成功插入: {success}/{TOTAL}")
            else:
                fail += 1
                errors.append((i, err))

    print("-" * 30)
    print(f"任务完成. 成功 = {success}, 失败 = {fail}")
    if fail:
        print("前10条错误示例:")
        for i, e in errors[:10]:
            print(f"- 数据 #{i}: {e}")

if __name__ == "__main__":
    # 建议先用少量数据 (例如 TOTAL = 50) 测试，以确认生成的数据符合预期
    main()