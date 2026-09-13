import json
import random
from faker import Faker
import time
import itertools

# 初始化Faker，仅用于生成电话和地址
fake = Faker('zh_CN')

# --- 数据配置 (最终版) ---

# V9 供应商数据库扩充
CITIES_AND_PROVINCES_V9 = [
    ("北京市", "北京市"), ("上海市", "上海市"), ("天津市", "天津市"), ("重庆市", "重庆市"),
    ("广东省", "广州市"), ("广东省", "深圳市"), ("广东省", "东莞市"), ("广东省", "佛山市"),
    ("四川省", "成都市"), ("浙江省", "杭州市"), ("浙江省", "宁波市"), ("浙江省", "温州市"),
    ("湖北省", "武汉市"), ("江苏省", "苏州市"), ("江苏省", "南京市"), ("江苏省", "无锡市"),
    ("陕西省", "西安市"), ("湖南省", "长沙市"), ("河南省", "郑州市"), ("云南省", "昆明市"),
    ("山东省", "济南市"), ("山东省", "青岛市"), ("安徽省", "合肥市"), ("福建省", "福州市"),
    ("福建省", "厦门市"), ("福建省", "泉州市"),("辽宁省", "沈阳市"), ("辽宁省", "大连市"),
    ("黑龙江省", "哈尔滨市"), ("河北省", "石家庄市"), ("山西省", "太原市"), ("江西省", "南昌市"),
    ("贵州省", "贵阳市"), ("广西壮族自治区", "南宁市"), ("海南省", "海口市"), ("甘肃省", "兰州市"),
    ("新疆维吾尔自治区", "乌鲁木齐市"), ("吉林省", "长春市"), ("内蒙古自治区", "呼和浩特市"),
    ("西藏自治区", "拉萨市"), ("宁夏回族自治区", "银川市"), ("青海省", "西宁市"),
    ("海南省", "三亚市"), ("山东省", "烟台市")
]

REVISED_SUPPLIER_SUFFIXES_V9 = [
    '生鲜供应链', '物流有限公司', '农业合作社', '食品集团', '直采中心', '冷链物流',
    '贸易有限公司', '生态农场', '仓储配送中心', '果蔬批发', '水产直供',
    '肉食加工厂', '粮油贸易行', '优质农产基地', '生态农业发展', '渔业合作社',
    '优选', '鲜配', '直供', '农庄', '实业', '集团', '股份公司', '商贸行', '合作联社', '加工中心'
]

# 配送区域
DELIVERY_REGIONS = [
    '北京', '上海', '广州', '深圳', '成都', '杭州', '重庆', '武汉', '苏州', '南京',
    '天津', '西安', '长沙', '郑州', '昆明', '济南', '合肥', '福州', '厦门'
]

# --- V6 最终版供应商生成逻辑 ---
def generate_suppliers_v6(count=1000):
    suppliers = []
    # 简单的随机生成，允许重复，因为现实中可能重名
    for _ in range(count):
        province, city = random.choice(CITIES_AND_PROVINCES_V9)
        city_name_for_prefix = city.replace('市', '')
        name = f"{city_name_for_prefix}{random.choice(REVISED_SUPPLIER_SUFFIXES_V9)}"
        address = f"{province}{city}{fake.street_address()}"
        areas = []
        num_areas = random.randint(1, 3)
        selected_regions = random.sample(DELIVERY_REGIONS, num_areas)
        for region in selected_regions:
            distance = round(random.uniform(10.0, 500.0), 1)
            price = max(6.0, round(5 + distance * 0.1, 1))
            areas.append({"region": region, "distance": distance, "price": price, "paths": []})
        supplier = {
            "name": name, "phone": fake.phone_number(), "address": address,
            "deliveryAreas": areas, "rating": round(random.uniform(3.0, 5.0), 1),
            "status": random.choices(['InUse', 'DisUse'], weights=[0.9, 0.1], k=1)[0]
        }
        suppliers.append(supplier)
    return suppliers

# --- V17 最终版产品生成逻辑 ---

# V8 价格生成器
def generate_realistic_price(min_price, max_price):
    if min_price > max_price: min_price, max_price = max_price, min_price
    base_price = random.uniform(min_price, max_price)
    integer_part = int(base_price)
    endings = [0.0, 0.5, 0.8, 0.9]
    weights = [0.1, 0.4, 0.1, 0.4]
    chosen_ending = random.choices(endings, weights=weights, k=1)[0]
    final_price = integer_part + chosen_ending
    if final_price < min_price: final_price += 1.0
    if final_price > max_price: final_price = max_price
    return round(final_price, 1)

# V17 最终数据结构：超大规模、超细粒度“组件”数据库
ULTIMATE_PRODUCT_COMPONENTS_V17 = {
    "水果": [
        {"item": "苹果", "variety": ["红富士", "阿克苏糖心", "嘎啦", "黄元帅", "青蛇果", "花牛"], "origin": ["山东烟台", "新疆", "陕西洛川", "甘肃静宁", "新西兰"], "brand": [], "feature": ["有机", "精选", "当季"], "spec": ["500g", "1kg", "1.5kg", "4个装", "家庭装"], "price_range": (10.0, 60.0)},
        {"item": "奇异果", "variety": ["阳光金果", "魅力金果", "绿心", "红心猕猴桃"], "origin": ["新西兰", "四川蒲江", "陕西周至"], "brand": ["佳沛"], "feature": ["有机", "进口", "空运"], "spec": ["4个装", "6个装", "12个装", "巨无霸单果"], "price_range": (25.0, 120.0)},
        {"item": "车厘子", "variety": ["宾莹", "拉宾斯", "桑提娜"], "origin": ["智利", "美国", "澳洲", "大连"], "brand": [], "feature": ["进口", "空运", "JJ级", "JJJ级"], "spec": ["250g", "500g", "1kg", "2kg原箱"], "price_range": (40.0, 300.0)},
        {"item": "草莓", "variety": ["红颜99", "奶油", "白雪公主", "巧克力"], "origin": ["丹东", "北京昌平", "本地大棚"], "brand": [], "feature": ["有机", "精选", "头茬"], "spec": ["250g", "400g", "500g", "精品礼盒"], "price_range": (20.0, 120.0)},
        {"item": "芒果", "variety": ["贵妃芒", "凯特芒", "桂七香芒", "澳芒", "小台农", "金煌芒"], "origin": ["海南", "四川攀枝花", "广西", "进口"], "brand": [], "feature": ["树上熟", "空运", "精选大果"], "spec": ["500g", "1kg", "1.5kg", "2-3个装"], "price_range": (15.0, 80.0)},
        {"item": "榴莲", "variety": ["金枕", "猫山王", "干尧"], "origin": ["泰国", "马来西亚"], "brand": [], "feature": ["树上熟", "A果", "冷冻果肉"], "spec": ["500g果肉", "1kg果肉", "原只(约2-3kg)"], "price_range": (80.0, 400.0)},
        {"item": "柑橘", "variety": ["砂糖橘", "沃柑", "丑橘不知火", "春见耙耙柑", "爱媛38号"], "origin": ["广西", "四川", "云南", "湖北"], "brand": [], "feature": ["精选", "家庭装", "无核"], "spec": ["500g", "1kg", "1.5kg", "2.5kg礼盒"], "price_range": (12.0, 70.0)},
        {"item": "橙子", "variety": ["脐橙", "血橙", "冰糖橙", "夏橙"], "origin": ["赣南", "奉节", "进口新奇士", "云南"], "brand": [], "feature": ["有机", "多维C"], "spec": ["1kg", "1.5kg", "2kg", "4个装"], "price_range": (20.0, 80.0)},
        {"item": "葡萄", "variety": ["阳光玫瑰", "夏黑无籽", "巨峰", "红提", "蓝宝石", "妮娜皇后", "青提"], "origin": ["新疆", "云南", "河北宣化", "进口"], "brand": [], "feature": ["无籽", "精选", "高山", "当季"], "spec": ["500g", "800g", "1kg", "礼盒装"], "price_range": (18.0, 150.0)},
        {"item": "瓜", "variety": ["麒麟西瓜", "硒砂瓜", "哈密瓜", "羊角蜜", "博洋9号"], "origin": ["海南", "北京大兴", "宁夏", "山东", "新疆"], "brand": [], "feature": ["吊蔓", "爆甜", "皮薄"], "spec": ["单只约2kg", "单只约4kg", "切块500g"], "price_range": (15.0, 80.0)},
        {"item": "桃", "variety": ["水蜜桃", "黄桃", "油桃", "蟠桃"], "origin": ["北京平谷", "无锡阳山", "山东蒙阴", "奉化玉露"], "brand": [], "feature": ["有机", "爆汁", "脆甜"], "spec": ["4个礼盒装", "500g", "1kg", "家庭装"], "price_range": (15.0, 80.0)},
        {"item": "李子", "variety": ["红心李", "恐龙蛋", "黑布林", "三华李", "青脆李"], "origin": ["四川", "新疆", "福建", "进口"], "brand": [], "feature": ["爆汁", "酸甜"], "spec": ["500g", "1kg"], "price_range": (15.0, 60.0)},
        {"item": "梨", "variety": ["皇冠梨", "雪花梨", "香梨", "玉露香梨", "南果梨"], "origin": ["河北", "新疆库尔勒", "安徽砀山", "山西"], "brand": [], "feature": ["多汁", "清甜", "润肺"], "spec": ["1kg", "1.5kg", "4个装"], "price_range": (12.0, 50.0)},
        {"item": "柚子", "variety": ["琯溪蜜柚", "沙田柚", "红心柚", "三红蜜柚"], "origin": ["福建平和", "广西容县", "重庆梁平"], "brand": [], "feature": ["皮薄", "多汁"], "spec": ["单果(约1-1.5kg)", "2个装"], "price_range": (15.0, 50.0)},
        {"item": "蓝莓", "variety": [], "origin": ["云南", "山东", "智利", "秘鲁"], "brand": [], "feature": ["有机", "大果", "空运"], "spec": ["125g", "2盒装", "家庭装500g"], "price_range": (15.0, 80.0)},
        {"item": "牛油果", "variety": ["哈斯"], "origin": ["墨西哥", "秘鲁", "云南"], "brand": [], "feature": ["进口", "即食", "有机"], "spec": ["2个装", "3个装", "家庭装"], "price_range": (18.0, 60.0)},
        {"item": "芭乐",  "variety": ["珍珠", "红心", "水晶"], "origin": ["广东", "福建", "台湾", "广西"],  "brand": [], "feature": ["有机", "无籽", "胭脂红", "脆甜"], "spec": ["500g", "1kg", "2个装", "3个大果装"], "price_range": (15.0, 45.0)},
        {"item": "火龙果", "variety": ["红心", "白心", "麒麟果(黄皮)"], "origin": ["海南", "广西", "云南", "越南", "哥伦比亚"], "brand": [], "feature": ["有机", "进口", "爆甜", "不麻嘴"], "spec": ["单果(约400g)", "2个装", "1.5kg家庭装", "礼盒装"], "price_range": (12.0, 70.0)}
    ],
    "蔬菜": [
        {"item": "番茄", "variety": ["普罗旺斯", "铁皮", "千禧圣女果", "草本", "粉番茄"], "origin": ["本地", "山东寿光"], "brand": [], "feature": ["有机", "串收", "沙瓤"], "spec": ["300g", "400g", "500g", "一盒"], "price_range": (8.0, 35.0)},
        {"item": "黄瓜", "variety": ["水果", "旱黄瓜", "小青瓜"], "origin": ["本地", "山东"], "brand": [], "feature": ["有机", "无刺", "顶花带刺"], "spec": ["2根装", "3根装", "500g"], "price_range": (5.0, 22.0)},
        {"item": "菌菇", "variety": ["羊肚菌", "松茸", "牛肝菌", "蟹味菇", "白玉菇", "杏鲍菇", "香菇", "口蘑", "平菇"], "origin": ["云南", "古田", "河北"], "brand": [], "feature": ["野生", "新鲜", "精选"], "spec": ["100g", "150g", "200g", "一盒"], "price_range": (7.0, 200.0)},
        {"item": "叶菜", "variety": ["奶油生菜", "罗马生菜", "小油菜", "菠菜", "空心菜", "娃娃菜", "芝麻菜", "上海青", "茼蒿"], "origin": ["本地", "高山", "云南"], "brand": [], "feature": ["有机", "水培", "免洗"], "spec": ["200g", "250g", "一把", "一袋"], "price_range": (4.0, 25.0)},
        {"item": "根茎", "variety": ["山药", "土豆", "洋葱", "白萝卜", "胡萝卜", "莲藕", "芋头", "红薯", "紫薯"], "origin": ["铁棍", "荷兰", "本地"], "brand": [], "feature": ["有机", "高山", "沙地"], "spec": ["一根", "500g", "750g", "一袋"], "price_range": (5.0, 30.0)},
        {"item": "茄果", "variety": ["长茄子", "圆茄子", "青椒", "彩椒", "螺丝椒", "线椒", "小米辣"], "origin": ["本地", "山东"], "brand": [], "feature": ["有机", "薄皮"], "spec": ["2个装", "500g", "一盒"], "price_range": (6.0, 25.0)},
    ],
    "肉禽": [
        {"item": "猪五花肉", "origin": ["本地", "山东"], "brand": ["壹号土猪", "网易味央", "黑猪"], "feature": ["冷鲜", "精切", "去皮"], "spec": ["250g", "300g", "500g"], "price_range": (18.0, 90.0)},
        {"item": "猪里脊", "origin": ["本地"], "brand": ["壹号土猪", "黑猪"], "feature": ["冷鲜", "小炒"], "spec": ["300g", "400g"], "price_range": (22.0, 70.0)},
        {"item": "猪排骨", "origin": ["本地"], "brand": ["黑猪"], "feature": ["冷鲜", "精切", "寸骨"], "spec": ["500g", "1kg"], "price_range": (30.0, 100.0)},
        {"item": "西冷牛排", "origin": ["澳洲", "美国"], "brand": ["科尔沁", "恒都", "大希地"], "feature": ["进口", "谷饲", "原切"], "spec": ["200g", "250g"], "price_range": (35.0, 150.0)},
        {"item": "眼肉牛排", "origin": ["澳洲", "美国"], "brand": ["科尔沁", "恒都"], "feature": ["进口", "M5和牛"], "spec": ["200g", "250g"], "price_range": (50.0, 350.0)},
        {"item": "鸡翅中", "origin": ["本地", "山东"], "brand": ["圣农", "泰森"], "feature": ["冰鲜", "奥尔良腌制"], "spec": ["300g", "500g", "1kg"], "price_range": (20.0, 60.0)},
    ],
    "水产": [
        {"item": "基围虾", "origin": ["广东", "福建"], "brand": [], "feature": ["鲜活", "游水"], "spec": ["250g", "500g"], "price_range": (25.0, 80.0)},
        {"item": "厄瓜多尔白虾", "origin": ["进口"], "brand": ["国联"], "feature": ["去壳虾仁", "黑虎虾"], "spec": ["500g", "1kg", "净重"], "price_range": (40.0, 120.0)},
        {"item": "小龙虾", "origin": ["潜江", "盱眙"], "brand": [], "feature": ["鲜活", "麻辣熟食", "蒜蓉"], "spec": ["500g", "1kg", "2kg"], "price_range": (30.0, 150.0)},
        {"item": "鲈鱼", "variety": ["海鲈鱼", "河鲈鱼"], "origin": ["舟山", "本地"], "brand": [], "feature": ["鲜活", "冰鲜", "去骨"], "spec": ["一条(约500g)", "一条(约600g)"], "price_range": (20.0, 60.0)},
        {"item": "三文鱼", "origin": ["挪威", "智利"], "brand": [], "feature": ["冰鲜", "刺身级", "空运"], "spec": ["中段250g", "鱼腩200g", "整条"], "price_range": (50.0, 300.0)},
        {"item": "大闸蟹", "origin": ["阳澄湖", "江苏兴化", "固城湖"], "brand": [], "feature": ["鲜活", "爆膏", "精选公蟹", "精选母蟹"], "spec": ["4只装", "6只装", "8只礼盒装"], "price_range": (100.0, 600.0)},
        {"item": "生蚝", "origin": ["乳山", "湛江", "法国吉娜朵"], "brand": [], "feature": ["鲜活", "刺身级"], "spec": ["6只装", "12只装", "一箱"], "price_range": (40.0, 300.0)},
    ],
    "速食": [
        {"item": "猪肉白菜水饺", "brand": ["湾仔码头", "思念", "三全", "必品阁"], "feature": ["手工", "皮薄馅大"], "spec": ["320g", "500g", "720g", "1kg"], "price_range": (12.0, 45.0)},
        {"item": "虾仁三鲜水饺", "brand": ["湾仔码头", "船歌鱼", "三全"], "feature": ["含整只虾仁"], "spec": ["320g", "500g", "700g"], "price_range": (20.0, 60.0)},
        {"item": "黑芝麻汤圆", "brand": ["思念玉", "湾仔码头", "缸鸭狗"], "feature": ["宁波风味", "流沙馅"], "spec": ["320g", "454g", "一盒12只"], "price_range": (10.0, 35.0)},
        {"item": "手抓饼", "brand": ["安井", "思念"], "feature": ["原味", "葱香"], "spec": ["10片装", "20片装"], "price_range": (15.0, 40.0)},
    ]
}

# V14 描述生成器
DESCRIPTION_TEMPLATES = {
    "水果": { "origin": ["源自著名的{origin}产区，", "来自阳光充足的{origin}核心果园，"], "feature": ["果形饱满，色泽鲜艳。", "采用有机种植方式，天然健康。"], "taste": ["口感清脆爽口，汁水丰盈。", "果肉细腻，入口即化。"], "usage": ["是您家庭分享的健康之选。", "富含多种维生素，是补充营养的佳品。"]},
    "DEFAULT": { "origin": ["源自核心产区，"], "feature": ["品质上乘，经过严格筛选。"], "taste": ["口感纯正，风味十足。"], "usage": ["是您厨房中的理想选择。"]}
}
def generate_realistic_description(name, category, component):
    template = DESCRIPTION_TEMPLATES.get(category, DESCRIPTION_TEMPLATES.get("DEFAULT"))
    origin_keyword = category
    all_prefixes = list(itertools.chain(component.get('origin',[]), component.get('brand',[]), component.get('variety',[]), component.get('feature',[])))
    sorted_prefixes = sorted(all_prefixes, key=len, reverse=True)
    for p in sorted_prefixes:
        if p in name:
            origin_keyword = p
            break
    origin_phrase = random.choice(template["origin"]).format(origin=origin_keyword)
    feature_phrase = random.choice(template["feature"])
    taste_phrase = random.choice(template["taste"])
    usage_phrase = random.choice(template["usage"])
    return f"【{category}臻选】{origin_phrase}{feature_phrase}{taste_phrase}{usage_phrase}"

# V16 名称构建引擎
def build_product_name_v16(component):
    parts = []
    # 每种类型最多选一个，且有概率不选
    if component.get("brand") and random.random() < 0.5: parts.append(random.choice(component["brand"]))
    if component.get("origin") and random.random() < 0.7: parts.append(random.choice(component["origin"]))
    if component.get("feature") and random.random() < 0.6: parts.append(random.choice(component["feature"]))
    
    item_name = component["item"]
    if component.get("variety") and random.random() < 0.8:
        # 如果品种和核心名不同，则组合，否则只用品种
        variety = random.choice(component["variety"])
        if variety not in item_name:
            item_name = f"{variety} {item_name}"
        else:
            item_name = variety
    
    parts.append(item_name)
    
    final_parts = list(dict.fromkeys(parts)) # 去重
    name = " ".join(final_parts)
    name += f" {random.choice(component['spec'])}"
    return " ".join(name.split()) # 再次清理多余空格

def generate_products_v17(count=10000):
    """V17最终版：通过动态生成确保数量，通过智能拼接确保逻辑正确。"""
    print("V17: 正在按需生成高质量产品...")
    generated_products = []
    used_names = set()
    product_id_counter = 10001
    
    all_components = []
    for category_name, component_list in ULTIMATE_PRODUCT_COMPONENTS_V17.items():
        for component in component_list:
            component['category'] = category_name
            all_components.append(component)

    if not all_components:
        print("错误：产品组件数据库为空！")
        return []

    max_attempts = count * 100 # 增加尝试次数以应对高密度下的随机碰撞
    attempts = 0

    while len(generated_products) < count and attempts < max_attempts:
        attempts += 1
        
        component = random.choice(all_components)
        
        name = build_product_name_v16(component)
        
        if name in used_names:
            continue
            
        used_names.add(name)
        
        min_price, max_price = component["price_range"]
        price = generate_realistic_price(min_price, max_price)
        
        description = generate_realistic_description(name, component["category"], component)

        product = {
            "productId": product_id_counter,
            "name": name,
            "description": description,
            "price": price,
            "quantityInStock": random.randint(50, 3000)
        }
        generated_products.append(product)
        product_id_counter += 1

    if len(generated_products) < count:
        print(f"警告：已达到最大尝试次数，但未能生成足够的唯一产品。实际生成数量为 {len(generated_products)}")
        
    print(f"V17: 产品数据生成完成，共计 {len(generated_products)} 条。")
    return generated_products


if __name__ == "__main__":
    start_time = time.time()
    
    # --- 生成供应商数据 ---
    print("开始生成供应商数据 (V6最终版)...")
    suppliers_data = generate_suppliers_v6(1000)
    with open('suppliers_final.json', 'w', encoding='utf-8') as f:
        json.dump(suppliers_data, f, ensure_ascii=False, indent=2)
    print(f"✅ {len(suppliers_data)}个供应商数据已成功生成并保存到 suppliers_final.json 文件中。 (耗时: {time.time() - start_time:.2f}秒)")

    # --- 生成产品数据 ---
    product_start_time = time.time()
    print("\n开始生成产品数据 (V17最终版)...")
    products_data = generate_products_v17(10000)
    with open('products_final.json', 'w', encoding='utf-8') as f:
        json.dump(products_data, f, ensure_ascii=False, indent=2)
    print(f"✅ {len(products_data)}个产品数据已成功生成并保存到 products_final.json 文件中。 (耗时: {time.time() - product_start_time:.2f}秒)")
    
    print(f"\n总耗时: {time.time() - start_time:.2f}秒")