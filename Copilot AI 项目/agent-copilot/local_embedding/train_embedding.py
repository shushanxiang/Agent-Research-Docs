import json

from sentence_transformers import SentenceTransformer, InputExample, losses, evaluation
from torch.utils.data import DataLoader
import pandas as pd




def train(train_file):  # 1. 准备训练数据
    # 假设你有一个包含句子对的 CSV 文件，其中第一列为句子1，第二列为句子2，第三列为相似度标签（0或1）
    with open(train_file,encoding='utf-8')as f:
        datas = json.load(f)
        train_examples = []
        for data in datas:
            train_examples.append(InputExample(texts=[data["sentences"], data["api"]], label=1))
            train_examples.append(InputExample(texts=[data["negative_sentences"], data["api"]], label=0))


    model = SentenceTransformer("/root/autodl-tmp/models/BAAI/bge-large-zh-v1.5")  # 中文模型[^2^]

    # 3. 定义训练参数
    train_loss = losses.CosineSimilarityLoss(model=model)
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)
    num_epochs = 3

    # 4. 定义评估器（可选）
    # 假设你有一个验证集，用于评估模型性能
    evaluator = evaluation.EmbeddingSimilarityEvaluator.from_input_examples(
        train_examples[:100], name="validation"
    )

    # 5. 训练模型
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=num_epochs,
        evaluator=evaluator,
        evaluation_steps=1000,
        save_best_model=True,
        show_progress_bar=True,
    )

    # 6. 保存模型
    model.save("output/bge_model")


if __name__ == "__main__":
    train("new_dataset_train.json")
