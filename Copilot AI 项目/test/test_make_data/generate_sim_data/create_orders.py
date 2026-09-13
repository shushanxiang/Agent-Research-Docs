import csv
import json
import requests
import time

# --- 配置 ---
# ▼▼▼ 请将此处的URL修改为您自己服务的实际地址 ▼▼▼
BASE_URL = "http://localhost:8080"  # 例如: "http://api.yourdomain.com"
# ▲▲▲ 请将此处的URL修改为您自己服务的实际地址 ▲▲▲

ORDERS_CSV_FILE = 'Generated File September 16, 2025 - 9_02PM.csv'

# 设置请求头
HEADERS = {
    'Content-Type': 'application/json'
}

# --- 函数定义 ---

def create_orders_from_csv():
    """读取CSV文件并逐条创建订单"""
    print("--- 开始添加订单数据 ---")
    
    try:
        with open(ORDERS_CSV_FILE, mode='r', encoding='utf-8-sig') as csvfile:
            # 使用DictReader可以直接将每一行读成一个字典
            reader = csv.DictReader(csvfile)
            orders_to_create = list(reader)
            
    except FileNotFoundError:
        print(f"错误：找不到订单文件 '{ORDERS_CSV_FILE}'。请确保文件名正确且与脚本在同一目录下。")
        return
    except Exception as e:
        print(f"读取CSV文件时发生错误: {e}")
        return

    success_count = 0
    fail_count = 0
    total_orders = len(orders_to_create)
    
    # 订单API的完整URL
    url = f"{BASE_URL}/orders/createOrder"

    for i, order_data in enumerate(orders_to_create):
        try:
            # 1. 构建符合API格式的请求体 (JSON payload)
            # CSV中的列名和API请求体中的字段名是完全一致的，但值需要转换成正确的类型
            payload = {
                "quantity": int(order_data['quantity']),
                "supplierId": int(order_data['supplierId']),
                "productId": int(order_data['productId']),
                "orderRegion": order_data['orderRegion']
            }

            # 2. 发送POST请求
            response = requests.post(url, json=payload, headers=HEADERS, timeout=10)

            # 3. 检查响应
            if response.status_code == 200:
                success_count += 1
                print(f"({i+1}/{total_orders}) ✅ 成功创建订单: ProductID {payload['productId']} in {payload['orderRegion']}")
            else:
                fail_count += 1
                # 打印详细的失败信息，便于调试
                print(f"({i+1}/{total_orders}) ❌ 创建订单失败 | 数据: {payload} | 状态码: {response.status_code} | 响应: {response.text}")

        except (ValueError, KeyError) as e:
            fail_count += 1
            print(f"({i+1}/{total_orders}) ❌ 数据格式错误 | 原始行: {order_data} | 错误: {e}")
        except requests.exceptions.RequestException as e:
            fail_count += 1
            print(f"({i+1}/{total_orders}) ❌ 请求异常 | 数据: {order_data} | 错误: {e}")
        
        # 增加一个小的延时，避免请求过于频繁
        time.sleep(0.02) 

    print("\n--- 订单数据添加完成 ---")
    print(f"总计: {total_orders}条 | 成功: {success_count}条 | 失败: {fail_count}条")


# --- 主程序入口 ---

if __name__ == "__main__":
    start_time = time.time()
    
    # 执行创建订单的函数
    create_orders_from_csv()
    
    end_time = time.time()
    print(f"\n所有订单导入完成，总耗时: {end_time - start_time:.2f} 秒。")