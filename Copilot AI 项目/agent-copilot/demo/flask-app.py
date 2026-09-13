# coding = utf-8

from flask import Flask, request, jsonify
from openai import OpenAI
import json
import os
from flasgger import Swagger, swag_from

from utils import model_api_key, model_base_url, model_name

app = Flask(__name__)
Swagger(app)
# 初始化 OpenAI 客户端（基于阿里 DashScope）
client = OpenAI(
    api_key=model_api_key,
    base_url=model_base_url
)

@app.route('/sentiment_analysis', methods=['POST'])
def mesh_query():
    """
        情感分析
        ---
        tags:
          - sentiment API
        description:
            情感分析接口，json格式
        parameters:
          - name: body
            in: body
            required: true
            schema:
              id: 情感分析body
              required:
                - query
              properties:
                query:
                  type: string
                  description: 分析语句.

        responses:
          200:
              description: 转化成功
              schema:
                type: object
                properties:
                  message:
                    type: string
        """
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({'error': 'Missing query parameter'}), 400

    query = data['query']
    content = query + '''
            \n
        ------------------------
        请分析上述文本的情感
        请直接输出结果，不需要输出额外的解释 
    '''
    try:
        completion = client.chat.completions.create(
            model=model_name,
            temperature=0.6,
            messages=[
                {'role': 'user', 'content': content}
            ]
        )
        response_text = completion.choices[0].message.content.strip()
        return {"message":response_text}

    except Exception as e:
        return jsonify({'message': str(e)})

@app.route('/api', methods=['GET'])
def get_data_index():
    """
    获取指定 ID 的数据
    这是一个带有路径参数的 GET 方法，用于根据 ID 返回特定数据。
    ---
    tags:
      - Sample API
    parameters:
      - name: item_id
        in: query
        type: string
        required: true
        description: 数据的唯一标识符
    responses:
      200:
        description: 成功返回指定 ID 的数据
        schema:
          type: object
          properties:
            message:
              type: string
      404:
        description: 未找到指定 ID 的数据
        schema:
          type: object
          properties:
            error:
              type: string
              example: Item not found
    """
    item_id  = request.args.get('item_id')
    if item_id == "123":
        data = {"message": f"Data for item_id: {item_id}"}
    else:
        return jsonify({"error": "Item not found"}), 404
    return jsonify(data)

@app.route('/api/data', methods=['GET'])
def get_data():
    """
    获取样本数据
    这是一个简单的 GET 方法，用于返回样本数据。
    ---
    tags:
      - Sample API
    responses:
      200:
        description: 成功返回样本数据
        schema:
          type: object
          properties:
            message:
              type: string
              example: This is a sample data response
    """
    data = {"message": "This is a sample data response"}
    return jsonify(data)

if __name__ == '__main__':
    print("Swagger访问地址：http://127.0.0.1:5001/apidocs")
    app.run(debug=False, host='0.0.0.0', port=5001)
