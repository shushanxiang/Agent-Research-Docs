import requests
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 基本配置 ---
BASE_URL = "http://localhost:8080"
ENDPOINT = "/products/addProduct"  # <-- 已更新为产品接口
FULL_URL = BASE_URL + ENDPOINT

TOTAL = 10000          # 目标数量
MAX_WORKERS = 20       # 并发线程数，可根据服务能力调整
MAX_RETRIES = 3        # 每条数据的最大重试次数
TIMEOUT = 10           # 请求超时时间（秒）

# --- 产品数据样本库 (基础名, 描述, 基础整数价格) ---
PRODUCT_BASES = [
    ("苹果", "产自山东的红富士", 8), ("香蕉", "来自海南的热带香蕉", 6), ("葡萄", "新疆吐鲁番的无籽葡萄", 15),
    ("草莓", "丹东本地的九九草莓", 22), ("西瓜", "大兴本地的麒麟瓜", 4), ("芒果", "攀枝花的凯特芒果", 12),
    ("樱桃", "大连的美早樱桃", 30), ("橙子", "来自赣州的脐橙", 7), ("蓝莓", "云南本地的优质蓝莓", 25),
    ("榴莲", "产自海南好吃的榴莲", 50), ("菠萝", "产自海南的菠萝", 10), ("桃子", "产自浙江的桃子", 9),
    ("梨子", "产自福建好吃的梨子", 5), ("阳光玫瑰", "产自云南的阳光玫瑰", 18)
]
# --- 常用价格后缀 (用于构造真实标价) ---
PRICE_ENDINGS = [0.0, 0.5, 0.8, 0.9, 0.99, -0.01, -0.1, -0.2, -0.5]
# --- 名称和描述后缀 ---
PRODUCT_SUFFIXES = ["王", "A级", "特选", "有机", "精选", "家庭装", "宝宝果"]

def gen_product_payload(i: int) -> dict:
    """
    生成单个产品的请求体 (payload)，包含真实的价格。
    """
    # 1. 随机选择一个基础产品
    base_name, base_desc, base_price = random.choice(PRODUCT_BASES)
    
    # 2. 生成多样化的名称和描述
    suffix = random.choice(PRODUCT_SUFFIXES)
    name = f"{base_name}-{suffix}{random.randint(1, 200)}"
    description = f"{base_desc} ({suffix})"
    
    # 3. **核心：生成真实感的价格**
    price_ending = random.choice(PRICE_ENDINGS)
    final_price = base_price + price_ending
    # 确保价格至少为正数 (例如 1 - 0.1 = 0.9)
    final_price = max(0.5, final_price) 
    # 四舍五入到两位小数，生成 double 类型
    final_price = round(final_price, 2)
    
    # 4. 生成随机库存
    quantity_in_stock = random.randint(50, 20000)
    
    payload = {
        "name": name,
        "description": description,
        "price": final_price,
        "quantityInStock": quantity_in_stock
    }
    return payload

def post_one(i: int) -> tuple:
    """
    发送单个POST请求，并包含重试逻辑。
    """
    payload = gen_product_payload(i)
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
    print(f"开始向 {FULL_URL} 并发插入 {TOTAL} 条新产品数据...")
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
    # 建议先用少量数据 (例如 TOTAL = 50) 测试，以确认API和数据格式都正常
    main()