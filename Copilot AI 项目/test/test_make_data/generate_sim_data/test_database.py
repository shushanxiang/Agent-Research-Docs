import json
import requests
import time

# --- 配置 ---
# ▼▼▼ 请将此处的URL修改为您自己服务的实际地址 ▼▼▼
BASE_URL = "http://localhost:8080"  # 例如: "http://api.yourdomain.com"
# ▲▲▲ 请将此处的URL修改为您自己服务的实际地址 ▲▲▲

SUPPLIERS_FILE = 'suppliers.json'
PRODUCTS_FILE = 'products_final.json'

# 设置请求头
HEADERS = {
    'Content-Type': 'application/json'
}

# --- 函数定义 ---

def add_suppliers():
    """读取供应商文件并逐条添加到数据库"""
    print("--- 开始添加供应商数据 ---")
    
    try:
        with open(SUPPLIERS_FILE, 'r', encoding='utf-8') as f:
            suppliers = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到供应商文件 '{SUPPLIERS_FILE}'。请确保文件与脚本在同一目录下。")
        return

    success_count = 0
    fail_count = 0
    
    # 供应商API的完整URL
    url = f"{BASE_URL}/suppliers/addSuppliers"

    for i, supplier in enumerate(suppliers):
        try:
            # 发送POST请求，使用json参数requests会自动处理序列化和请求头
            response = requests.post(url, json=supplier, headers=HEADERS, timeout=10)

            # 检查响应状态码
            if response.status_code == 200:
                success_count += 1
                print(f"({i+1}/{len(suppliers)}) ✅ 成功添加供应商: {supplier.get('name', 'N/A')}")
            else:
                fail_count += 1
                print(f"({i+1}/{len(suppliers)}) ❌ 添加失败: {supplier.get('name', 'N/A')} | 状态码: {response.status_code} | 响应: {response.text}")

        except requests.exceptions.RequestException as e:
            fail_count += 1
            print(f"({i+1}/{len(suppliers)}) ❌ 请求异常: {supplier.get('name', 'N/A')} | 错误: {e}")
        
        # 增加一个小的延时，避免请求过于频繁导致服务器压力过大
        time.sleep(0.05) 

    print(f"--- 供应商数据添加完成 ---")
    print(f"总计: {len(suppliers)}条 | 成功: {success_count}条 | 失败: {fail_count}条\n")


def add_products():
    """读取产品文件并逐条添加到数据库"""
    print("--- 开始添加产品数据 ---")
    
    try:
        with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
            products = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到产品文件 '{PRODUCTS_FILE}'。请确保文件与脚本在同一目录下。")
        return

    success_count = 0
    fail_count = 0
    
    # 产品API的完整URL
    url = f"{BASE_URL}/products/addProduct"

    for i, product in enumerate(products):
        try:
            response = requests.post(url, json=product, headers=HEADERS, timeout=10)

            if response.status_code == 200:
                success_count += 1
                print(f"({i+1}/{len(products)}) ✅ 成功添加产品: {product.get('name', 'N/A')}")
            else:
                fail_count += 1
                print(f"({i+1}/{len(products)}) ❌ 添加失败: {product.get('name', 'N/A')} | 状态码: {response.status_code} | 响应: {response.text}")

        except requests.exceptions.RequestException as e:
            fail_count += 1
            print(f"({i+1}/{len(products)}) ❌ 请求异常: {product.get('name', 'N/A')} | 错误: {e}")
        
        time.sleep(0.01) # 产品的延时可以更短一些

    print(f"--- 产品数据添加完成 ---")
    print(f"总计: {len(products)}条 | 成功: {success_count}条 | 失败: {fail_count}条\n")


# --- 主程序入口 ---

if __name__ == "__main__":
    start_time = time.time()
    
    # 依次执行添加供应商和产品的函数
    add_suppliers()
    add_products()
    
    end_time = time.time()
    print(f"所有数据导入完成，总耗时: {end_time - start_time:.2f} 秒。")